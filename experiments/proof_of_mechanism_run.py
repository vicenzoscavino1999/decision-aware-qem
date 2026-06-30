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
from daqem.candidates import (
    build_candidate_landscape_for_graph,
    graph_seed_for_instance,
    maxcut_values_for_graph,
)
from daqem.cdr import fit_linear_cdr
from daqem.dynamic import epsilon_opt_from_ideal_values
from daqem.gap_kernel import nearest_psd
from daqem.noise import depolarizing_noise_model
from daqem.pec import circuit_gamma
from daqem.qaoa import default_angles, maxcut_graph, qaoa_maxcut_circuit
from daqem.qem_methods import accuracy_zne_coeffs
from daqem.risk import gri_risk
from daqem.rng import make_rng


CONFIG_PATH = REPO_ROOT / "reproducibility" / "config" / "proof_of_mechanism.yaml"
OUTPUT_DIR = REPO_ROOT / "results" / "proof_of_mechanism"
METHODS = ("Raw", "Accuracy-ZNE", "Decision-ZNE", "CDR", "PEC")


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


def _graph(instance_id: str, config: dict):
    cell = config["cell"]
    return maxcut_graph(
        num_qubits=int(cell["num_qubits"]),
        degree=int(cell["degree"]),
        seed=graph_seed_for_instance(instance_id),
    )


def _landscape(instance_id: str, graph, config: dict):
    cell = config["cell"]
    return build_candidate_landscape_for_graph(
        instance_id,
        graph,
        candidate_count=int(cell["candidate_count"]),
        depth=int(cell["depth"]),
        local_radius=float(cell["local_radius"]),
        search_radius=float(cell["search_radius"]),
        search_count=int(cell["search_count"]),
    )


def select_instances(config: dict) -> list[dict[str, Any]]:
    rows = []
    for instance_id in config["instance_selection"]["pool_ids"]:
        graph = _graph(instance_id, config)
        landscape = _landscape(instance_id, graph, config)
        epsilon = epsilon_opt_from_ideal_values(
            landscape.ideal_values,
            quantile=float(config["instance_selection"]["epsilon_opt_quantile"]),
        )
        rows.append(
            {
                "instance_id": instance_id,
                "graph_seed": int(graph_seed_for_instance(instance_id)),
                "epsilon_opt": float(epsilon),
                "x_star": int(landscape.x_star),
            }
        )
    min_eps = float(config["instance_selection"]["min_epsilon_opt"])
    eligible = [row for row in rows if float(row["epsilon_opt"]) >= min_eps]
    eligible = sorted(eligible, key=lambda row: (float(row["epsilon_opt"]), str(row["instance_id"])))
    selected = eligible[: int(config["instance_selection"]["selected_count"])]
    if len(selected) < int(config["instance_selection"]["selected_count"]):
        raise RuntimeError("not enough outcome-blind eligible instances for proof-of-mechanism")
    selected_ids = {row["instance_id"] for row in selected}
    for row in rows:
        row["selected"] = row["instance_id"] in selected_ids
    return rows


