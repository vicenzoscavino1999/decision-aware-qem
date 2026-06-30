from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from qiskit import transpile
from qiskit_aer import AerSimulator

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from daqem.candidates import (  # noqa: E402
    CONFIRMATORY_E2_INSTANCE_IDS,
    CONFIRMATORY_INSTANCE_IDS,
    PILOT_INSTANCE_IDS,
    assert_pilot_instance,
    landscape_for_instance,
    maxcut_graph_for_instance,
    noiseless_qaoa_maxcut_expectation,
)
from daqem.dynamic import (  # noqa: E402
    DynamicSafeguards,
    epsilon_opt_from_ideal_values,
    generate_candidate_batch,
    lexicographic_argmin,
    success_from_regret,
)
from daqem.noise import (  # noqa: E402
    ONE_QUBIT_DEPOLARIZING,
    TWO_QUBIT_DEPOLARIZING,
    depolarizing_noise_model,
)
from daqem.qaoa import maxcut_value, qaoa_maxcut_circuit  # noqa: E402
from daqem.rng import make_rng  # noqa: E402
from experiments.pilot_power_report import build_power_table  # noqa: E402


CONFIG_PATH = REPO_ROOT / "reproducibility" / "config" / "dynamic_task.yaml"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "results"
CONFIRMATORY_SELECTOR_REL = Path("confirmatory") / "e1_static_selector_table.csv"


def _profile_namespace(profile: str) -> str:
    if str(profile) == "full" or str(profile).startswith("confirmatory_"):
        return "confirmatory"
    return "pilot"


def _instance_namespace(instance_id: str) -> str:
    if str(instance_id) in CONFIRMATORY_INSTANCE_IDS:
        return "confirmatory"
    if str(instance_id) in PILOT_INSTANCE_IDS:
        return "pilot"
    raise ValueError(f"unknown dynamic instance id: {instance_id!r}")


