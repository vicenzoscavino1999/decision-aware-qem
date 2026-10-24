from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import yaml
from qiskit import transpile
from qiskit_aer import AerSimulator

import experiments.a3_pullback_frontier as a3
from experiments.confirmatory_instance_manifest import _difficulty_bounds
from daqem.candidates import (
    build_candidate_landscape_for_graph,
    graph_seed_for_instance,
    maxcut_values_for_graph,
)
from daqem.dynamic import epsilon_opt_from_ideal_values
from daqem.gap_kernel import nearest_psd
from daqem.auxiliary_noise import simulate_primitives, write_primitive_evidence, evaluation_shot_counts
from daqem.decisions import integer_shot_sums, zne_failures
from daqem.qaoa import maxcut_graph, qaoa_maxcut_circuit
from daqem.risk import gri_risk
from daqem.rng import make_rng
from daqem.selectors import da_selector, mse_selector
from daqem.structured_noise import structured_noise_model_factory


CONFIG_PATH = REPO_ROOT / "reproducibility" / "config" / "r1_full.yaml"
OUTPUT_DIR = REPO_ROOT / "results" / "r1_full"
METHODS = ("Raw", "Accuracy-ZNE", "Decision-ZNE")


def load_config(path: Path = CONFIG_PATH) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _jsonable(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def _r1_graph(instance_id: str, config: dict):
    cell = config["primary_cell"]
    return maxcut_graph(
        num_qubits=int(cell["num_qubits"]),
        degree=int(cell["degree"]),
        seed=graph_seed_for_instance(instance_id),
    )


def _landscape_for_graph(instance_id: str, graph, config: dict):
    cell = config["primary_cell"]
    return build_candidate_landscape_for_graph(
        instance_id,
        graph,
        candidate_count=int(cell["candidate_count"]),
        depth=int(cell["depth"]),
        local_radius=float(cell["local_radius"]),
        search_radius=float(cell["search_radius"]),
        search_count=int(cell["search_count"]),
    )


def _gate0_config(config: dict) -> dict[str, Any]:
    cell = config["primary_cell"]
    gate0 = dict(a3.load_gate0_config("full"))
    gate0.update(
        {
            "candidate_count": int(cell["candidate_count"]),
            "budget_grid": [int(budget) for budget in cell["budget_grid"]],
            "B_max": max(int(budget) for budget in cell["budget_grid"]),
            "local_radius": float(cell["local_radius"]),
            "search_radius": float(cell["search_radius"]),
            "search_count": int(cell["search_count"]),
            "depth": int(cell["depth"]),
            "qubits": int(cell["num_qubits"]),
            "graph_degree": int(cell["degree"]),
        }
    )
    return gate0


def _primitive_moments_on_graph(
    *,
    instance_id: str,
    graph,
    config: dict,
    gate0_config: dict[str, Any],
    noise_model_factory,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, bool]:
    data = simulate_primitives(instance_id=instance_id, graph=graph,
        gate0_config=gate0_config, noise_model_factory=noise_model_factory)
    return data['means'], data['variances'], data['ideal_values'], np.asarray(data['x_star']), True


def build_epsilon_manifest(config: dict, output_dir: Path) -> tuple[list[dict[str, Any]], dict[str, float]]:
    rows = []
    for instance_id in config["instance_ids"]:
        graph = _r1_graph(instance_id, config)
        landscape = _landscape_for_graph(instance_id, graph, config)
        epsilon = epsilon_opt_from_ideal_values(
            landscape.ideal_values,
            quantile=float(config["primary_cell"]["epsilon_opt_quantile"]),
        )
        rows.append(
            {
                "instance_id": instance_id,
                "graph_seed": int(graph_seed_for_instance(instance_id)),
                "epsilon_opt_ideal": float(epsilon),
                "x_star": int(landscape.x_star),
            }
        )
    eps = np.array([row["epsilon_opt_ideal"] for row in rows], dtype=float)
    q1, q2 = _difficulty_bounds(eps)
    for row in rows:
        value = float(row["epsilon_opt_ideal"])
        if value <= q1:
            row["difficulty_tercile"] = "hard"
        elif value <= q2:
            row["difficulty_tercile"] = "medium"
        else:
            row["difficulty_tercile"] = "easy"
    bounds = {"hard_medium": float(q1), "medium_easy": float(q2)}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "epsilon_opt_manifest.json").write_text(
        json.dumps({"rows": rows, "tercile_bounds": bounds}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return rows, bounds


def _method_values(coefficients: np.ndarray, means: np.ndarray) -> np.ndarray:
    return np.einsum("s,sk->k", np.asarray(coefficients, dtype=float), np.asarray(means, dtype=float))


def _method_unit_variance(coefficients: np.ndarray, variances: np.ndarray) -> np.ndarray:
    coeffs = np.asarray(coefficients, dtype=float)
    return np.einsum("s,sk->k", coeffs * coeffs, np.asarray(variances, dtype=float))


def phase_a_instance(
    *,
    instance_id: str,
    config: dict,
    gate0_config: dict[str, Any],
) -> dict[str, Any]:
    graph = _r1_graph(instance_id, config)
    noise_factory = structured_noise_model_factory(config, graph)
    primitive_data = simulate_primitives(instance_id=instance_id, graph=graph,
        gate0_config=gate0_config, noise_model_factory=noise_factory)
    means, variances = primitive_data['means'], primitive_data['variances']
    ideal_values, x_star_arr = primitive_data['ideal_values'], primitive_data['x_star']
    graph_match = True
    x_star = int(x_star_arr)
    candidate_count = len(ideal_values)
    competitors = [idx for idx in range(candidate_count) if idx != x_star]
    ideal_values = np.asarray(ideal_values, dtype=float)
    coeffs_by_method = a3.method_coefficients_from_true_cdev(
        primitive_variance_unit=variances,
        ideal_values=ideal_values,
        x_star=x_star,
        gate0_config=gate0_config,
    )
    cdev_diag = np.asarray(variances, dtype=float).reshape(-1)
    method_data = {}
    for method in METHODS:
        coeffs = np.asarray(coeffs_by_method[method], dtype=float)
        values = _method_values(coeffs, means)
        mu = values[competitors] - float(values[x_star])
        gap_map = a3._gap_map(coeffs, candidate_count, x_star)
        sigma_unit = nearest_psd((gap_map * cdev_diag) @ gap_map.T)
        unit_var = _method_unit_variance(coeffs, variances)
        method_data[method] = {
            "coefficients": coeffs,
            "values": values,
            "mu": mu,
            "sigma_unit": sigma_unit,
            "unit_var_by_candidate": unit_var,
        }
    budgets = [int(budget) for budget in gate0_config["budget_grid"]]
    budget_rows = []
    for budget in budgets:
        gri_by_method = {
            method: float(gri_risk(data["mu"], data["sigma_unit"], B=budget))
            for method, data in method_data.items()
        }
        mse_by_method = {}
        for method, data in method_data.items():
            bias_sq = (np.asarray(data["values"], dtype=float) - ideal_values) ** 2
            mse_by_method[method] = float(
                np.mean(bias_sq + np.asarray(data["unit_var_by_candidate"]) / float(budget))
            )
        da_method = da_selector(gri_by_method)
        mse_method = mse_selector(mse_by_method)
        raw_gri = gri_by_method["Raw"]
        da_gri = gri_by_method[da_method]
        relative = None if raw_gri <= 0 else float((raw_gri - da_gri) / raw_gri)
        budget_rows.append(
            {
                "budget": budget,
                "evaluation_shots": evaluation_shot_counts(budget,candidate_count),
                "GRI": gri_by_method,
                "MSE": mse_by_method,
                "DA_selected_method": da_method,
                "MSE_selected_method": mse_method,
                "DA_beats_Raw": bool(da_gri < raw_gri),
                "relative_savings_DA_vs_Raw": relative,
                "rho_gap_noise": None if relative is None else float(relative / 0.20),
            }
        )
    return {
        "instance_id": instance_id,
        "primitive_data": primitive_data,
        "input_config": config,
        "graph_match": bool(graph_match),
        "x_star": x_star,
        "ideal_values": ideal_values,
        "means": means,
        "variances": variances,
        "coefficients": {method: np.asarray(coeffs_by_method[method], dtype=float) for method in METHODS},
        "method_data": method_data,
        "budgets": budget_rows,
    }


def summarize_phase_a(instance_results: list[dict[str, Any]], budgets: list[int]) -> dict[str, Any]:
    summary = {}
    n = len(instance_results)
    for budget in budgets:
        rows = [
            next(row for row in result["budgets"] if int(row["budget"]) == int(budget))
            for result in instance_results
        ]
        count = sum(bool(row["DA_beats_Raw"]) for row in rows)
        rho_values = [row["rho_gap_noise"] for row in rows if row["rho_gap_noise"] is not None]
        summary[str(budget)] = {
            "DA_beats_Raw_count": int(count),
            "n_instances": int(n),
            "majority": bool(count > n / 2),
            "rho_mean": None if not rho_values else float(np.mean(rho_values)),
            "rho_min": None if not rho_values else float(np.min(rho_values)),
            "rho_max": None if not rho_values else float(np.max(rho_values)),
        }
    return summary


def _state_probability_arrays(
    *,
    instance_id: str,
    graph,
    config: dict,
    gate0_config: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    data = simulate_primitives(instance_id=instance_id, graph=graph, gate0_config=gate0_config,
        noise_model_factory=structured_noise_model_factory(config,graph))
    return data['probabilities'], data['values_by_state'], data['ideal_values'], data['x_star']


def empirical_instance(
    *,
    instance_result: dict[str, Any],
    config: dict,
    gate0_config: dict[str, Any],
    sample_archive_dir: Path | None = None,
) -> list[dict[str, Any]]:
    instance_id = str(instance_result["instance_id"])
    graph = _r1_graph(instance_id, config)
    if 'primitive_data' in instance_result:
        if instance_result.get('input_config') != config:
            raise ValueError('primitive data belong to a different configuration')
        data = instance_result['primitive_data']
        probs,values_by_state,ideal_values,x_star = (data[k] for k in ('probabilities','values_by_state','ideal_values','x_star'))
    else:
        probs,values_by_state,ideal_values,x_star = _state_probability_arrays(
            instance_id=instance_id, graph=graph, config=config, gate0_config=gate0_config)
    if not np.array_equal(ideal_values,instance_result['ideal_values']):
        raise ValueError('empirical ideal landscape mismatch')
    if x_star != int(instance_result["x_star"]):
        raise ValueError("empirical x_star mismatch")
    budgets = [int(budget) for budget in gate0_config["budget_grid"]]
    replicates = config["primary_cell"]["replicates"]
    if int(replicates)!=replicates or replicates<1:
        raise ValueError('replicates must be a positive integer')
    replicates = int(replicates)
    competitors = [i for i in range(len(ideal_values)) if i!=x_star]
    samples = {'budget':[], 'replicate':[], 'primitive_sums':[]}
    rows = []
    for budget in budgets:
        phase_a_row = next(row for row in instance_result["budgets"] if int(row["budget"]) == budget)
        da_method = str(phase_a_row["DA_selected_method"])
        mse_method = str(phase_a_row["MSE_selected_method"])
        failure_counts = {method: 0 for method in METHODS}
        failure_counts["DA_selected"] = 0
        failure_counts["MSE_selected"] = 0
        for replicate_id in range(replicates):
            rng = make_rng(
                instance_id=instance_id,
                method="R1_structured_empirical",
                budget=budget,
                replicate_id=replicate_id,
                stream="multinomial_probabilities",
            )
            primitive_estimates = np.empty(probs.shape[:2], dtype=float)
            for scale_idx in range(probs.shape[0]):
                for candidate_idx in range(probs.shape[1]):
                    counts = rng.multinomial(int(budget), probs[scale_idx, candidate_idx])
                    primitive_estimates[scale_idx, candidate_idx] = float(
                        np.dot(counts, values_by_state) / float(budget)
                    )
            sums = integer_shot_sums(primitive_estimates,budget)
            failures = {
                'Raw': int(np.any(sums[0,competitors] <= sums[0,x_star])),
                'Accuracy-ZNE': int(zne_failures(primitive_estimates[None],x_star,budget)[0]),
                'Decision-ZNE': int(zne_failures(primitive_estimates[None],x_star,budget,
                    coefficients=instance_result['coefficients']['Decision-ZNE'])[0]),
            }
            for method in METHODS:
                failure_counts[method] += failures[method]
            failure_counts['DA_selected'] += failures[da_method]
            failure_counts['MSE_selected'] += failures[mse_method]
            if sample_archive_dir is not None:
                samples['budget'].append(budget)
                samples['replicate'].append(replicate_id)
                samples['primitive_sums'].append(sums)
        denom = float(replicates)
        failure_rates = {key: float(value / denom) for key, value in failure_counts.items()}
        raw = failure_rates["Raw"]
        da = failure_rates["DA_selected"]
        rows.append(
            {
                "instance_id": instance_id,
                "budget": budget,
                "evaluation_shots": evaluation_shot_counts(budget,len(ideal_values)),
                "replicates": replicates,
                "DA_selected_method": da_method,
                "MSE_selected_method": mse_method,
                "failure_counts": failure_counts,
                "failure_rates": failure_rates,
                "absolute_reduction_DA_vs_Raw": float(raw - da),
                "relative_reduction_DA_vs_Raw": None if raw <= 0.0 else float((raw - da) / raw),
                "predicted_GRI": phase_a_row["GRI"],
            }
        )
    if sample_archive_dir is not None:
        sample_archive_dir.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(sample_archive_dir/f'{instance_id}_samples.npz',**samples)
    return rows


def aggregate_empirical(
    empirical_rows: list[dict[str, Any]],
    phase_a_results: list[dict[str, Any]],
    epsilon_rows: list[dict[str, Any]],
    budgets: list[int],
) -> dict[str, Any]:
    epsilon_by_id = {row["instance_id"]: row for row in epsilon_rows}
    ids=[item['instance_id'] for item in phase_a_results]
    keys=[(row['instance_id'],int(row['budget'])) for row in empirical_rows]
    if len(set(ids))!=len(ids) or len(epsilon_by_id)!=len(epsilon_rows) or set(ids)!=set(epsilon_by_id):
        raise ValueError('instance lists must match without duplicates')
    if len(set(keys))!=len(keys) or set(keys)!={(i,int(b)) for i in ids for b in budgets}:
        raise ValueError('missing or duplicate instance/budget records')
    aggregate = {}
    by_instance_budget = {}
    for row in empirical_rows:
        by_instance_budget[(row["instance_id"], int(row["budget"]))] = row
    for budget in budgets:
        rows = [row for row in empirical_rows if int(row["budget"]) == int(budget)]
        total_reps = int(sum(row["replicates"] for row in rows))
        failure_by_key = {}
        for key in ["Raw", "Accuracy-ZNE", "Decision-ZNE", "DA_selected", "MSE_selected"]:
            total_fail = sum(int(row["failure_counts"][key]) for row in rows)
            failure_by_key[key] = float(total_fail / total_reps)
        raw = failure_by_key["Raw"]
        da = failure_by_key["DA_selected"]
        predicted = {
            method: float(
                np.mean(
                    [
                        next(r for r in result["budgets"] if int(r["budget"]) == int(budget))["GRI"][method]
                        for result in phase_a_results
                    ]
                )
            )
            for method in METHODS
        }
        aggregate[str(budget)] = {
            "total_replicates": total_reps,
            "failure_rates": failure_by_key,
            "absolute_reduction_DA_vs_Raw": float(raw - da),
            "relative_reduction_DA_vs_Raw": None if raw <= 0.0 else float((raw - da) / raw),
            "predicted_mean_GRI": predicted,
            "predicted_minus_empirical": {
                method: float(predicted[method] - failure_by_key[method]) for method in METHODS
            },
        }
    continuous = {}
    for budget in budgets:
        eps = []
        abs_red = []
        rel_red = []
        eps_relative = []
        for instance_id in epsilon_by_id:
            row = by_instance_budget[(instance_id, int(budget))]
            eps.append(float(epsilon_by_id[instance_id]["epsilon_opt_ideal"]))
            abs_red.append(float(row["absolute_reduction_DA_vs_Raw"]))
            if row['relative_reduction_DA_vs_Raw'] is not None:
                rel_red.append(float(row['relative_reduction_DA_vs_Raw']))
                eps_relative.append(float(epsilon_by_id[instance_id]['epsilon_opt_ideal']))
        eps_arr = np.asarray(eps, dtype=float)
        abs_arr = np.asarray(abs_red, dtype=float)
        rel_arr = np.asarray(rel_red, dtype=float)
        continuous[str(budget)] = {
            "pearson_epsilon_vs_absolute_reduction": _corr(eps_arr, abs_arr),
            "pearson_epsilon_vs_relative_reduction": _corr(np.asarray(eps_relative), rel_arr),
            "relative_trend_valid_instances": len(rel_red),
        }
    terciles = {}
    for budget in budgets:
        budget_rows = [row for row in empirical_rows if int(row["budget"]) == int(budget)]
        grouped = {}
        for label in ("hard", "medium", "easy"):
            rows = [
                row for row in budget_rows
                if epsilon_by_id[row["instance_id"]]["difficulty_tercile"] == label
            ]
            reps = int(sum(row["replicates"] for row in rows))
            if reps == 0:
                continue
            raw_fail = sum(int(row["failure_counts"]["Raw"]) for row in rows) / float(reps)
            da_fail = sum(int(row["failure_counts"]["DA_selected"]) for row in rows) / float(reps)
            grouped[label] = {
                "n_instances": len(rows),
                "replicates": reps,
                "failure_rate_Raw": float(raw_fail),
                "failure_rate_DA": float(da_fail),
                "absolute_reduction_DA_vs_Raw": float(raw_fail - da_fail),
                "relative_reduction_DA_vs_Raw": None if raw_fail <= 0.0 else float((raw_fail - da_fail) / raw_fail),
            }
        terciles[str(budget)] = grouped
    return {
        "aggregate_by_budget": aggregate,
        "continuous_epsilon_trend": continuous,
        "terciles_descriptive": terciles,
    }


def _corr(x: np.ndarray, y: np.ndarray) -> float | None:
    if x.size < 2 or float(np.std(x)) == 0.0 or float(np.std(y)) == 0.0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def write_outputs(result: dict[str, Any], output_dir: Path = OUTPUT_DIR) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "r1_full_result.json"
    md_path = output_dir / "r1_full_result.md"
    json_path.write_text(
        json.dumps(_jsonable(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# R1 Full Structured-Noise Result",
        "",
        "Additive robustness cell. No confirmatory C-ids are used.",
        result["model_scope"],
        "",
        "## Phase A Prediction",
        "",
        "| budget | DA<Raw count | n | majority | rho_mean | rho_min | rho_max |",
        "|---:|---:|---:|:---:|---:|---:|---:|",
    ]
    for budget, row in result["phase_a_summary"].items():
        lines.append(
            "| {budget} | {count} | {n} | {maj} | {mean} | {minv} | {maxv} |".format(
                budget=budget,
                count=row["DA_beats_Raw_count"],
                n=row["n_instances"],
                maj=str(row["majority"]),
                mean=_fmt(row["rho_mean"]),
                minv=_fmt(row["rho_min"]),
                maxv=_fmt(row["rho_max"]),
            )
        )
    if result["phase_b_status"] != "completed":
        lines.extend(["", f"Phase B skipped: {result['phase_b_status']}"])
    else:
        lines.extend(
            [
                "",
                "## Phase B Empirical Aggregate",
                "",
                "| budget | fail Raw | fail Acc-ZNE | fail Dec-ZNE | fail DA | fail MSE | abs red DA-Raw | rel red DA-Raw |",
                "|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for budget, row in result["phase_b"]["aggregate_by_budget"].items():
            fr = row["failure_rates"]
            lines.append(
                "| {budget} | {raw} | {acc} | {dec} | {da} | {mse} | {absr} | {relr} |".format(
                    budget=budget,
                    raw=_fmt(fr["Raw"]),
                    acc=_fmt(fr["Accuracy-ZNE"]),
                    dec=_fmt(fr["Decision-ZNE"]),
                    da=_fmt(fr["DA_selected"]),
                    mse=_fmt(fr["MSE_selected"]),
                    absr=_fmt(row["absolute_reduction_DA_vs_Raw"]),
                    relr=_fmt(row["relative_reduction_DA_vs_Raw"]),
                )
            )
        lines.extend(
            [
                "",
                "## Predicted GRI vs Empirical Failure",
                "",
                "| budget | pred Raw | emp Raw | pred Dec-ZNE | emp Dec-ZNE |",
                "|---:|---:|---:|---:|---:|",
            ]
        )
        for budget, row in result["phase_b"]["aggregate_by_budget"].items():
            pred = row["predicted_mean_GRI"]
            emp = row["failure_rates"]
            lines.append(
                f"| {budget} | {_fmt(pred['Raw'])} | {_fmt(emp['Raw'])} | "
                f"{_fmt(pred['Decision-ZNE'])} | {_fmt(emp['Decision-ZNE'])} |"
            )
        lines.extend(
            [
                "",
                "## Epsilon-Opt Continuous Trend",
                "",
                "| budget | corr epsilon vs abs reduction | corr epsilon vs rel reduction |",
                "|---:|---:|---:|",
            ]
        )
        for budget, row in result["phase_b"]["continuous_epsilon_trend"].items():
            lines.append(
                f"| {budget} | {_fmt(row['pearson_epsilon_vs_absolute_reduction'])} | "
                f"{_fmt(row['pearson_epsilon_vs_relative_reduction'])} |"
            )
        lines.extend(
            [
                "",
                "## Epsilon-Opt Terciles (Descriptive)",
                "",
                "| budget | tercile | n | fail Raw | fail DA | abs reduction | rel reduction |",
                "|---:|:---|---:|---:|---:|---:|---:|",
            ]
        )
        for budget, groups in result["phase_b"]["terciles_descriptive"].items():
            for tercile, row in groups.items():
                lines.append(
                    f"| {budget} | {tercile} | {row['n_instances']} | "
                    f"{_fmt(row['failure_rate_Raw'])} | {_fmt(row['failure_rate_DA'])} | "
                    f"{_fmt(row['absolute_reduction_DA_vs_Raw'])} | {_fmt(row['relative_reduction_DA_vs_Raw'])} |"
                )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def _fmt(value: Any) -> str:
    if value is None:
        return "NA"
    return f"{float(value):.12g}"


def run(config_path: Path = CONFIG_PATH, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    config = load_config(config_path)
    gate0_config = _gate0_config(config)
    budgets = [int(budget) for budget in gate0_config["budget_grid"]]
    output_dir.mkdir(parents=True, exist_ok=True)
    epsilon_rows, tercile_bounds = build_epsilon_manifest(config, output_dir)
    phase_a_results = [
        phase_a_instance(instance_id=instance_id, config=config, gate0_config=gate0_config)
        for instance_id in config["instance_ids"]
    ]
    phase_a_summary = summarize_phase_a(phase_a_results, budgets)
    generalizes = any(row["majority"] for row in phase_a_summary.values())
    result: dict[str, Any] = {
        "config_path": str(config_path),
        "model_scope": "Oracle analytic control; B shots per candidate per scale; Raw costs B and ZNE 3B, before any training cost.",
        "decision_rule": "strict optimum; every exact tie is a failure",
        "instance_ids": list(config["instance_ids"]),
        "epsilon_manifest_written_before_outcomes": True,
        "epsilon_rows": epsilon_rows,
        "tercile_bounds": tercile_bounds,
        "phase_a_summary": phase_a_summary,
        "phase_a_instances": [
            {key:value for key,value in item.items() if key not in {'primitive_data','input_config'}}
            for item in phase_a_results
        ],
        "phase_b_status": "not_run_fail_fast_phase_a_no_majority" if not generalizes else "completed",
    }
    for item in phase_a_results:
        write_primitive_evidence(item['primitive_data'],output_dir/'primitives',item['instance_id'])
    if generalizes:
        empirical_rows = []
        for item in phase_a_results:
            empirical_rows.extend(
                empirical_instance(instance_result=item, config=config, gate0_config=gate0_config, sample_archive_dir=output_dir/"samples")
            )
        result["phase_b_rows"] = empirical_rows
        result["phase_b"] = aggregate_empirical(
            empirical_rows,
            phase_a_results,
            epsilon_rows,
            budgets,
        )
    write_outputs(result, output_dir)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)
    result = run(args.config, args.output_dir)
    print("R1 FULL COMPLETE")
    print(f"phase_b_status={result['phase_b_status']}")
    for budget, row in result["phase_a_summary"].items():
        print(
            f"phaseA budget={budget} DA_beats_Raw={row['DA_beats_Raw_count']}/"
            f"{row['n_instances']} majority={row['majority']} rho_mean={_fmt(row['rho_mean'])}"
        )
    if result["phase_b_status"] == "completed":
        for budget, row in result["phase_b"]["aggregate_by_budget"].items():
            fr = row["failure_rates"]
            print(
                f"phaseB budget={budget} fail_Raw={_fmt(fr['Raw'])} "
                f"fail_DA={_fmt(fr['DA_selected'])} "
                f"rel_reduction={_fmt(row['relative_reduction_DA_vs_Raw'])}"
            )
    print(f"wrote={args.output_dir / 'r1_full_result.json'}")
    print(f"wrote={args.output_dir / 'r1_full_result.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