def _probability_arrays(instance_id: str, graph, landscape, config: dict):
    scales = np.asarray(config["noise"]["zne_scales"], dtype=float)
    depth = int(config["cell"]["depth"])
    values_by_state = -maxcut_values_for_graph(graph)
    state_count = values_by_state.size
    noisy_probs = np.empty((len(scales), landscape.angles.shape[0], state_count), dtype=float)
    for scale_idx, scale in enumerate(scales):
        simulator = AerSimulator(
            method="density_matrix",
            noise_model=depolarizing_noise_model(
                p1=min(float(config["noise"]["p1"]) * float(scale), 0.95),
                p2=min(float(config["noise"]["p2"]) * float(scale), 0.95),
            ),
        )
        circuits = []
        for angles in landscape.angles:
            circuit = qaoa_maxcut_circuit(
                graph,
                depth=depth,
                gammas=angles[:depth],
                betas=angles[depth:],
                measure=False,
            )
            circuit.save_probabilities_dict()
            circuits.append(circuit)
        transpiled = transpile(circuits, simulator, seed_transpiler=260616 + scale_idx)
        result = simulator.run(transpiled).result()
        for candidate_idx in range(landscape.angles.shape[0]):
            arr = np.zeros(state_count, dtype=float)
            for key, probability in result.data(candidate_idx)["probabilities"].items():
                arr[a3._state_index(key)] = float(probability)
            noisy_probs[scale_idx, candidate_idx] = arr / float(np.sum(arr))
    ideal_sim = AerSimulator(method="density_matrix")
    ideal_circuits = []
    for angles in landscape.angles:
        circuit = qaoa_maxcut_circuit(
            graph,
            depth=depth,
            gammas=angles[:depth],
            betas=angles[depth:],
            measure=False,
        )
        circuit.save_probabilities_dict()
        ideal_circuits.append(circuit)
    ideal_result = ideal_sim.run(
        transpile(ideal_circuits, ideal_sim, seed_transpiler=260616)
    ).result()
    ideal_probs = np.empty((landscape.angles.shape[0], state_count), dtype=float)
    for candidate_idx in range(landscape.angles.shape[0]):
        arr = np.zeros(state_count, dtype=float)
        for key, probability in ideal_result.data(candidate_idx)["probabilities"].items():
            arr[a3._state_index(key)] = float(probability)
        ideal_probs[candidate_idx] = arr / float(np.sum(arr))
    return noisy_probs, ideal_probs, values_by_state