def report_rel(profile: str) -> Path:
    if _profile_namespace(profile) == "confirmatory":
        return Path("confirmatory") / f"e2_dynamic_{profile}.md"
    if str(profile).startswith("dynamic_pilot_"):
        suffix = str(profile).removeprefix("dynamic_pilot_")
        return Path("pilot") / f"dynamic_pilot_{suffix}.md"
    suffix = "smoke" if profile == "smoke" else str(profile)
    return Path("pilot") / f"dynamic_pilot_{suffix}.md"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest().upper()


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _write_json_atomic(path: Path, payload: dict) -> None:
    _write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_dataframe_atomic(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(path)


def _checkpoint_root(output_root: Path, profile: str) -> Path:
    return output_root / _profile_namespace(profile) / str(profile)


def _dynamic_instance_paths(output_root: Path, profile: str, instance_id: str) -> dict[str, Path]:
    root = _checkpoint_root(output_root, profile) / "instances"
    return {
        "results": root / f"{instance_id}_results.csv",
        "trace": root / f"{instance_id}_trace.csv",
        "cost": root / f"{instance_id}_cost.json",
    }


def _checkpoint_path(output_root: Path, profile: str) -> Path:
    return _checkpoint_root(output_root, profile) / "checkpoint.json"


def _load_dynamic_checkpoint(output_root: Path, profile: str) -> dict:
    path = _checkpoint_path(output_root, profile)
    if not path.exists():
        return {"profile": profile, "instances": {}}
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    payload.setdefault("profile", profile)
    payload.setdefault("instances", {})
    return payload


def _dynamic_config_fingerprint(config: dict) -> str:
    excluded = {"_checkpoint_info"}
    stable = {key: value for key, value in config.items() if key not in excluded}
    data = json.dumps(stable, sort_keys=True, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest().upper()


def _completed_dynamic_instance(
    output_root: Path,
    profile: str,
    instance_id: str,
    config_fingerprint: str,
) -> bool:
    checkpoint = _load_dynamic_checkpoint(output_root, profile)
    entry = checkpoint.get("instances", {}).get(str(instance_id), {})
    if entry.get("status") != "complete":
        return False
    if entry.get("config_fingerprint") != config_fingerprint:
        return False
    paths = _dynamic_instance_paths(output_root, profile, instance_id)
    outputs = entry.get("outputs", {})
    for key, path in paths.items():
        if not path.exists() or outputs.get(key) != _sha256_file(path):
            return False
    return True


def load_config(profile: str = "smoke") -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    profiles = raw.get("profiles", {})
    if profile not in profiles:
        raise ValueError(f"unknown dynamic profile: {profile}")
    config = dict(raw.get("defaults", {}))
    config.update(profiles[profile])
    config["profile"] = profile
    config["output_namespace"] = str(config.get("output_namespace", _profile_namespace(profile)))
    for instance_id in config["instance_ids"]:
        if config["output_namespace"] == "pilot":
            assert_pilot_instance(str(instance_id))
        elif config["output_namespace"] == "confirmatory":
            if str(instance_id) not in CONFIRMATORY_E2_INSTANCE_IDS:
                raise ValueError(f"E2 confirmatory ids must be C001..C032; got {instance_id!r}")
        else:
            raise ValueError(f"unknown dynamic output namespace: {config['output_namespace']!r}")
    safeguards = DynamicSafeguards(
        candidate_generation_independent_of_selector=bool(
            config["candidate_generation_independent_of_selector"]
        ),
        same_candidates_for_DA_and_MSE=bool(config["same_candidates_for_DA_and_MSE"]),
        same_initial_points_for_DA_and_MSE=bool(
            config["same_initial_points_for_DA_and_MSE"]
        ),
        same_budget_grid_for_DA_and_MSE=bool(config["same_budget_grid_for_DA_and_MSE"]),
        same_stopping_rule_for_DA_and_MSE=bool(
            config["same_stopping_rule_for_DA_and_MSE"]
        ),
        selector_does_not_generate_candidates=bool(
            config["selector_does_not_generate_candidates"]
        ),
    )
    safeguards.validate()
    budgets = sorted(int(value) for value in config["budget_grid"])
    if int(config["B_max"]) != max(budgets):
        raise ValueError("B_max must equal max(budget_grid) for nested prefixes")
    config["budget_grid"] = budgets
    if "candidate_radius_grid" in config:
        radius_grid = [float(value) for value in config["candidate_radius_grid"]]
        if not radius_grid or any(value <= 0.0 for value in radius_grid):
            raise ValueError("candidate_radius_grid must contain positive values")
        config["candidate_radius_grid"] = radius_grid
    if "epsilon_quantile_grid" in config:
        eps_grid = [float(value) for value in config["epsilon_quantile_grid"]]
        if not eps_grid or any(value <= 0.0 or value >= 1.0 for value in eps_grid):
            raise ValueError("epsilon_quantile_grid values must be in (0, 1)")
        config["epsilon_quantile_grid"] = eps_grid
    return config


def _confirmatory_selector_table_path(output_root: Path) -> Path:
    return output_root / CONFIRMATORY_SELECTOR_REL


def _a3_frozen_prediction_path(output_root: Path, instance_id: str) -> Path:
    namespace = _instance_namespace(instance_id)
    return output_root / namespace / "a3_frozen_prediction" / f"{instance_id}.npz"


def _static_selector_map(output_root: Path, instance_id: str, budgets: list[int]) -> dict[int, dict[str, str]]:
    if _instance_namespace(instance_id) == "confirmatory":
        selector_path = _confirmatory_selector_table_path(output_root)
        if not selector_path.exists():
            raise FileNotFoundError(f"missing confirmatory E1 selector table: {selector_path}")
        table = pd.read_csv(selector_path)
        required = {"cell", "budget", "MSE_selected_method", "DA_selected_method"}
        missing = required - set(table.columns)
        if missing:
            raise ValueError(f"confirmatory selector table missing columns: {sorted(missing)}")
    else:
        table = build_power_table(output_root)
    rows = table[table["cell"] == instance_id].copy()
    available = sorted(int(value) for value in rows["budget"].unique())
    if not available:
        raise ValueError(f"missing static selector rows for {instance_id}")
    selector_map: dict[int, dict[str, str]] = {}
    for budget in budgets:
        hit = rows[rows["budget"] == int(budget)]
        source_budget = int(budget)
        if len(hit) != 1:
            source_budget = min(available, key=lambda value: (abs(value - int(budget)), value))
            hit = rows[rows["budget"] == source_budget]
        if len(hit) != 1:
            raise ValueError(
                f"missing static selector row for {instance_id} budget={budget} "
                f"(source_budget={source_budget})"
            )
        row = hit.iloc[0]
        selector_map[int(budget)] = {
            "MSE": str(row["MSE_selected_method"]),
            "DA": str(row["DA_selected_method"]),
            "source_budget": str(source_budget),
        }
    return selector_map


def _method_coefficients(output_root: Path, instance_id: str, method_menu: list[str]) -> dict[str, np.ndarray]:
    frozen_path = _a3_frozen_prediction_path(output_root, instance_id)
    if not frozen_path.exists():
        raise FileNotFoundError(f"missing A3 frozen prediction: {frozen_path}")
    frozen = np.load(frozen_path, allow_pickle=False)
    names = [str(name) for name in frozen["method_names"]]
    coeffs = np.asarray(frozen["method_coefficients"], dtype=float)
    by_method = {name: coeffs[idx].copy() for idx, name in enumerate(names)}
    missing = [name for name in method_menu if name not in by_method]
    if missing:
        raise ValueError(f"A3 frozen prediction missing method coefficients: {missing}")
    return {name: by_method[name] for name in method_menu}


def _prefix_objective_stats(memory: list[str], graph, budgets: list[int]) -> tuple[np.ndarray, np.ndarray]:
    values = -np.fromiter((maxcut_value(bitstring, graph) for bitstring in memory), dtype=float)
    cumulative = np.cumsum(values)
    means = []
    mean_variances = []
    for budget in budgets:
        prefix = values[: int(budget)]
        means.append(float(cumulative[int(budget) - 1] / float(budget)))
        shot_variance = float(np.var(prefix, ddof=1)) if int(budget) > 1 else 0.0
        mean_variances.append(shot_variance / float(budget))
    return np.asarray(means, dtype=float), np.asarray(mean_variances, dtype=float)


def _evaluate_candidate_batch(
    *,
    instance_id: str,
    trajectory_id: int,
    round_id: int,
    graph,
    depth: int,
    angles: np.ndarray,
    scales: np.ndarray,
    budgets: list[int],
    b_max: int,
) -> tuple[np.ndarray, np.ndarray, dict[str, int]]:
    primitive_means = np.empty((len(scales), len(angles), len(budgets)), dtype=float)
    primitive_mean_vars = np.empty_like(primitive_means)
    aer_runs = 0
    circuits_run = 0
    for scale_idx, scale in enumerate(scales):
        p1 = min(float(ONE_QUBIT_DEPOLARIZING) * float(scale), 0.95)
        p2 = min(float(TWO_QUBIT_DEPOLARIZING) * float(scale), 0.95)
        noise_model = depolarizing_noise_model(p1=p1, p2=p2)
        circuits = [
            qaoa_maxcut_circuit(
                graph,
                depth=depth,
                gammas=row[:depth],
                betas=row[depth:],
                measure=True,
            )
            for row in angles
        ]
        rng = make_rng(
            instance_id=instance_id,
            method=f"dynamic_scale_{scale:g}",
            budget=int(b_max),
            replicate_id=int(trajectory_id * 10_000 + round_id),
            stream=f"batch_scale_{scale_idx}",
        )
        seed = int(rng.integers(1, 2**31 - 1))
        simulator = AerSimulator(noise_model=noise_model, seed_simulator=seed)
        transpiled = transpile(circuits, simulator, seed_transpiler=seed)
        result = simulator.run(transpiled, shots=int(b_max), memory=True).result()
        aer_runs += 1
        circuits_run += len(circuits)
        for candidate_idx in range(len(circuits)):
            memory = result.get_memory(candidate_idx)
            means, mean_vars = _prefix_objective_stats(memory, graph, budgets)
            primitive_means[scale_idx, candidate_idx, :] = means
            primitive_mean_vars[scale_idx, candidate_idx, :] = mean_vars
    cost = {
        "aer_runs": aer_runs,
        "circuits": circuits_run,
        "shots": circuits_run * int(b_max),
    }
    return primitive_means, primitive_mean_vars, cost


def _method_estimates(
    primitive_means: np.ndarray,
    primitive_mean_vars: np.ndarray,
    coeffs_by_method: dict[str, np.ndarray],
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    estimates: dict[str, np.ndarray] = {}
    variances: dict[str, np.ndarray] = {}
    for method, coeffs in coeffs_by_method.items():
        c = np.asarray(coeffs, dtype=float)
        estimates[method] = np.einsum("s,skb->kb", c, primitive_means)
        variances[method] = np.einsum("s,skb->kb", c**2, primitive_mean_vars)
    return estimates, variances


def _active_scale_count(coefficients: np.ndarray) -> int:
    return int(np.count_nonzero(np.abs(np.asarray(coefficients, dtype=float)) > 1e-12))


def _candidate_ideal_values(graph, depth: int, angles: np.ndarray) -> np.ndarray:
    return -np.array(
        [
            noiseless_qaoa_maxcut_expectation(graph, depth=depth, angles=row)
            for row in angles
        ],
        dtype=float,
    )


def _trajectory_initial_angles(landscape, instance_id: str, trajectory_id: int) -> np.ndarray:
    rng = make_rng(
        instance_id=instance_id,
        method="dynamic_initial_point",
        budget=0,
        replicate_id=int(trajectory_id),
        stream="shared_initial",
    )
    start = max(1, len(landscape.angles) // 3)
    pool = np.arange(start, len(landscape.angles), dtype=int)
    if pool.size == 0:
        pool = np.arange(len(landscape.angles), dtype=int)
    idx = int(pool[int(rng.integers(0, pool.size))])
    return np.asarray(landscape.angles[idx], dtype=float).copy()


def _run_instance(
    *,
    output_root: Path,
    instance_id: str,
    config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int | float]]:
    budgets = [int(value) for value in config["budget_grid"]]
    b_max = int(config["B_max"])
    depth = int(config["depth"])
    scales = np.asarray(config["zne_lambdas"], dtype=float)
    method_menu = [str(value) for value in config["method_menu_core"]]
    selector_map = _static_selector_map(output_root, instance_id, budgets)
    coeffs_by_method = _method_coefficients(output_root, instance_id, method_menu)
    graph = maxcut_graph_for_instance(
        instance_id,
        num_qubits=int(config["qubits"]),
        degree=int(config["graph_degree"]),
    )
    landscape = landscape_for_instance(
        instance_id,
        candidate_count=int(config["initial_landscape_count"]),
        depth=depth,
        num_qubits=int(config["qubits"]),
        graph_degree=int(config["graph_degree"]),
        local_radius=float(config["local_radius"]),
        search_radius=float(config["search_radius"]),
        search_count=int(config["search_count"]),
    )
    epsilon_opt = epsilon_opt_from_ideal_values(
        landscape.ideal_values,
        quantile=float(config["epsilon_quantile"]),
    )
    reference_best_ideal = float(np.min(landscape.ideal_values))
    active_scales_by_method = {
        method: _active_scale_count(coeffs)
        for method, coeffs in coeffs_by_method.items()
    }

    result_rows = []
    trace_rows = []
    total_cost = {"aer_runs": 0, "circuits": 0, "shots": 0}
    for trajectory_id in range(int(config["trajectories"])):
        proposal = _trajectory_initial_angles(landscape, instance_id, trajectory_id)
        trajectory_ideal_values: list[float] = []
        incumbent = {
            budget: {
                "MSE": {"score": np.inf, "ideal": np.inf, "method": selector_map[budget]["MSE"]},
                "DA": {"score": np.inf, "ideal": np.inf, "method": selector_map[budget]["DA"]},
            }
            for budget in budgets
        }
        for round_id in range(int(config["max_rounds"])):
            rng = make_rng(
                instance_id=instance_id,
                method="dynamic_candidates",
                budget=b_max,
                replicate_id=int(trajectory_id),
                stream=f"round_{round_id}",
            )
            batch_angles = generate_candidate_batch(
                proposal,
                candidates_per_round=int(config["candidates_per_round"]),
                radius=float(config["candidate_radius"]),
                rng=rng,
            )
            ideal_values = _candidate_ideal_values(graph, depth, batch_angles)
            trajectory_ideal_values.extend(float(value) for value in ideal_values)
            primitive_means, primitive_mean_vars, cost = _evaluate_candidate_batch(
                instance_id=instance_id,
                trajectory_id=trajectory_id,
                round_id=round_id,
                graph=graph,
                depth=depth,
                angles=batch_angles,
                scales=scales,
                budgets=budgets,
                b_max=b_max,
            )
            for key in total_cost:
                total_cost[key] += int(cost[key])
            estimates, _variances = _method_estimates(
                primitive_means,
                primitive_mean_vars,
                coeffs_by_method,
            )

            bmax_idx = budgets.index(b_max)
            reference_idx = lexicographic_argmin(estimates["Raw"][:, bmax_idx])
            proposal = batch_angles[reference_idx].copy()

            for budget_idx, budget in enumerate(budgets):
                mse_method = selector_map[budget]["MSE"]
                mse_idx = lexicographic_argmin(estimates[mse_method][:, budget_idx])
                mse_score = float(estimates[mse_method][mse_idx, budget_idx])
                if mse_score < float(incumbent[budget]["MSE"]["score"]):
                    incumbent[budget]["MSE"] = {
                        "score": mse_score,
                        "ideal": float(ideal_values[mse_idx]),
                        "method": mse_method,
                    }

                da_method = selector_map[budget]["DA"]
                da_scores = estimates[da_method][:, budget_idx]
                da_idx = lexicographic_argmin(da_scores)
                da_score = float(da_scores[da_idx])
                if da_score < float(incumbent[budget]["DA"]["score"]):
                    incumbent[budget]["DA"] = {
                        "score": da_score,
                        "ideal": float(ideal_values[da_idx]),
                        "method": da_method,
                    }

                if trajectory_id == 0:
                    trace_rows.append(
                        {
                            "instance": instance_id,
                            "trajectory": trajectory_id,
                            "round": round_id,
                            "budget": budget,
                            "reference_candidate": int(reference_idx),
                            "MSE_method": mse_method,
                            "MSE_candidate": int(mse_idx),
                            "MSE_score": mse_score,
                            "DA_method": da_method,
                            "DA_candidate": int(da_idx),
                            "DA_score": da_score,
                        "round_best_ideal": float(np.min(ideal_values)),
                    }
                )

        best_seen_ideal = float(np.min(np.asarray(trajectory_ideal_values, dtype=float)))
        for budget in budgets:
            for selector in ("DA", "MSE"):
                state = incumbent[budget][selector]
                regret_decision = max(float(state["ideal"]) - best_seen_ideal, 0.0)
                regret_global = max(float(state["ideal"]) - reference_best_ideal, 0.0)
                success_decision = success_from_regret(regret_decision, epsilon_opt)
                success_global = success_from_regret(regret_global, epsilon_opt)
                active_scales = active_scales_by_method[str(state["method"])]
                result_rows.append(
                    {
                        "instance": instance_id,
                        "trajectory": trajectory_id,
                        "selector": selector,
                        "budget": budget,
                        "selected_method": state["method"],
                        "selector_source_budget": selector_map[budget]["source_budget"],
                        "final_ideal_value": float(state["ideal"]),
                        "best_seen_ideal_value": best_seen_ideal,
                        "reference_best_ideal_value": reference_best_ideal,
                        "epsilon_opt": epsilon_opt,
                        "regret": regret_decision,
                        "regret_decision": regret_decision,
                        "regret_global": regret_global,
                        "active_scales": active_scales,
                        "cost_per_candidate_shots": active_scales * int(budget),
                        "success": success_decision,
                        "success_decision": success_decision,
                        "success_global": success_global,
                    }
                )

    return pd.DataFrame(result_rows), pd.DataFrame(trace_rows), total_cost


def _read_dynamic_instance_outputs(
    output_root: Path,
    profile: str,
    instance_id: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int | float]]:
    paths = _dynamic_instance_paths(output_root, profile, instance_id)
    results = pd.read_csv(paths["results"])
    trace = pd.read_csv(paths["trace"])
    with paths["cost"].open("r", encoding="utf-8") as f:
        cost = json.load(f)
    for column in ["success", "success_decision", "success_global"]:
        if column in results.columns:
            results[column] = results[column].astype(bool)
    return results, trace, cost


def _write_dynamic_instance_outputs(
    output_root: Path,
    profile: str,
    instance_id: str,
    results: pd.DataFrame,
    trace: pd.DataFrame,
    cost: dict[str, int | float],
    *,
    duration_seconds: float,
    config_fingerprint: str,
) -> None:
    paths = _dynamic_instance_paths(output_root, profile, instance_id)
    _write_dataframe_atomic(paths["results"], results)
    _write_dataframe_atomic(paths["trace"], trace)
    _write_json_atomic(paths["cost"], cost)
    checkpoint = _load_dynamic_checkpoint(output_root, profile)
    checkpoint["profile"] = profile
    checkpoint.setdefault("instances", {})
    checkpoint["instances"][str(instance_id)] = {
        "status": "complete",
        "config_fingerprint": config_fingerprint,
        "duration_seconds": float(duration_seconds),
        "outputs": {key: _sha256_file(path) for key, path in paths.items()},
    }
    _write_json_atomic(_checkpoint_path(output_root, profile), checkpoint)


def _run_checkpointed_instances(
    *,
    output_root: Path,
    config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int | float], dict[str, object]]:
    profile = str(config["profile"])
    config_fingerprint = _dynamic_config_fingerprint(config)
    all_results = []
    all_traces = []
    total_cost = {"aer_runs": 0, "circuits": 0, "shots": 0}
    reused: list[str] = []
    recomputed: list[str] = []

    for instance_id in [str(value) for value in config["instance_ids"]]:
        if _completed_dynamic_instance(
            output_root,
            profile,
            instance_id,
            config_fingerprint,
        ):
            reused.append(instance_id)
            results, trace, cost = _read_dynamic_instance_outputs(
                output_root,
                profile,
                instance_id,
            )
        else:
            instance_start = time.perf_counter()
            results, trace, cost = _run_instance(
                output_root=output_root,
                instance_id=instance_id,
                config=config,
            )
            _write_dynamic_instance_outputs(
                output_root,
                profile,
                instance_id,
                results,
                trace,
                cost,
                duration_seconds=time.perf_counter() - instance_start,
                config_fingerprint=config_fingerprint,
            )
            recomputed.append(instance_id)

        all_results.append(results)
        all_traces.append(trace)
        for key in total_cost:
            total_cost[key] += int(cost[key])

    info = {
        "checkpoint_path": _checkpoint_path(output_root, profile).relative_to(output_root).as_posix(),
        "config_fingerprint": config_fingerprint,
        "reused_instances": reused,
        "recomputed_instances": recomputed,
        "resumed": bool(reused),
    }
    return (
        pd.concat(all_results, ignore_index=True),
        pd.concat(all_traces, ignore_index=True),
        total_cost,
        info,
    )


def _render_report(
    *,
    output_root: Path,
    config: dict,
    summary: pd.DataFrame,
    results: pd.DataFrame,
    trace: pd.DataFrame,
    cost: dict[str, int | float],
    duration_seconds: float,
) -> Path:
    out = output_root / report_rel(str(config["profile"]))
    out.parent.mkdir(parents=True, exist_ok=True)
    regime = _regime_diagnostic(summary)
    primary_discrimination = _metric_discrimination_diagnostic(summary)
    aggregate = _aggregate_summary(results, float(config["P_target"]))
    target_rows, reachable, shot_savings_ratio = _target_crossings(
        aggregate,
        float(config["P_target"]),
    )
    global_summary = _summary_with_success_column(
        results,
        float(config["P_target"]),
        "success_global",
    )
    global_aggregate = _aggregate_with_success_column(
        results,
        float(config["P_target"]),
        "success_global",
    )
    global_target_rows, global_reachable, global_shot_savings_ratio = _target_crossings(
        global_aggregate,
        float(config["P_target"]),
    )
    checkpoint_info = config.get("_checkpoint_info")
    decision_instance_targets = _instance_target_rows(summary, float(config["P_target"]))
    global_instance_targets = _instance_target_rows(global_summary, float(config["P_target"]))
    decision_robustness = _robustness_counts(decision_instance_targets)
    global_robustness = _robustness_counts(global_instance_targets)
    decision_advantage = _advantage_label(aggregate, shot_savings_ratio)
    global_advantage = _advantage_label(global_aggregate, global_shot_savings_ratio)
    title_profile = (
        str(config["profile"])
        .removeprefix("dynamic_pilot_")
        .removeprefix("confirmatory_")
        .replace("_", " ")
        .title()
    )
    title_scope = "Confirmatory" if str(config.get("output_namespace")) == "confirmatory" else "Pilot"
    lines = [
        f"# Dynamic {title_scope} {title_profile}",
        "",
        "Diagnostic only: not canonical, not part of verify/reference, and not frozen.",
        "",
        "## Loop Structure",
        "",
        f"- optimizer: {config['optimizer']}",
        f"- profile: {config['profile']}",
        f"- instances: {config['instance_ids']}",
        f"- trajectories: {config['trajectories']}",
        f"- max_rounds: {config['max_rounds']}",
        f"- candidates_per_round: {config['candidates_per_round']}",
        f"- budget_grid: {config['budget_grid']}",
        f"- B_max: {config['B_max']}",
        f"- proposal_update_reference: {config['proposal_update_reference']}",
        "",
    ]
    if checkpoint_info is not None:
        lines.extend(
            [
                "## Checkpoint/Resume",
                "",
                f"- checkpoint_path: {checkpoint_info['checkpoint_path']}",
                f"- resumed: {checkpoint_info['resumed']}",
                f"- reused_instances: {checkpoint_info['reused_instances']}",
                f"- recomputed_instances: {checkpoint_info['recomputed_instances']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Metric Fidelity Justification",
            "",
            "Section 10.2 step 5 asks to record whether the decision was correct, and Section 10.4 defines the studied decision as choosing between candidates with noisy estimated values. Therefore the primary success metric is decision-quality within the shared candidate trajectory. Global-opt success remains a secondary diagnostic because it is dominated by the search geometry shared by DA and MSE. This metric change is set before inspecting DA-vs-MSE under the new metric and is intended to be frozen pre-hash.",
            "",
            "## Safeguards",
            "",
            "| safeguard | value |",
            "|---|---|",
        ]
    )
    for key in [
        "candidate_generation_independent_of_selector",
        "same_candidates_for_DA_and_MSE",
        "same_initial_points_for_DA_and_MSE",
        "same_budget_grid_for_DA_and_MSE",
        "same_stopping_rule_for_DA_and_MSE",
        "selector_does_not_generate_candidates",
    ]:
        lines.append(f"| {key} | {bool(config[key])} |")
    lines.extend(
        [
            "",
            "DA and MSE consume the same candidate batches and the same Aer shot memory. The common candidate trace is generated by a selector-independent proposal incumbent; DA/MSE do not generate candidates.",
            "",
            "## Success Definition",
            "",
            f"- epsilon_opt_rule: {config['epsilon_opt_rule']}",
            f"- epsilon_quantile: {config['epsilon_quantile']}",
            "- epsilon_opt is fixed per instance from the frozen ideal landscape, not from candidates seen by a trajectory.",
            "- primary decision-quality: final selected incumbent has ideal regret <= epsilon_opt relative to the best ideal candidate seen in the same trajectory.",
            "- secondary global-opt: final selected incumbent has ideal regret <= epsilon_opt relative to the frozen ideal landscape optimum.",
            "",
            "## Primary Selector Rule",
            "",
            "- DA decision: lexicographic_argmin(estimates[DA_method]).",
            "- MSE decision: lexicographic_argmin(estimates[MSE_method]).",
            "- DA_method and MSE_method are the frozen static selectors from F1a; low probe budgets use the nearest available static selector source budget.",
            "- decision_score_z_removed_from_primary: true",
            "",
            "## P(success; B) Decision-Quality Primary",
            "",
            "| instance | selector | budget | selector_source_budget | selected_method | active_scales | shots_per_candidate | trajectories | successes | P_success | B_at_target_nominal | shots_at_target_0.80 |",
            "|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for row in summary.to_dict(orient="records"):
        b_at = "not_reached" if pd.isna(row["B_at_target_nominal"]) else str(int(row["B_at_target_nominal"]))
        shots_at = "not_reached" if pd.isna(row["shots_at_target_0.80"]) else str(int(row["shots_at_target_0.80"]))
        lines.append(
            "| {instance} | {selector} | {budget} | {selector_source_budget} | {selected_method} | {active_scales} | "
            "{cost_per_candidate_shots} | {trajectories} | {successes} | {P_success:.6g} | ".format(**row)
            + f"{b_at} | {shots_at} |"
        )
    lines.extend(
        [
            "",
            "## Aggregate P(success; B) Decision-Quality Primary",
            "",
            "| selector | budget | selected_method | active_scales | shots_per_candidate | trajectories | successes | P_success |",
            "|---|---:|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in aggregate.to_dict(orient="records"):
        lines.append(
            "| {selector} | {budget} | {selected_method} | {active_scales} | "
            "{cost_per_candidate_shots} | {trajectories} | {successes} | "
            "{P_success:.6g} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## B(0.80) Matched Cost Decision-Quality Primary",
            "",
            "| selector | reaches_0.80 | B_nominal | shots_total_per_candidate | selected_method |",
            "|---|---|---|---|---|",
        ]
    )
    for row in target_rows:
        lines.append(
            "| {selector} | {reaches_target} | {B_nominal} | "
            "{shots_total_per_candidate} | {selected_method} |".format(**row)
        )
    ratio_text = "not_computed"
    if shot_savings_ratio is not None:
        ratio_text = f"{shot_savings_ratio:.6g}"
    lines.extend(
        [
            "",
            f"- reachable_0.80: {reachable}",
            f"- shot_savings_ratio_MSE_over_DA: {ratio_text}",
            f"- decision_quality_advantage_type: {decision_advantage}",
            (
                "- recalibration_if_false: not_needed"
                if reachable
                else "- recalibration_if_false: consider epsilon_quantile slightly higher or candidate_radius slightly higher before hash freeze; not applied here"
            ),
            "",
            "## Robustness By Instance Decision-Quality Primary",
            "",
            "| instance | selector | reaches_0.80 | B_nominal | shots_total_per_candidate | selected_method | max_P_success | marginal_no_cross |",
            "|---|---|---|---|---|---|---:|---|",
        ]
    )
    for row in decision_instance_targets:
        lines.append(
            "| {instance} | {selector} | {reaches_target} | {B_nominal} | "
            "{shots_total_per_candidate} | {selected_method} | {max_P_success:.6g} | "
            "{marginal_no_cross} |".format(**row)
        )
    lines.extend(
        [
            f"- DA_instances_reaching_0.80: {decision_robustness['DA']['reaches']}/{decision_robustness['DA']['total']}",
            f"- MSE_instances_reaching_0.80: {decision_robustness['MSE']['reaches']}/{decision_robustness['MSE']['total']}",
            f"- DA_marginal_no_cross: {decision_robustness['DA']['marginal']}",
            f"- MSE_marginal_no_cross: {decision_robustness['MSE']['marginal']}",
            "",
            "## P(success; B) Global-Opt Secondary",
            "",
            "| instance | selector | budget | selected_method | active_scales | shots_per_candidate | trajectories | successes | P_success | B_at_target_nominal | shots_at_target_0.80 |",
            "|---|---|---:|---|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for row in global_summary.to_dict(orient="records"):
        b_at = "not_reached" if pd.isna(row["B_at_target_nominal"]) else str(int(row["B_at_target_nominal"]))
        shots_at = "not_reached" if pd.isna(row["shots_at_target_0.80"]) else str(int(row["shots_at_target_0.80"]))
        lines.append(
            "| {instance} | {selector} | {budget} | {selected_method} | {active_scales} | "
            "{cost_per_candidate_shots} | {trajectories} | {successes} | {P_success:.6g} | ".format(**row)
            + f"{b_at} | {shots_at} |"
        )
    global_ratio_text = (
        "not_computed"
        if global_shot_savings_ratio is None
        else f"{global_shot_savings_ratio:.6g}"
    )
    lines.extend(
        [
            "",
            "## B(0.80) Matched Cost Global-Opt Secondary",
            "",
            "| selector | reaches_0.80 | B_nominal | shots_total_per_candidate | selected_method |",
            "|---|---|---|---|---|",
        ]
    )
    for row in global_target_rows:
        lines.append(
            "| {selector} | {reaches_target} | {B_nominal} | "
            "{shots_total_per_candidate} | {selected_method} |".format(**row)
        )
    lines.extend(
        [
            "",
            f"- global_opt_reachable_0.80: {global_reachable}",
            f"- global_opt_shot_savings_ratio_MSE_over_DA: {global_ratio_text}",
            f"- global_opt_advantage_type: {global_advantage}",
            "",
            "## Robustness By Instance Global-Opt Secondary",
            "",
            "| instance | selector | reaches_0.80 | B_nominal | shots_total_per_candidate | selected_method | max_P_success | marginal_no_cross |",
            "|---|---|---|---|---|---|---:|---|",
        ]
    )
    for row in global_instance_targets:
        lines.append(
            "| {instance} | {selector} | {reaches_target} | {B_nominal} | "
            "{shots_total_per_candidate} | {selected_method} | {max_P_success:.6g} | "
            "{marginal_no_cross} |".format(**row)
        )
    lines.extend(
        [
            f"- global_DA_instances_reaching_0.80: {global_robustness['DA']['reaches']}/{global_robustness['DA']['total']}",
            f"- global_MSE_instances_reaching_0.80: {global_robustness['MSE']['reaches']}/{global_robustness['MSE']['total']}",
            f"- global_DA_marginal_no_cross: {global_robustness['DA']['marginal']}",
            f"- global_MSE_marginal_no_cross: {global_robustness['MSE']['marginal']}",
            "",
            "## Regime Probe",
            "",
            f"- any_low_budget_P_success_below_one: {regime['any_below_one']}",
            f"- any_selector_separation: {regime['any_selector_separation']}",
            f"- any_budget_rise: {regime['any_budget_rise']}",
            f"- discriminating_probe: {regime['discriminating_probe']}",
            f"- calibration: candidate_radius={config['candidate_radius']}, budget_grid={config['budget_grid']}",
            "",
            "## Primary Metric Discrimination",
            "",
            f"- low_budget_P_success_below_one: {primary_discrimination['low_budget_below_one']}",
            f"- selector_separated_any_budget: {primary_discrimination['selector_separated_any_budget']}",
            f"- rises_with_budget_any_selector: {primary_discrimination['rises_with_budget_any_selector']}",
            f"- decision_quality_discriminates_DA_vs_MSE: {primary_discrimination['discriminates_da_vs_mse']}",
            (
                "- proposal_if_false: not_needed"
                if primary_discrimination["discriminates_da_vs_mse"]
                else "- proposal_if_false: tighten epsilon_opt, e.g. lower epsilon_quantile before hash freeze; not applied here"
            ),
            "",
            "## Example Trajectory 0",
            "",
            "| round | budget | reference_candidate | MSE_method | MSE_candidate | MSE_score | DA_method | DA_candidate | DA_score | round_best_ideal |",
            "|---:|---:|---:|---|---:|---:|---|---:|---:|---:|",
        ]
    )
    for row in trace.to_dict(orient="records"):
        lines.append(
            "| {round} | {budget} | {reference_candidate} | {MSE_method} | {MSE_candidate} | "
            "{MSE_score:.6g} | {DA_method} | {DA_candidate} | {DA_score:.6g} | "
            "{round_best_ideal:.6g} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Cost",
            "",
            f"- aer_runs: {int(cost['aer_runs'])}",
            f"- circuits: {int(cost['circuits'])}",
            f"- shots_at_B_max: {int(cost['shots'])}",
            f"- wall_seconds: {float(duration_seconds):.6g}",
            "",
            "## Raw Trajectory Outcomes",
            "",
            "| instance | trajectory | selector | budget | selected_method | success_decision | regret_decision | success_global | regret_global | epsilon_opt |",
            "|---|---:|---|---:|---|---|---:|---|---:|---:|",
        ]
    )
    for row in results.sort_values(["instance", "trajectory", "budget", "selector"]).to_dict(
        orient="records"
    ):
        lines.append(
            "| {instance} | {trajectory} | {selector} | {budget} | {selected_method} | "
            "{success_decision} | {regret_decision:.6g} | {success_global} | "
            "{regret_global:.6g} | {epsilon_opt:.6g} |".format(**row)
        )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def _summarize(results: pd.DataFrame, p_target: float) -> pd.DataFrame:
    grouped = (
        results.groupby(["instance", "selector", "budget", "selected_method"], as_index=False)
        .agg(
            trajectories=("success", "size"),
            successes=("success", "sum"),
            P_success=("success", "mean"),
            selector_source_budget=("selector_source_budget", "first"),
            active_scales=("active_scales", "first"),
            cost_per_candidate_shots=("cost_per_candidate_shots", "first"),
        )
        .sort_values(["instance", "selector", "budget", "selected_method"], kind="mergesort")
    )
    b_at: dict[tuple[str, str], tuple[int | float, int | float]] = {}
    for (instance, selector), subset in grouped.groupby(["instance", "selector"]):
        ok = subset[subset["P_success"] >= float(p_target)].sort_values(
            ["cost_per_candidate_shots", "budget"],
            kind="mergesort",
        )
        b_at[(str(instance), str(selector))] = (
            (np.nan, np.nan)
            if ok.empty
            else (int(ok.iloc[0]["budget"]), int(ok.iloc[0]["cost_per_candidate_shots"]))
        )
    grouped["B_at_target_nominal"] = [
        b_at[(str(row["instance"]), str(row["selector"]))][0]
        for row in grouped.to_dict(orient="records")
    ]
    grouped["shots_at_target_0.80"] = [
        b_at[(str(row["instance"]), str(row["selector"]))][1]
        for row in grouped.to_dict(orient="records")
    ]
    return grouped


def _summary_with_success_column(
    results: pd.DataFrame,
    p_target: float,
    success_column: str,
) -> pd.DataFrame:
    tmp = results.copy()
    tmp["success"] = tmp[success_column]
    return _summarize(tmp, p_target)


def _unique_or_mixed(values: pd.Series) -> str:
    unique = sorted({str(value) for value in values})
    return unique[0] if len(unique) == 1 else "mixed:" + "+".join(unique)


def _unique_int_or_max(values: pd.Series) -> int:
    unique = sorted({int(value) for value in values})
    return unique[0] if len(unique) == 1 else max(unique)


def _aggregate_summary(results: pd.DataFrame, p_target: float) -> pd.DataFrame:
    grouped = (
        results.groupby(["selector", "budget"], as_index=False)
        .agg(
            selected_method=("selected_method", _unique_or_mixed),
            trajectories=("success", "size"),
            successes=("success", "sum"),
            P_success=("success", "mean"),
            active_scales=("active_scales", _unique_int_or_max),
            cost_per_candidate_shots=("cost_per_candidate_shots", _unique_int_or_max),
        )
        .sort_values(["selector", "budget"], kind="mergesort")
    )
    b_at: dict[str, tuple[int | float, int | float]] = {}
    for selector, subset in grouped.groupby("selector"):
        ok = subset[subset["P_success"] >= float(p_target)].sort_values(
            ["cost_per_candidate_shots", "budget"],
            kind="mergesort",
        )
        b_at[str(selector)] = (
            (np.nan, np.nan)
            if ok.empty
            else (int(ok.iloc[0]["budget"]), int(ok.iloc[0]["cost_per_candidate_shots"]))
        )
    grouped["B_at_target_nominal"] = [
        b_at[str(row["selector"])][0] for row in grouped.to_dict(orient="records")
    ]
    grouped["shots_at_target_0.80"] = [
        b_at[str(row["selector"])][1] for row in grouped.to_dict(orient="records")
    ]
    return grouped


def _aggregate_with_success_column(
    results: pd.DataFrame,
    p_target: float,
    success_column: str,
) -> pd.DataFrame:
    tmp = results.copy()
    tmp["success"] = tmp[success_column]
    return _aggregate_summary(tmp, p_target=p_target)


def _target_crossings(
    aggregate: pd.DataFrame,
    p_target: float,
) -> tuple[list[dict[str, object]], bool, float | None]:
    rows: list[dict[str, object]] = []
    shots: dict[str, int] = {}
    for selector, subset in aggregate.groupby("selector"):
        ok = subset[subset["P_success"] >= float(p_target)].sort_values(
            ["cost_per_candidate_shots", "budget"],
            kind="mergesort",
        )
        if ok.empty:
            rows.append(
                {
                    "selector": str(selector),
                    "reaches_target": False,
                    "B_nominal": "not_reached",
                    "shots_total_per_candidate": "not_reached",
                    "selected_method": "not_reached",
                }
            )
            continue
        hit = ok.iloc[0]
        shot_value = int(hit["cost_per_candidate_shots"])
        shots[str(selector)] = shot_value
        rows.append(
            {
                "selector": str(selector),
                "reaches_target": True,
                "B_nominal": int(hit["budget"]),
                "shots_total_per_candidate": shot_value,
                "selected_method": str(hit["selected_method"]),
            }
        )
    reachable = any(bool(row["reaches_target"]) for row in rows)
    ratio = None
    if "DA" in shots and "MSE" in shots and shots["DA"] > 0:
        ratio = shots["MSE"] / float(shots["DA"])
    return rows, reachable, ratio


def _instance_target_rows(summary: pd.DataFrame, p_target: float) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for (instance, selector), subset in summary.groupby(["instance", "selector"]):
        ordered = subset.sort_values(["cost_per_candidate_shots", "budget"], kind="mergesort")
        max_p = float(ordered["P_success"].max())
        ok = ordered[ordered["P_success"] >= float(p_target)]
        if ok.empty:
            rows.append(
                {
                    "instance": str(instance),
                    "selector": str(selector),
                    "reaches_target": False,
                    "B_nominal": "not_reached",
                    "shots_total_per_candidate": "not_reached",
                    "selected_method": "not_reached",
                    "max_P_success": max_p,
                    "marginal_no_cross": bool(max_p >= float(p_target) - 0.05),
                }
            )
            continue
        hit = ok.iloc[0]
        rows.append(
            {
                "instance": str(instance),
                "selector": str(selector),
                "reaches_target": True,
                "B_nominal": int(hit["budget"]),
                "shots_total_per_candidate": int(hit["cost_per_candidate_shots"]),
                "selected_method": str(hit["selected_method"]),
                "max_P_success": max_p,
                "marginal_no_cross": False,
            }
        )
    return rows


def _robustness_counts(rows: list[dict[str, object]]) -> dict[str, dict[str, int]]:
    out = {
        "DA": {"total": 0, "reaches": 0, "marginal": 0},
        "MSE": {"total": 0, "reaches": 0, "marginal": 0},
    }
    for row in rows:
        selector = str(row["selector"])
        if selector not in out:
            out[selector] = {"total": 0, "reaches": 0, "marginal": 0}
        out[selector]["total"] += 1
        out[selector]["reaches"] += int(bool(row["reaches_target"]))
        out[selector]["marginal"] += int(bool(row["marginal_no_cross"]))
    return out


def _radius_sweep_summary(results: pd.DataFrame) -> pd.DataFrame:
    return (
        results.groupby(["radius", "selector", "budget"], as_index=False)
        .agg(
            selected_method=("selected_method", _unique_or_mixed),
            trajectories=("success", "size"),
            successes=("success", "sum"),
            P_success=("success", "mean"),
            active_scales=("active_scales", _unique_int_or_max),
            cost_per_candidate_shots=("cost_per_candidate_shots", _unique_int_or_max),
        )
        .sort_values(["radius", "selector", "budget"], kind="mergesort")
    )


def _radius_target_rows(
    summary: pd.DataFrame,
    p_target: float,
) -> tuple[pd.DataFrame, dict[float, float | None]]:
    rows: list[dict[str, object]] = []
    ratios: dict[float, float | None] = {}
    for radius, radius_df in summary.groupby("radius"):
        shots: dict[str, int] = {}
        for selector, subset in radius_df.groupby("selector"):
            ok = subset[subset["P_success"] >= float(p_target)].sort_values(
                ["cost_per_candidate_shots", "budget"],
                kind="mergesort",
            )
            if ok.empty:
                rows.append(
                    {
                        "radius": float(radius),
                        "selector": str(selector),
                        "reaches_target": False,
                        "B_nominal": "not_reached",
                        "shots_total_per_candidate": "not_reached",
                        "selected_method": "not_reached",
                    }
                )
                continue
            hit = ok.iloc[0]
            shot_value = int(hit["cost_per_candidate_shots"])
            shots[str(selector)] = shot_value
            rows.append(
                {
                "radius": float(radius),
                "selector": str(selector),
                "reaches_target": True,
                    "B_nominal": int(hit["budget"]),
                    "shots_total_per_candidate": shot_value,
                    "selected_method": str(hit["selected_method"]),
                }
            )
        ratios[float(radius)] = (
            shots["MSE"] / float(shots["DA"])
            if "DA" in shots and "MSE" in shots and shots["DA"] > 0
            else None
        )
    return pd.DataFrame(rows), ratios


def _radius_selection_table(
    summary: pd.DataFrame,
    *,
    ceiling_min: float,
    mse_rise_min: float,
) -> tuple[pd.DataFrame, float | None]:
    rows: list[dict[str, object]] = []
    for radius, radius_df in summary.groupby("radius"):
        by_selector: dict[str, dict[str, float]] = {}
        for selector, subset in radius_df.groupby("selector"):
            ordered = subset.sort_values("budget", kind="mergesort")
            low = float(ordered.iloc[0]["P_success"])
            ceiling = float(ordered.iloc[-1]["P_success"])
            by_selector[str(selector)] = {
                "p_at_low": low,
                "ceiling": ceiling,
                "rise": ceiling - low,
            }
        da_ceiling = by_selector.get("DA", {}).get("ceiling", np.nan)
        mse_ceiling = by_selector.get("MSE", {}).get("ceiling", np.nan)
        mse_rise = by_selector.get("MSE", {}).get("rise", np.nan)
        low_da = by_selector.get("DA", {}).get("p_at_low", np.nan)
        low_mse = by_selector.get("MSE", {}).get("p_at_low", np.nan)
        discrimination_low = (
            bool(max(low_da, low_mse) < 1.0 and abs(low_da - low_mse) > 0.0)
            if np.isfinite(low_da) and np.isfinite(low_mse)
            else False
        )
        eligible = bool(
            da_ceiling >= float(ceiling_min)
            and mse_ceiling >= float(ceiling_min)
            and mse_rise >= float(mse_rise_min)
        )
        rows.append(
            {
                "radius": float(radius),
                "DA_P_at_256": low_da,
                "MSE_P_at_256": low_mse,
                "DA_ceiling": da_ceiling,
                "MSE_ceiling": mse_ceiling,
                "MSE_rise": mse_rise,
                "low_budget_discriminates": discrimination_low,
                "eligible_by_rule": eligible,
            }
        )
    table = pd.DataFrame(rows).sort_values("radius", kind="mergesort")
    eligible_rows = table[table["eligible_by_rule"]]
    chosen = None if eligible_rows.empty else float(eligible_rows.iloc[0]["radius"])
    return table, chosen


def _render_radius_sweep_report(
    *,
    output_root: Path,
    config: dict,
    summary: pd.DataFrame,
    selection: pd.DataFrame,
    chosen_radius: float | None,
    target_rows: pd.DataFrame,
    shot_ratios: dict[float, float | None],
    cost: dict[str, int | float],
    duration_seconds: float,
) -> Path:
    out = output_root / report_rel(str(config["profile"]))
    out.parent.mkdir(parents=True, exist_ok=True)
    ceiling_min = float(config["selection_rule"]["ceiling_min_both_selectors"])
    mse_rise_min = float(config["selection_rule"]["mse_rise_min"])
    lines = [
        "# Dynamic Pilot Radius Sweep",
        "",
        "Diagnostic recalibration probe only: not canonical, not part of verify/reference, and not frozen.",
        "",
        "## Setup",
        "",
        f"- profile: {config['profile']}",
        f"- instances: {config['instance_ids']}",
        f"- trajectories_per_radius: {config['trajectories']}",
        f"- max_rounds: {config['max_rounds']}",
        f"- candidates_per_round: {config['candidates_per_round']}",
        f"- budget_grid: {config['budget_grid']}",
        f"- B_max: {config['B_max']}",
        f"- candidate_radius_grid: {config['candidate_radius_grid']}",
        f"- epsilon_quantile: {config['epsilon_quantile']}",
        "- selector_primary: method-only argmin; no decision_score_z.",
        "- safeguards: same candidates, initial points, budget grid, stopping rule, and Aer shot memory for DA/MSE.",
        "",
        "## Neutral Selection Rule",
        "",
        f"- choose smallest radius with DA ceiling >= {ceiling_min} and MSE ceiling >= {ceiling_min}.",
        f"- require MSE rise = P_success(B_max) - P_success(256) >= {mse_rise_min}.",
        "- this rule does not use the DA-vs-MSE margin.",
        "",
        "## Radius Selection Table",
        "",
        "| radius | DA_P@256 | MSE_P@256 | DA_ceiling | MSE_ceiling | MSE_rise | low_budget_discriminates | eligible_by_rule |",
        "|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in selection.to_dict(orient="records"):
        lines.append(
            "| {radius:.2f} | {DA_P_at_256:.6g} | {MSE_P_at_256:.6g} | "
            "{DA_ceiling:.6g} | {MSE_ceiling:.6g} | {MSE_rise:.6g} | "
            "{low_budget_discriminates} | {eligible_by_rule} |".format(**row)
        )
    chosen_text = "none" if chosen_radius is None else f"{chosen_radius:.2f}"
    lines.extend(
        [
            "",
            f"- chosen_radius_by_rule: {chosen_text}",
            (
                "- if_none: propose increasing epsilon_quantile slightly before hash freeze; not applied here."
                if chosen_radius is None
                else "- if_none: not_applicable"
            ),
            "",
            "## P(success; B) Curves",
            "",
            "| radius | selector | budget | selected_method | shots_per_candidate | trajectories | successes | P_success |",
            "|---:|---|---:|---|---:|---:|---:|---:|",
        ]
    )
    for row in summary.to_dict(orient="records"):
        lines.append(
            "| {radius:.2f} | {selector} | {budget} | {selected_method} | "
            "{cost_per_candidate_shots} | {trajectories} | {successes} | "
            "{P_success:.6g} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## B(0.80) Matched Cost By Radius",
            "",
            "| radius | selector | reaches_0.80 | B_nominal | shots_total_per_candidate | selected_method |",
            "|---:|---|---|---|---|---|",
        ]
    )
    for row in target_rows.to_dict(orient="records"):
        lines.append(
            "| {radius:.2f} | {selector} | {reaches_target} | {B_nominal} | "
            "{shots_total_per_candidate} | {selected_method} |".format(**row)
        )
    lines.extend(["", "## Shot Savings Ratio", ""])
    if chosen_radius is not None:
        ratio = shot_ratios.get(float(chosen_radius))
        ratio_text = "not_computed" if ratio is None else f"{ratio:.6g}"
        lines.append(f"- chosen_radius_ratio_MSE_over_DA: {ratio_text}")
    for radius in sorted(shot_ratios):
        ratio = shot_ratios[radius]
        ratio_text = "not_computed" if ratio is None else f"{ratio:.6g}"
        lines.append(f"- radius_{radius:.2f}_ratio_MSE_over_DA: {ratio_text}")
    lines.extend(
        [
            "",
            "## Cost",
            "",
            f"- aer_runs: {int(cost['aer_runs'])}",
            f"- circuits: {int(cost['circuits'])}",
            f"- shots_at_B_max: {int(cost['shots'])}",
            f"- wall_seconds: {float(duration_seconds):.6g}",
        ]
    )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def _epsilon_values_by_instance(config: dict) -> dict[str, dict[float, float]]:
    values: dict[str, dict[float, float]] = {}
    for instance_id in config["instance_ids"]:
        landscape = build_candidate_landscape(
            str(instance_id),
            candidate_count=int(config["initial_landscape_count"]),
            depth=int(config["depth"]),
            num_qubits=int(config["qubits"]),
            graph_degree=int(config["graph_degree"]),
            local_radius=float(config["local_radius"]),
            search_radius=float(config["search_radius"]),
            search_count=int(config["search_count"]),
        )
        values[str(instance_id)] = {
            float(q): epsilon_opt_from_ideal_values(
                landscape.ideal_values,
                quantile=float(q),
            )
            for q in config["epsilon_quantile_grid"]
        }
    return values


def _rescore_epsilon_grid(results: pd.DataFrame, config: dict) -> pd.DataFrame:
    eps_by_instance = _epsilon_values_by_instance(config)
    rows: list[dict[str, object]] = []
    for row in results.to_dict(orient="records"):
        instance_id = str(row["instance"])
        for q, epsilon in eps_by_instance[instance_id].items():
            out = dict(row)
            out["epsilon_quantile"] = float(q)
            out["epsilon_opt"] = float(epsilon)
            out["success_decision"] = bool(
                float(out["regret_decision"]) <= float(epsilon)
            )
            out["success_global"] = bool(float(out["regret_global"]) <= float(epsilon))
            out["success"] = out["success_decision"]
            rows.append(out)
    return pd.DataFrame(rows)


def _epsilon_metric_summary(
    scored: pd.DataFrame,
    success_column: str,
) -> pd.DataFrame:
    return (
        scored.groupby(["epsilon_quantile", "selector", "budget"], as_index=False)
        .agg(
            selected_method=("selected_method", _unique_or_mixed),
            trajectories=(success_column, "size"),
            successes=(success_column, "sum"),
            P_success=(success_column, "mean"),
            active_scales=("active_scales", _unique_int_or_max),
            cost_per_candidate_shots=("cost_per_candidate_shots", _unique_int_or_max),
        )
        .sort_values(["epsilon_quantile", "selector", "budget"], kind="mergesort")
    )


def _epsilon_selection_table(
    decision_summary: pd.DataFrame,
    *,
    p_target: float,
    mse_p256_max: float,
    mse_rise_min: float,
) -> tuple[pd.DataFrame, float | None]:
    rows: list[dict[str, object]] = []
    for q, q_df in decision_summary.groupby("epsilon_quantile"):
        mse = q_df[q_df["selector"] == "MSE"].sort_values("budget", kind="mergesort")
        if mse.empty:
            continue
        p256 = float(mse[mse["budget"] == int(mse["budget"].min())].iloc[0]["P_success"])
        pmax = float(mse[mse["budget"] == int(mse["budget"].max())].iloc[0]["P_success"])
        rise = pmax - p256
        crosses = bool((mse["P_success"] >= float(p_target)).any())
        eligible = bool(
            p256 <= float(mse_p256_max)
            and crosses
            and rise >= float(mse_rise_min)
        )
        rows.append(
            {
                "epsilon_quantile": float(q),
                "P_success_MSE_at_256": p256,
                "P_success_MSE_at_8192": pmax,
                "rise_MSE": rise,
                "crosses_target": crosses,
                "eligible": eligible,
            }
        )
    table = pd.DataFrame(rows).sort_values(
        "epsilon_quantile",
        ascending=False,
        kind="mergesort",
    )
    eligible_rows = table[table["eligible"]]
    chosen = None if eligible_rows.empty else float(eligible_rows.iloc[0]["epsilon_quantile"])
    return table, chosen


def _target_rows_for_summary(
    summary: pd.DataFrame,
    p_target: float,
) -> tuple[list[dict[str, object]], float | None]:
    target_rows, _reachable, ratio = _target_crossings(summary, p_target)
    return target_rows, ratio


def _advantage_label(summary: pd.DataFrame, ratio: float | None) -> str:
    if ratio is None or ratio <= 1.0:
        return "no_cost_advantage"
    diffs = []
    for _budget, subset in summary.groupby("budget"):
        values = {
            str(row["selector"]): float(row["P_success"])
            for row in subset.to_dict(orient="records")
        }
        if {"DA", "MSE"} <= set(values):
            diffs.append(values["DA"] - values["MSE"])
    if diffs and min(diffs) >= -1e-12 and max(diffs) > 1e-12:
        return "cost_plus_accuracy"
    return "cost_only"


def _render_epsilon_sweep_report(
    *,
    output_root: Path,
    config: dict,
    decision_summary: pd.DataFrame,
    global_summary: pd.DataFrame,
    selection: pd.DataFrame,
    chosen_epsilon: float | None,
    cost: dict[str, int | float],
    duration_seconds: float,
) -> Path:
    out = output_root / report_rel(str(config["profile"]))
    out.parent.mkdir(parents=True, exist_ok=True)
    rule = config.get("epsilon_selection_rule", {})
    mse_p256_max = float(rule.get("mse_p256_max", 0.60))
    mse_rise_min = float(rule.get("mse_rise_min", 0.20))
    lines = [
        "# Dynamic Pilot Epsilon Sweep",
        "",
        "Diagnostic final epsilon recalibration probe only: not canonical, not part of verify/reference, and not frozen.",
        "",
        "## Metric Fidelity Justification",
        "",
        "Section 10.2 step 5 asks to record whether the decision was correct, and Section 10.4 defines the studied decision as choosing between candidates with noisy estimated values. Therefore the primary success metric is decision-quality within the shared candidate trajectory. Global-opt success remains a secondary diagnostic because it is dominated by the search geometry shared by DA and MSE. This metric change is set before inspecting DA-vs-MSE under the new metric and is intended to be frozen pre-hash.",
        "",
        "## Setup",
        "",
        f"- profile: {config['profile']}",
        f"- instances: {config['instance_ids']}",
        f"- trajectories: {config['trajectories']}",
        f"- max_rounds: {config['max_rounds']}",
        f"- candidates_per_round: {config['candidates_per_round']}",
        f"- budget_grid: {config['budget_grid']}",
        f"- B_max: {config['B_max']}",
        f"- candidate_radius: {config['candidate_radius']}",
        f"- epsilon_quantile_grid: {config['epsilon_quantile_grid']}",
        "- rescore_only: epsilon changes success labels only; Aer trajectories were simulated once.",
        "- selector_primary: method-only argmin; no decision_score_z.",
        "- safeguards: same candidates, initial points, budget grid, stopping rule, and Aer shot memory for DA/MSE.",
        "",
        "## Stopping Rule",
        "",
        "- This is the final epsilon iteration.",
        "- If an epsilon de-saturates the curve and crosses 0.80, that is the dynamic full regime.",
        "- If none satisfies the rule, Claim 2 dynamic is reported as cost-based and epsilon is not tuned further.",
        "",
        "## Neutral Epsilon Selection Rule",
        "",
        f"- choose the largest epsilon_quantile with MSE P_success@256 <= {mse_p256_max}.",
        "- require MSE to cross P_success >= 0.80 at some budget.",
        f"- require MSE rise = P_success@8192 - P_success@256 >= {mse_rise_min}.",
        "- this rule uses only the baseline MSE, not the DA-vs-MSE margin.",
        "",
        "## Epsilon Eligibility Table",
        "",
        "| epsilon_quantile | P_success_MSE@256 | P_success_MSE@8192 | rise_MSE | crosses_0.80 | eligible |",
        "|---:|---:|---:|---:|---|---|",
    ]
    for row in selection.to_dict(orient="records"):
        lines.append(
            "| {epsilon_quantile:.2f} | {P_success_MSE_at_256:.6g} | "
            "{P_success_MSE_at_8192:.6g} | {rise_MSE:.6g} | "
            "{crosses_target} | {eligible} |".format(**row)
        )
    chosen_text = "none" if chosen_epsilon is None else f"{chosen_epsilon:.2f}"
    lines.extend(
        [
            "",
            f"- chosen_epsilon_quantile: {chosen_text}",
            (
                "- if_none: Claim 2 dynamic should be treated as cost-based; no further epsilon tuning in this calibration loop."
                if chosen_epsilon is None
                else "- if_none: not_applicable"
            ),
            "",
            "## Decision-Quality Primary Curves",
            "",
            "| epsilon_quantile | selector | budget | selected_method | shots_per_candidate | trajectories | successes | P_success |",
            "|---:|---|---:|---|---:|---:|---:|---:|",
        ]
    )
    for row in decision_summary.to_dict(orient="records"):
        lines.append(
            "| {epsilon_quantile:.2f} | {selector} | {budget} | {selected_method} | "
            "{cost_per_candidate_shots} | {trajectories} | {successes} | "
            "{P_success:.6g} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Global-Opt Secondary Curves",
            "",
            "| epsilon_quantile | selector | budget | selected_method | shots_per_candidate | trajectories | successes | P_success |",
            "|---:|---|---:|---|---:|---:|---:|---:|",
        ]
    )
    for row in global_summary.to_dict(orient="records"):
        lines.append(
            "| {epsilon_quantile:.2f} | {selector} | {budget} | {selected_method} | "
            "{cost_per_candidate_shots} | {trajectories} | {successes} | "
            "{P_success:.6g} |".format(**row)
        )

    if chosen_epsilon is not None:
        decision_chosen = decision_summary[
            decision_summary["epsilon_quantile"] == float(chosen_epsilon)
        ].copy()
        global_chosen = global_summary[
            global_summary["epsilon_quantile"] == float(chosen_epsilon)
        ].copy()
        decision_targets, decision_ratio = _target_rows_for_summary(
            decision_chosen,
            float(config["P_target"]),
        )
        global_targets, global_ratio = _target_rows_for_summary(
            global_chosen,
            float(config["P_target"]),
        )
        decision_label = _advantage_label(decision_chosen, decision_ratio)
        global_label = _advantage_label(global_chosen, global_ratio)
        lines.extend(
            [
                "",
                f"## Chosen Epsilon Decision-Quality Primary ({chosen_epsilon:.2f})",
                "",
                "| selector | reaches_0.80 | B_nominal | shots_total_per_candidate | selected_method |",
                "|---|---|---|---|---|",
            ]
        )
        for row in decision_targets:
            lines.append(
                "| {selector} | {reaches_target} | {B_nominal} | "
                "{shots_total_per_candidate} | {selected_method} |".format(**row)
            )
        decision_ratio_text = "not_computed" if decision_ratio is None else f"{decision_ratio:.6g}"
        lines.extend(
            [
                f"- decision_quality_shot_savings_ratio_MSE_over_DA: {decision_ratio_text}",
                f"- decision_quality_advantage_type: {decision_label}",
                "",
                f"## Chosen Epsilon Global-Opt Secondary ({chosen_epsilon:.2f})",
                "",
                "| selector | reaches_0.80 | B_nominal | shots_total_per_candidate | selected_method |",
                "|---|---|---|---|---|",
            ]
        )
        for row in global_targets:
            lines.append(
                "| {selector} | {reaches_target} | {B_nominal} | "
                "{shots_total_per_candidate} | {selected_method} |".format(**row)
            )
        global_ratio_text = "not_computed" if global_ratio is None else f"{global_ratio:.6g}"
        lines.extend(
            [
                f"- global_opt_shot_savings_ratio_MSE_over_DA: {global_ratio_text}",
                f"- global_opt_advantage_type: {global_label}",
            ]
        )

    lines.extend(
        [
            "",
            "## Cost",
            "",
            f"- aer_runs: {int(cost['aer_runs'])}",
            f"- circuits: {int(cost['circuits'])}",
            f"- shots_at_B_max: {int(cost['shots'])}",
            f"- wall_seconds: {float(duration_seconds):.6g}",
        ]
    )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def _regime_diagnostic(summary: pd.DataFrame) -> dict[str, bool]:
    any_below_one = bool((summary["P_success"] < 1.0).any())
    any_selector_separation = False
    for (_, budget), subset in summary.groupby(["instance", "budget"]):
        values = {
            str(row["selector"]): float(row["P_success"])
            for row in subset.to_dict(orient="records")
        }
        if {"DA", "MSE"} <= set(values) and abs(values["DA"] - values["MSE"]) > 0.0:
            any_selector_separation = True
            break
    any_budget_rise = False
    for (_, selector), subset in summary.groupby(["instance", "selector"]):
        ordered = subset.sort_values("budget", kind="mergesort")
        vals = ordered["P_success"].to_numpy(dtype=float)
        if vals.size >= 2 and float(vals[-1]) > float(vals[0]):
            any_budget_rise = True
            break
    return {
        "any_below_one": any_below_one,
        "any_selector_separation": any_selector_separation,
        "any_budget_rise": any_budget_rise,
        "discriminating_probe": bool(any_below_one and (any_selector_separation or any_budget_rise)),
    }


def _metric_discrimination_diagnostic(summary: pd.DataFrame) -> dict[str, bool]:
    low_budget_below_one = False
    for _instance, subset in summary.groupby("instance"):
        low_budget = int(subset["budget"].min())
        low_rows = subset[subset["budget"] == low_budget]
        if bool((low_rows["P_success"] < 1.0).any()):
            low_budget_below_one = True
            break

    selector_separated = False
    for (_, _budget), subset in summary.groupby(["instance", "budget"]):
        values = {
            str(row["selector"]): float(row["P_success"])
            for row in subset.to_dict(orient="records")
        }
        if {"DA", "MSE"} <= set(values) and abs(values["DA"] - values["MSE"]) > 0.0:
            selector_separated = True
            break

    rises_with_budget = False
    for (_, _selector), subset in summary.groupby(["instance", "selector"]):
        ordered = subset.sort_values("budget", kind="mergesort")
        vals = ordered["P_success"].to_numpy(dtype=float)
        if vals.size >= 2 and float(np.max(vals)) > float(vals[0]):
            rises_with_budget = True
            break

    return {
        "low_budget_below_one": low_budget_below_one,
        "selector_separated_any_budget": selector_separated,
        "rises_with_budget_any_selector": rises_with_budget,
        "discriminates_da_vs_mse": bool(
            low_budget_below_one and selector_separated and rises_with_budget
        ),
    }


def run(output_root: Path = DEFAULT_OUTPUT_ROOT, profile: str = "smoke") -> dict[str, object]:
    start = time.perf_counter()
    config = load_config(profile)
    if "epsilon_quantile_grid" in config:
        all_results = []
        total_cost = {"aer_runs": 0, "circuits": 0, "shots": 0}
        for instance_id in config["instance_ids"]:
            results, _trace, cost = _run_instance(
                output_root=output_root,
                instance_id=str(instance_id),
                config=config,
            )
            all_results.append(results)
            for key in total_cost:
                total_cost[key] += int(cost[key])
        results_df = pd.concat(all_results, ignore_index=True)
        scored = _rescore_epsilon_grid(results_df, config)
        decision_summary = _epsilon_metric_summary(scored, "success_decision")
        global_summary = _epsilon_metric_summary(scored, "success_global")
        rule = config.get("epsilon_selection_rule", {})
        selection, chosen_epsilon = _epsilon_selection_table(
            decision_summary,
            p_target=float(config["P_target"]),
            mse_p256_max=float(rule.get("mse_p256_max", 0.60)),
            mse_rise_min=float(rule.get("mse_rise_min", 0.20)),
        )
        duration = time.perf_counter() - start
        report = _render_epsilon_sweep_report(
            output_root=output_root,
            config=config,
            decision_summary=decision_summary,
            global_summary=global_summary,
            selection=selection,
            chosen_epsilon=chosen_epsilon,
            cost=total_cost,
            duration_seconds=duration,
        )
        payload = {
            "profile": profile,
            "report": report.relative_to(output_root).as_posix(),
            "chosen_epsilon_quantile": chosen_epsilon,
            "selection": selection.to_dict(orient="records"),
            "decision_summary": decision_summary.to_dict(orient="records"),
            "global_summary": global_summary.to_dict(orient="records"),
            "cost": total_cost,
            "duration_seconds": duration,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return payload
    if "candidate_radius_grid" in config:
        all_results = []
        total_cost = {"aer_runs": 0, "circuits": 0, "shots": 0}
        for radius in config["candidate_radius_grid"]:
            radius_config = dict(config)
            radius_config["candidate_radius"] = float(radius)
            for instance_id in radius_config["instance_ids"]:
                results, _trace, cost = _run_instance(
                    output_root=output_root,
                    instance_id=str(instance_id),
                    config=radius_config,
                )
                results.insert(0, "radius", float(radius))
                all_results.append(results)
                for key in total_cost:
                    total_cost[key] += int(cost[key])
        results_df = pd.concat(all_results, ignore_index=True)
        summary = _radius_sweep_summary(results_df)
        selection_rule = config.get("selection_rule", {})
        ceiling_min = float(selection_rule.get("ceiling_min_both_selectors", 0.85))
        mse_rise_min = float(selection_rule.get("mse_rise_min", 0.15))
        selection, chosen_radius = _radius_selection_table(
            summary,
            ceiling_min=ceiling_min,
            mse_rise_min=mse_rise_min,
        )
        target_rows, shot_ratios = _radius_target_rows(
            summary,
            float(config["P_target"]),
        )
        duration = time.perf_counter() - start
        report = _render_radius_sweep_report(
            output_root=output_root,
            config=config,
            summary=summary,
            selection=selection,
            chosen_radius=chosen_radius,
            target_rows=target_rows,
            shot_ratios=shot_ratios,
            cost=total_cost,
            duration_seconds=duration,
        )
        payload = {
            "profile": profile,
            "report": report.relative_to(output_root).as_posix(),
            "chosen_radius": chosen_radius,
            "selection": selection.to_dict(orient="records"),
            "summary": summary.to_dict(orient="records"),
            "cost": total_cost,
            "duration_seconds": duration,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return payload
    if bool(config.get("checkpoint_by_instance", False)):
        results_df, trace_df, total_cost, checkpoint_info = _run_checkpointed_instances(
            output_root=output_root,
            config=config,
        )
        summary = _summarize(results_df, float(config["P_target"]))
        duration = time.perf_counter() - start
        report_config = dict(config)
        report_config["_checkpoint_info"] = checkpoint_info
        report = _render_report(
            output_root=output_root,
            config=report_config,
            summary=summary,
            results=results_df,
            trace=trace_df,
            cost=total_cost,
            duration_seconds=duration,
        )
        payload = {
            "profile": profile,
            "report": report.relative_to(output_root).as_posix(),
            "summary": summary.to_dict(orient="records"),
            "checkpoint": checkpoint_info,
            "cost": total_cost,
            "duration_seconds": duration,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return payload
    all_results = []
    all_traces = []
    total_cost = {"aer_runs": 0, "circuits": 0, "shots": 0}
    for instance_id in config["instance_ids"]:
        results, trace, cost = _run_instance(
            output_root=output_root,
            instance_id=str(instance_id),
            config=config,
        )
        all_results.append(results)
        all_traces.append(trace)
        for key in total_cost:
            total_cost[key] += int(cost[key])
    results_df = pd.concat(all_results, ignore_index=True)
    trace_df = pd.concat(all_traces, ignore_index=True)
    summary = _summarize(results_df, float(config["P_target"]))
    duration = time.perf_counter() - start
    report = _render_report(
        output_root=output_root,
        config=config,
        summary=summary,
        results=results_df,
        trace=trace_df,
        cost=total_cost,
        duration_seconds=duration,
    )
    payload = {
        "profile": profile,
        "report": report.relative_to(output_root).as_posix(),
        "summary": summary.to_dict(orient="records"),
        "cost": total_cost,
        "duration_seconds": duration,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--profile", default="smoke")
    args = parser.parse_args(argv)
    run(Path(args.output).resolve(), profile=args.profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