def _moments_from_probs(probs: np.ndarray, values_by_state: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    means = np.einsum("...s,s->...", probs, values_by_state)
    second = np.einsum("...s,s->...", probs, values_by_state * values_by_state)
    variances = np.maximum(second - means * means, 0.0)
    return means, variances


def _method_values(coeffs: np.ndarray, primitive_values: np.ndarray) -> np.ndarray:
    return np.einsum("s,sk->k", np.asarray(coeffs, dtype=float), np.asarray(primitive_values, dtype=float))


def _actual_gap_covariance(coeffs: np.ndarray, variances: np.ndarray, shots_by_scale: np.ndarray, x_star: int):
    candidate_count = variances.shape[1]
    gap_map = a3._gap_map(coeffs, candidate_count, int(x_star))
    actual_diag = (variances / shots_by_scale[:, None]).reshape(-1)
    return nearest_psd((gap_map * actual_diag) @ gap_map.T)


def _candidate_variance(coeffs: np.ndarray, variances: np.ndarray, shots_by_scale: np.ndarray) -> np.ndarray:
    return np.einsum(
        "s,sk->k",
        np.asarray(coeffs, dtype=float) ** 2,
        np.asarray(variances, dtype=float) / shots_by_scale[:, None],
    )


def _signed_budget_exponent(mu: np.ndarray, covariance: np.ndarray) -> float:
    mu_arr = np.asarray(mu, dtype=float)
    if np.any(mu_arr <= 0.0):
        return 0.0
    diag = np.diag(np.asarray(covariance, dtype=float))
    terms = [np.inf if var <= 0 else margin * margin / (2.0 * var) for margin, var in zip(mu_arr, diag, strict=True)]
    return float(np.min(terms))


def instance_analytics(instance_id: str, config: dict) -> dict[str, Any]:
    graph = _graph(instance_id, config)
    landscape = _landscape(instance_id, graph, config)
    noisy_probs, ideal_probs, values_by_state = _probability_arrays(instance_id, graph, landscape, config)
    noisy_means, noisy_vars = _moments_from_probs(noisy_probs, values_by_state)
    ideal_means, ideal_vars = _moments_from_probs(ideal_probs, values_by_state)
    if np.max(np.abs(ideal_means - landscape.ideal_values)) > 1e-6:
        raise ValueError(f"ideal probability means mismatch for {instance_id}")
    x_star = int(landscape.x_star)
    candidate_count = len(landscape.ideal_values)
    competitors = [idx for idx in range(candidate_count) if idx != x_star]
    scales = np.asarray(config["noise"]["zne_scales"], dtype=float)
    raw_coeffs = np.array([1.0, 0.0, 0.0], dtype=float)
    acc_coeffs = accuracy_zne_coeffs(scales, p=int(config["noise"]["zne_order"]))
    gate0_like = {
        "zne_lambdas": list(scales),
        "zne_order": int(config["noise"]["zne_order"]),
        "decision_zne_mu_floor": 1e-6,
    }
    dec_coeffs = a3.method_coefficients_from_true_cdev(
        primitive_variance_unit=noisy_vars,
        ideal_values=landscape.ideal_values,
        x_star=x_star,
        gate0_config=gate0_like,
    )["Decision-ZNE"]
    cdr_fit = fit_linear_cdr(noisy_means[0], landscape.ideal_values)
    gamma = circuit_gamma(
        graph,
        depth=int(config["cell"]["depth"]),
        gammas=default_angles(int(config["cell"]["depth"]))[0],
        betas=default_angles(int(config["cell"]["depth"]))[1],
        p1=float(config["noise"]["p1"]),
        p2=float(config["noise"]["p2"]),
    )
    budgets = [int(budget) for budget in config["budget_grid"]]
    analytic_by_budget = {}
    for budget in budgets:
        per_scale = np.full(3, float(budget) / 3.0, dtype=float)
        raw_shots = np.array([float(budget), 1.0, 1.0], dtype=float)
        method_specs = {
            "Raw": (raw_coeffs, noisy_means, noisy_vars, raw_shots),
            "Accuracy-ZNE": (acc_coeffs, noisy_means, noisy_vars, per_scale),
            "Decision-ZNE": (dec_coeffs, noisy_means, noisy_vars, per_scale),
        }
        budget_data = {}
        for method, (coeffs, means, variances, shots_by_scale) in method_specs.items():
            values = _method_values(coeffs, means)
            mu = values[competitors] - float(values[x_star])
            cov = _actual_gap_covariance(coeffs, variances, shots_by_scale, x_star)
            cand_var = _candidate_variance(coeffs, variances, shots_by_scale)
            mse = float(np.mean((values - landscape.ideal_values) ** 2 + cand_var))
            budget_data[method] = {
                "mean_values": values,
                "GRI": float(gri_risk(mu, cov, B=1.0)),
                "I_hat": _signed_budget_exponent(mu, cov),
                "MSE_expected": mse,
                "covariance": cov,
            }
        cdr_values = cdr_fit.a * noisy_means[0] + cdr_fit.b
        raw_cov = budget_data["Raw"]["covariance"]
        cdr_mu = cdr_values[competitors] - float(cdr_values[x_star])
        cdr_cov = nearest_psd(cdr_fit.a * cdr_fit.a * raw_cov)
        cdr_var = (cdr_fit.a * cdr_fit.a) * noisy_vars[0] / float(budget)
        budget_data["CDR"] = {
            "mean_values": cdr_values,
            "GRI": float(gri_risk(cdr_mu, cdr_cov, B=1.0)),
            "I_hat": _signed_budget_exponent(cdr_mu, cdr_cov),
            "MSE_expected": float(np.mean((cdr_values - landscape.ideal_values) ** 2 + cdr_var)),
            "covariance": cdr_cov,
        }
        pec_eff = max(1, int(np.floor(float(budget) / (gamma * gamma))))
        pec_mu = landscape.ideal_values[competitors] - float(landscape.ideal_values[x_star])
        pec_cov = _actual_gap_covariance(
            np.array([1.0]),
            ideal_vars[None, :],
            np.array([float(pec_eff)]),
            x_star,
        )
        budget_data["PEC"] = {
            "mean_values": np.asarray(landscape.ideal_values, dtype=float),
            "GRI": float(gri_risk(pec_mu, pec_cov, B=1.0)),
            "I_hat": _signed_budget_exponent(pec_mu, pec_cov),
            "MSE_expected": float(np.mean(ideal_vars / float(pec_eff))),
            "covariance": pec_cov,
            "effective_shots": pec_eff,
        }
        analytic_by_budget[str(budget)] = budget_data
    return {
        "instance_id": instance_id,
        "graph_seed": int(graph_seed_for_instance(instance_id)),
        "epsilon_opt": float(epsilon_opt_from_ideal_values(
            landscape.ideal_values,
            quantile=float(config["instance_selection"]["epsilon_opt_quantile"]),
        )),
        "x_star": x_star,
        "gamma": float(gamma),
        "gamma_squared": float(gamma * gamma),
        "cdr_fit": {"a": float(cdr_fit.a), "b": float(cdr_fit.b)},
        "landscape": landscape,
        "noisy_probs": noisy_probs,
        "ideal_probs": ideal_probs,
        "values_by_state": values_by_state,
        "noisy_means": noisy_means,
        "noisy_vars": noisy_vars,
        "ideal_vars": ideal_vars,
        "coefficients": {
            "Raw": raw_coeffs,
            "Accuracy-ZNE": acc_coeffs,
            "Decision-ZNE": dec_coeffs,
        },
        "analytic_by_budget": analytic_by_budget,
    }


def _sample_expectation(rng: np.random.Generator, probs: np.ndarray, values_by_state: np.ndarray, shots: int) -> float:
    counts = rng.multinomial(int(shots), probs)
    return float(np.dot(counts, values_by_state) / float(shots))


def empirical_observations(instances: list[dict[str, Any]], config: dict) -> list[dict[str, Any]]:
    observations = []
    budgets = [int(budget) for budget in config["budget_grid"]]
    replicates = int(config["replicates"])
    for item in instances:
        instance_id = item["instance_id"]
        x_star = int(item["x_star"])
        for budget in budgets:
            for replicate in range(replicates):
                order_rng = make_rng(
                    instance_id=instance_id,
                    method="proof_of_mechanism",
                    budget=budget,
                    replicate_id=replicate,
                    stream="method_order",
                )
                method_order = list(METHODS)
                order_rng.shuffle(method_order)
                raw_rng = make_rng(
                    instance_id=instance_id,
                    method="Raw",
                    budget=budget,
                    replicate_id=replicate,
                    stream="proof_multinomial",
                )
                raw_estimates = np.array(
                    [
                        _sample_expectation(raw_rng, probs, item["values_by_state"], budget)
                        for probs in item["noisy_probs"][0]
                    ],
                    dtype=float,
                )
                per_scale_shots = int(budget // 3)
                zne_rng = make_rng(
                    instance_id=instance_id,
                    method="ZNE",
                    budget=budget,
                    replicate_id=replicate,
                    stream="proof_multinomial",
                )
                primitive_estimates = np.empty(item["noisy_probs"].shape[:2], dtype=float)
                for scale_idx in range(item["noisy_probs"].shape[0]):
                    for candidate_idx in range(item["noisy_probs"].shape[1]):
                        primitive_estimates[scale_idx, candidate_idx] = _sample_expectation(
                            zne_rng,
                            item["noisy_probs"][scale_idx, candidate_idx],
                            item["values_by_state"],
                            per_scale_shots,
                        )
                pec_eff = max(1, int(np.floor(float(budget) / item["gamma_squared"])))
                pec_rng = make_rng(
                    instance_id=instance_id,
                    method="PEC",
                    budget=budget,
                    replicate_id=replicate,
                    stream="proof_effective_multinomial",
                )
                pec_estimates = np.array(
                    [
                        _sample_expectation(pec_rng, probs, item["values_by_state"], pec_eff)
                        for probs in item["ideal_probs"]
                    ],
                    dtype=float,
                )
                estimates = {
                    "Raw": raw_estimates,
                    "Accuracy-ZNE": _method_values(item["coefficients"]["Accuracy-ZNE"], primitive_estimates),
                    "Decision-ZNE": _method_values(item["coefficients"]["Decision-ZNE"], primitive_estimates),
                    "CDR": item["cdr_fit"]["a"] * raw_estimates + item["cdr_fit"]["b"],
                    "PEC": pec_estimates,
                }
                for method in METHODS:
                    est = estimates[method]
                    observations.append(
                        {
                            "instance_id": instance_id,
                            "budget": budget,
                            "replicate": replicate,
                            "method": method,
                            "decision_failure": int(np.argmin(est) != x_star),
                            "mse": float(np.mean((est - item["landscape"].ideal_values) ** 2)),
                            "method_order": method_order,
                        }
                    )
    return observations


def _bootstrap_ci(values: np.ndarray, *, reps: int, alpha: float, rng: np.random.Generator) -> list[float]:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return [float("nan"), float("nan")]
    stats = np.empty(int(reps), dtype=float)
    for idx in range(int(reps)):
        sample = arr[rng.integers(0, arr.size, size=arr.size)]
        stats[idx] = float(np.mean(sample))
    lo, hi = np.quantile(stats, [float(alpha) / 2.0, 1.0 - float(alpha) / 2.0])
    return [float(lo), float(hi)]


def aggregate(instances: list[dict[str, Any]], observations: list[dict[str, Any]], config: dict) -> dict[str, Any]:
    budgets = [int(budget) for budget in config["budget_grid"]]
    boot_rng = make_rng(
        instance_id="proof_of_mechanism",
        method="bootstrap",
        budget=0,
        replicate_id=0,
        stream="ci",
    )
    rows = []
    for budget in budgets:
        for method in METHODS:
            obs = [row for row in observations if row["budget"] == budget and row["method"] == method]
            failures = np.asarray([row["decision_failure"] for row in obs], dtype=float)
            mses = np.asarray([row["mse"] for row in obs], dtype=float)
            analytic_gri = np.asarray(
                [item["analytic_by_budget"][str(budget)][method]["GRI"] for item in instances],
                dtype=float,
            )
            analytic_i = np.asarray(
                [item["analytic_by_budget"][str(budget)][method]["I_hat"] for item in instances],
                dtype=float,
            )
            rows.append(
                {
                    "budget": budget,
                    "method": method,
                    "MSE_mean": float(np.mean(mses)),
                    "MSE_ci": _bootstrap_ci(
                        mses,
                        reps=int(config["bootstrap_repetitions"]),
                        alpha=float(config["ci_alpha"]),
                        rng=boot_rng,
                    ),
                    "R_empirical": float(np.mean(failures)),
                    "R_ci": _bootstrap_ci(
                        failures,
                        reps=int(config["bootstrap_repetitions"]),
                        alpha=float(config["ci_alpha"]),
                        rng=boot_rng,
                    ),
                    "GRI_mean": float(np.mean(analytic_gri)),
                    "I_hat_mean": float(np.mean(analytic_i)),
                }
            )
    coexistence = []
    cdr_control = []
    gap_kernel = []
    for budget in budgets:
        by_method = {row["method"]: row for row in rows if row["budget"] == budget}
        pec_coexist = (
            by_method["PEC"]["MSE_mean"] < by_method["Raw"]["MSE_mean"]
            and by_method["PEC"]["R_empirical"] > by_method["Raw"]["R_empirical"]
        )
        if pec_coexist:
            coexistence.append(budget)
        cdr_flat = abs(by_method["CDR"]["R_empirical"] - by_method["Raw"]["R_empirical"]) <= float(
            config["death_criteria"]["cdr_decision_flat_tolerance"]
        )
        cdr_mse_down = by_method["CDR"]["MSE_mean"] < by_method["Raw"]["MSE_mean"]
        if cdr_mse_down and cdr_flat:
            cdr_control.append(budget)
        gap_explains = (
            by_method["PEC"]["GRI_mean"] > by_method["Raw"]["GRI_mean"]
            and by_method["PEC"]["I_hat_mean"] < by_method["Raw"]["I_hat_mean"]
        )
        if gap_explains:
            gap_kernel.append(budget)
    epsilon_values = np.asarray([item["epsilon_opt"] for item in instances], dtype=float)
    death = {
        "margins_nondegenerate": bool(
            np.all(epsilon_values >= float(config["death_criteria"]["margin_nondegenerate_min_epsilon"]))
        ),
        "pec_effect_persists_matched_shot": bool(coexistence),
        "randomized_execution_order": bool(config["randomized_execution_order"]),
        "gap_kernel_explains": bool(set(coexistence).issubset(set(gap_kernel)) and bool(coexistence)),
        "not_affine_control_only": bool(cdr_control),
    }
    return {
        "table": rows,
        "coexistence_budgets_PEC": coexistence,
        "cdr_control_budgets": cdr_control,
        "gap_kernel_explained_budgets": gap_kernel,
        "death_criteria": death,
    }


def write_outputs(result: dict[str, Any], output_dir: Path = OUTPUT_DIR) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "result.json"
    md_path = output_dir / "result.md"
    json_path.write_text(json.dumps(_jsonable(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Proof Of Mechanism Result",
        "",
        "No confirmatory C-ids are used. Instances are selected by ideal epsilon only.",
        "",
        "## Selected Instances",
        "",
        "| instance | epsilon_opt | graph_seed |",
        "|:---|---:|---:|",
    ]
    for row in result["selected_instances"]:
        lines.append(f"| {row['instance_id']} | {row['epsilon_opt']:.12g} | {row['graph_seed']} |")
    lines.extend(
        [
            "",
            "## Aggregate Table",
            "",
            "| budget | method | MSE | MSE CI | R empirical | R CI | GRI | I_hat |",
            "|---:|:---|---:|:---|---:|:---|---:|---:|",
        ]
    )
    for row in result["aggregate"]["table"]:
        lines.append(
            f"| {row['budget']} | {row['method']} | {row['MSE_mean']:.12g} | "
            f"[{row['MSE_ci'][0]:.12g}, {row['MSE_ci'][1]:.12g}] | "
            f"{row['R_empirical']:.12g} | [{row['R_ci'][0]:.12g}, {row['R_ci'][1]:.12g}] | "
            f"{row['GRI_mean']:.12g} | {row['I_hat_mean']:.12g} |"
        )
    lines.extend(
        [
            "",
            "## Coexistence And Controls",
            "",
            f"- PEC coexistence budgets: {result['aggregate']['coexistence_budgets_PEC']}",
            f"- CDR affine-control budgets: {result['aggregate']['cdr_control_budgets']}",
            f"- gap-kernel explained budgets: {result['aggregate']['gap_kernel_explained_budgets']}",
            "",
            "## Death Criteria",
            "",
        ]
    )
    for key, value in result["aggregate"]["death_criteria"].items():
        lines.append(f"- {key}: {'PASS' if value else 'FAIL'}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def run(config_path: Path = CONFIG_PATH, output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    config = load_config(config_path)
    selection_rows = select_instances(config)
    selected_ids = [row["instance_id"] for row in selection_rows if row["selected"]]
    instances = [instance_analytics(instance_id, config) for instance_id in selected_ids]
    observations = empirical_observations(instances, config)
    result = {
        "config_path": str(config_path.relative_to(REPO_ROOT)),
        "selected_instances": [row for row in selection_rows if row["selected"]],
        "all_pool_instances": selection_rows,
        "aggregate": aggregate(instances, observations, config),
        "instance_gamma_squared_range": [
            float(np.min([item["gamma_squared"] for item in instances])),
            float(np.max([item["gamma_squared"] for item in instances])),
        ],
    }
    write_outputs(result, output_dir)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)
    result = run(args.config, args.output_dir)
    print("PROOF OF MECHANISM COMPLETE")
    print(f"selected_instances={[row['instance_id'] for row in result['selected_instances']]}")
    print(f"PEC_coexistence_budgets={result['aggregate']['coexistence_budgets_PEC']}")
    print(f"CDR_control_budgets={result['aggregate']['cdr_control_budgets']}")
    print(f"death_criteria={result['aggregate']['death_criteria']}")
    print(f"wrote={OUTPUT_DIR.relative_to(REPO_ROOT) / 'result.json'}")
    print(f"wrote={OUTPUT_DIR.relative_to(REPO_ROOT) / 'result.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
