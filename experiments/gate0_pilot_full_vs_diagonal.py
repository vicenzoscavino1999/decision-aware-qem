from __future__ import annotations

import argparse
import io
import json
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from qiskit import transpile
from qiskit_aer import AerSimulator
from sklearn.covariance import LedoitWolf

from daqem.candidates import (
    CONFIRMATORY_INSTANCE_IDS,
    PILOT_INSTANCE_IDS,
    assert_pilot_instance,
    landscape_for_instance,
    maxcut_graph_for_instance,
)
from daqem.gap_kernel import nearest_psd
from daqem.noise import (
    ONE_QUBIT_DEPOLARIZING,
    TWO_QUBIT_DEPOLARIZING,
    depolarizing_noise_model,
)
from daqem.qaoa import maxcut_value, qaoa_maxcut_circuit
from daqem.qem_methods import (
    accuracy_zne_coeffs,
    decision_optimal_zne_coeffs,
    richardson_constraints,
)
from daqem.risk import gri_risk
from daqem.rng import make_rng
from daqem.selectors import da_selector


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "reproducibility" / "config" / "gate0_pilot.yaml"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "results"
CSV_REL = Path("pilot/gate0_full_vs_diagonal.csv")
REGIME_PROBE_REL = Path("pilot/regime_probe.md")
MAX_MEMORY_SHOTS_PER_CIRCUIT = 81_920


def load_config(profile: str = "smoke") -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    profiles = raw.get("profiles", {})
    if profile not in profiles:
        raise ValueError(f"unknown Gate 0 pilot profile: {profile}")
    config = dict(raw.get("defaults", {}))
    config.update(profiles[profile])
    config["profile"] = profile
    config["pilot_instance_ids"] = list(raw.get("pilot_instance_ids", PILOT_INSTANCE_IDS))
    config["confirmatory_instance_ids"] = list(
        raw.get("confirmatory_instance_ids", CONFIRMATORY_INSTANCE_IDS)
    )
    config["output_namespace"] = str(config.get("output_namespace", "pilot"))
    overlap = set(config["pilot_instance_ids"]) & set(config["confirmatory_instance_ids"])
    if overlap:
        raise ValueError(f"pilot/confirmatory firewall split overlaps: {sorted(overlap)}")
    for instance_id in config["instance_ids"]:
        if config["output_namespace"] == "pilot":
            if instance_id not in config["pilot_instance_ids"]:
                raise ValueError(f"Gate 0 pilot profile uses non-pilot id: {instance_id}")
        elif config["output_namespace"] == "confirmatory":
            if instance_id not in CONFIRMATORY_INSTANCE_IDS:
                raise ValueError(
                    f"Gate 0 confirmatory profile uses non-confirmatory id: {instance_id}"
                )
        else:
            raise ValueError(f"unknown Gate 0 output namespace: {config['output_namespace']!r}")
    return config


def raw_relpath(instance_id: str) -> Path:
    return Path("pilot") / "raw" / f"{instance_id}.npz"


def confirmatory_raw_relpath(instance_id: str) -> Path:
    return Path("confirmatory") / "raw" / f"{instance_id}.npz"


def regime_probe_raw_relpath(instance_id: str) -> Path:
    return Path("pilot") / "regime_probe_raw" / f"{instance_id}.npz"


def _write_deterministic_npz(path: Path, **arrays) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    with zipfile.ZipFile(tmp, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(arrays):
            buffer = io.BytesIO()
            np.lib.format.write_array(buffer, np.asarray(arrays[name]), allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy")
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, buffer.getvalue())
    tmp.replace(path)


def _prefix_objective_estimates(memory: list[str], graph, budgets: list[int]) -> np.ndarray:
    values = np.fromiter((maxcut_value(bitstring, graph) for bitstring in memory), dtype=float)
    cumulative = np.cumsum(values)
    return -np.array([cumulative[budget - 1] / float(budget) for budget in budgets], dtype=float)


def _replicate_chunks(replicates: int, b_max: int) -> list[tuple[int, int]]:
    chunk_size = max(1, min(int(replicates), MAX_MEMORY_SHOTS_PER_CIRCUIT // int(b_max)))
    return [
        (start, min(start + chunk_size, int(replicates)))
        for start in range(0, int(replicates), chunk_size)
    ]


def _raw_relpath_for_config(instance_id: str, config: dict) -> Path:
    if config["profile"] == "regime_probe":
        return regime_probe_raw_relpath(instance_id)
    if str(config.get("output_namespace", "pilot")) == "confirmatory":
        return confirmatory_raw_relpath(instance_id)
    return raw_relpath(instance_id)


def _graph_and_landscape_for_config(instance_id: str, config: dict):
    candidate_count = int(config["candidate_count"])
    depth = int(config["depth"])
    qubits = int(config["qubits"])
    graph_degree = int(config.get("graph_degree", 3))
    landscape = landscape_for_instance(
        instance_id,
        candidate_count=candidate_count,
        depth=depth,
        num_qubits=qubits,
        graph_degree=graph_degree,
        local_radius=float(config["local_radius"]),
        search_radius=float(config["search_radius"]),
        search_count=int(config["search_count"]),
    )
    graph = maxcut_graph_for_instance(instance_id, num_qubits=qubits, degree=graph_degree)
    return graph, landscape


def generate_instance_raw(staging: Path, instance_id: str, config: dict) -> dict[str, float]:
    """Run the expensive Aer primitive-scale generation for one declared instance."""

    if str(config.get("output_namespace", "pilot")) == "pilot":
        assert_pilot_instance(instance_id)
    elif instance_id not in CONFIRMATORY_INSTANCE_IDS:
        raise ValueError(f"confirmatory raw generation requires C001..C048; got {instance_id!r}")
    start = time.perf_counter()
    budgets = sorted(int(value) for value in config["budget_grid"])
    b_max = int(config.get("B_max", max(budgets)))
    if b_max != max(budgets):
        raise ValueError("B_max must equal max(budget_grid) for nested prefixes")
    replicates = int(config["replicates"])
    candidate_count = int(config["candidate_count"])
    depth = int(config["depth"])
    qubits = int(config["qubits"])
    graph_degree = int(config.get("graph_degree", 3))
    scales = np.asarray(config["zne_lambdas"], dtype=float)

    graph, landscape = _graph_and_landscape_for_config(instance_id, config)

    estimates = np.empty((replicates, len(scales), candidate_count, len(budgets)), dtype=float)
    for scale_idx, scale in enumerate(scales):
        p1 = min(float(ONE_QUBIT_DEPOLARIZING) * float(scale), 0.95)
        p2 = min(float(TWO_QUBIT_DEPOLARIZING) * float(scale), 0.95)
        noise_model = depolarizing_noise_model(p1=p1, p2=p2)
        circuits = []
        for row in landscape.angles:
            circuits.append(
                qaoa_maxcut_circuit(
                    graph,
                    depth=depth,
                    gammas=row[:depth],
                    betas=row[depth:],
                    measure=True,
                )
            )
        for chunk_start, chunk_end in _replicate_chunks(replicates, b_max):
            rng = make_rng(
                instance_id=instance_id,
                method=f"noise_scale_{scale:g}",
                budget=b_max,
                replicate_id=chunk_start,
                stream="gate0_pilot_generation",
            )
            seed = int(rng.integers(1, 2**31 - 1))
            simulator = AerSimulator(noise_model=noise_model, seed_simulator=seed)
            transpiled = transpile(circuits, simulator, seed_transpiler=seed)
            chunk_replicates = chunk_end - chunk_start
            result = simulator.run(
                transpiled,
                shots=b_max * chunk_replicates,
                memory=True,
            ).result()
            for candidate_idx in range(candidate_count):
                memory = result.get_memory(candidate_idx)
                for local_replicate in range(chunk_replicates):
                    replicate_id = chunk_start + local_replicate
                    start_idx = local_replicate * b_max
                    end_idx = start_idx + b_max
                    estimates[replicate_id, scale_idx, candidate_idx, :] = (
                        _prefix_objective_estimates(memory[start_idx:end_idx], graph, budgets)
                    )

    metadata = {
        "profile": config["profile"],
        "instance_id": instance_id,
        "pilot_instance_ids": config["pilot_instance_ids"],
        "confirmatory_instance_ids": (
            list(CONFIRMATORY_INSTANCE_IDS)
            if str(config.get("output_namespace", "pilot")) == "confirmatory"
            else config["confirmatory_instance_ids"]
        ),
        "depth": depth,
        "qubits": qubits,
        "graph_degree": graph_degree,
        "graph_seed": landscape.graph_seed,
        "x_star": landscape.x_star,
        "candidate_count": candidate_count,
        "replicates": replicates,
        "budget_grid": budgets,
        "B_max": b_max,
        "zne_lambdas": scales.tolist(),
        "objective": "minimize_negative_MaxCut_expectation",
    }
    if str(config.get("output_namespace", "pilot")) == "confirmatory":
        metadata["output_namespace"] = "confirmatory"
    _write_deterministic_npz(
        staging / _raw_relpath_for_config(instance_id, config),
        metadata_json=np.array(json.dumps(metadata, sort_keys=True)),
        instance_id=np.array(instance_id),
        budgets=np.asarray(budgets, dtype=np.int64),
        zne_lambdas=scales,
        angles=landscape.angles,
        ideal_values=landscape.ideal_values,
        x_star=np.array(landscape.x_star, dtype=np.int64),
        graph_edges=np.asarray(landscape.graph_edges, dtype=np.int64),
        primitive_objective_estimates=estimates,
    )
    return {"duration_seconds": time.perf_counter() - start}


def _metadata_dict(raw) -> dict:
    return json.loads(str(raw["metadata_json"].item()))


def _validate_raw_matches_config(raw, instance_id: str, config: dict) -> None:
    metadata = _metadata_dict(raw)
    expected = {
        "profile": config["profile"],
        "instance_id": instance_id,
        "candidate_count": int(config["candidate_count"]),
        "replicates": int(config["replicates"]),
        "budget_grid": sorted(int(value) for value in config["budget_grid"]),
        "B_max": int(config["B_max"]),
    }
    observed = {
        "profile": metadata.get("profile"),
        "instance_id": metadata.get("instance_id"),
        "candidate_count": int(metadata.get("candidate_count", -1)),
        "replicates": int(metadata.get("replicates", -1)),
        "budget_grid": [int(value) for value in metadata.get("budget_grid", [])],
        "B_max": int(metadata.get("B_max", -1)),
    }
    if observed != expected:
        raise ValueError(
            f"raw sample metadata mismatch for {instance_id}: observed={observed}, "
            f"expected={expected}"
        )
    expected_shape = (
        int(config["replicates"]),
        len(config["zne_lambdas"]),
        int(config["candidate_count"]),
        len(config["budget_grid"]),
    )
    actual_shape = tuple(raw["primitive_objective_estimates"].shape)
    if actual_shape != expected_shape:
        raise ValueError(
            f"raw sample shape mismatch for {instance_id}: {actual_shape} != {expected_shape}"
        )


def _covariance(samples: np.ndarray, *, shrinkage: bool) -> np.ndarray:
    arr = np.asarray(samples, dtype=float)
    if arr.ndim != 2:
        raise ValueError("samples must be a two-dimensional array")
    if arr.shape[0] < 2:
        raise ValueError("at least two samples are required for covariance")
    if arr.shape[1] == 1:
        return np.array([[float(np.var(arr[:, 0], ddof=1))]])
    if shrinkage and arr.shape[0] > arr.shape[1]:
        return nearest_psd(LedoitWolf().fit(arr).covariance_)
    return nearest_psd(np.cov(arr, rowvar=False, ddof=1))


def _criterion(delta: float, selector_changed: bool, bstar_gain: float, config: dict) -> str:
    gri_trigger = abs(float(delta)) > float(config["margin_threshold"])
    bstar_trigger = float(bstar_gain) > float(config["bstar_gain_threshold"])
    triggers = [gri_trigger, bool(selector_changed), bstar_trigger]
    if sum(triggers) > 1:
        return "multiple"
    if gri_trigger:
        return "gri_margin"
    if selector_changed:
        return "selector_change"
    if bstar_trigger:
        return "bstar_prediction_gain"
    return "none"


def empirical_decision_failure_rate(gap_samples: np.ndarray) -> float:
    """Return mean indicator that any residual gap is non-positive."""

    arr = np.asarray(gap_samples, dtype=float)
    if arr.ndim != 2:
        raise ValueError("gap_samples must have shape (replicates, gaps)")
    if arr.shape[0] == 0 or arr.shape[1] == 0:
        raise ValueError("gap_samples must be nonempty")
    return float(np.mean(np.any(arr <= 0.0, axis=1)))


def _method_gap_samples(
    primitive_objective_estimates: np.ndarray,
    ideal_values: np.ndarray,
    x_star: int,
    budget_idx: int,
    config: dict,
) -> dict[str, np.ndarray]:
    budgets_estimates = primitive_objective_estimates[:, :, :, budget_idx]
    competitor_indices = [idx for idx in range(len(ideal_values)) if idx != x_star]
    primitive_gaps = (
        budgets_estimates[:, :, competitor_indices] - budgets_estimates[:, :, [x_star]]
    )
    scales = np.asarray(config["zne_lambdas"], dtype=float)
    order = int(config["zne_order"])
    acc_coeffs = accuracy_zne_coeffs(scales, p=order)
    true_mu = ideal_values[competitor_indices] - ideal_values[x_star]
    mu_lower = np.maximum(true_mu, float(config["decision_zne_mu_floor"]))

    q_list = []
    for gap_idx in range(primitive_gaps.shape[2]):
        q_list.append(_covariance(primitive_gaps[:, :, gap_idx], shrinkage=False))
    A, rho = richardson_constraints(scales, p=order)
    decision_coeffs = decision_optimal_zne_coeffs(q_list, mu_lower, A, rho)

    methods = {
        "Raw": primitive_gaps[:, 0, :],
        "Accuracy-ZNE": np.einsum("s,rsd->rd", acc_coeffs, primitive_gaps),
        "Decision-ZNE": np.einsum("s,rsd->rd", decision_coeffs, primitive_gaps),
    }
    return {method: methods[method] for method in config["method_menu_core"]}


def analyze_gate0(output_root: Path, staging: Path, config: dict) -> pd.DataFrame:
    """Cheap, re-runnable Gate 0 analysis from frozen raw samples."""

    rows = []
    example_sigma_written = False
    for instance_id in config["instance_ids"]:
        raw = np.load(output_root / raw_relpath(instance_id), allow_pickle=False)
        _validate_raw_matches_config(raw, instance_id, config)
        budgets = [int(value) for value in raw["budgets"]]
        ideal_values = np.asarray(raw["ideal_values"], dtype=float)
        x_star = int(raw["x_star"])
        estimates = np.asarray(raw["primitive_objective_estimates"], dtype=float)
        for budget_idx, budget in enumerate(budgets):
            method_samples = _method_gap_samples(
                estimates,
                ideal_values,
                x_star,
                budget_idx,
                config,
            )
            full_risks: dict[str, float] = {}
            diag_risks: dict[str, float] = {}
            method_stats: dict[str, tuple[float, float, float]] = {}
            for method, gap_samples in method_samples.items():
                mu = np.mean(gap_samples, axis=0)
                sigma = _covariance(gap_samples, shrinkage=bool(config["use_ledoit_wolf"]))
                sigma_diag = np.diag(np.diag(sigma))
                full = gri_risk(mu, sigma, B=1.0)
                diag = gri_risk(mu, sigma_diag, B=1.0)
                full_risks[method] = full
                diag_risks[method] = diag
                method_stats[method] = (full, diag, abs(full - diag) * float(budget))
                if not example_sigma_written and method == config["method_menu_core"][0]:
                    sigma_path = staging / Path("pilot") / "gate0_example_sigma.csv"
                    sigma_path.parent.mkdir(parents=True, exist_ok=True)
                    pd.DataFrame(sigma).to_csv(sigma_path, index=False)
                    example_sigma_written = True

            selector_full = da_selector(full_risks, gri_valid=True)
            selector_diag = da_selector(diag_risks, gri_valid=True)
            selector_changed = selector_full != selector_diag
            for method in config["method_menu_core"]:
                full, diag, bstar_gain = method_stats[method]
                delta = full - diag
                criterion = _criterion(delta, selector_changed, bstar_gain, config)
                relevant = criterion != "none"
                rows.append(
                    {
                        "problem_cell": instance_id,
                        "method": method,
                        "budget": budget,
                        "gri_full": full,
                        "gri_diagonal": diag,
                        "delta_gri_full_minus_diagonal": delta,
                        "margin_threshold": float(config["margin_threshold"]),
                        "selector_full": selector_full,
                        "selector_diagonal": selector_diag,
                        "selector_changed": selector_changed,
                        "bstar_prediction_gain": bstar_gain,
                        "criterion_triggered": criterion,
                        "mechanism_relevant": relevant,
                        "gate0_status": "pass" if relevant else "fail",
                    }
                )
    df = pd.DataFrame(rows)
    out = staging / CSV_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    return df


def build_regime_probe_report(output_root: Path, staging: Path, config: dict) -> pd.DataFrame:
    """Write the non-canonical decision-critical regime diagnostic report."""

    rows = []
    for instance_id in config["instance_ids"]:
        raw = np.load(output_root / regime_probe_raw_relpath(instance_id), allow_pickle=False)
        _validate_raw_matches_config(raw, instance_id, config)
        budgets = [int(value) for value in raw["budgets"]]
        ideal_values = np.asarray(raw["ideal_values"], dtype=float)
        x_star = int(raw["x_star"])
        estimates = np.asarray(raw["primitive_objective_estimates"], dtype=float)
        for budget_idx, budget in enumerate(budgets):
            method_samples = _method_gap_samples(
                estimates,
                ideal_values,
                x_star,
                budget_idx,
                config,
            )
            full_risks: dict[str, float] = {}
            diag_risks: dict[str, float] = {}
            deltas: list[float] = []
            for method, gap_samples in method_samples.items():
                mu = np.mean(gap_samples, axis=0)
                sigma = _covariance(gap_samples, shrinkage=bool(config["use_ledoit_wolf"]))
                sigma_diag = np.diag(np.diag(sigma))
                full = gri_risk(mu, sigma, B=1.0)
                diag = gri_risk(mu, sigma_diag, B=1.0)
                full_risks[method] = full
                diag_risks[method] = diag
                deltas.append(full - diag)
            rows.append(
                {
                    "instance": instance_id,
                    "budget": budget,
                    "Raw_failure_rate_emp": empirical_decision_failure_rate(
                        method_samples["Raw"]
                    ),
                    "Raw_gri_full": full_risks["Raw"],
                    "max_delta_full_minus_diag": max(deltas, key=abs),
                    "selector_changed_any": da_selector(full_risks)
                    != da_selector(diag_risks),
                }
            )

    df = pd.DataFrame(rows)
    regime_ok = bool(
        (
            (df["Raw_failure_rate_emp"] >= 0.15)
            & (df["Raw_failure_rate_emp"] <= 0.70)
        ).any()
    )
    if regime_ok:
        adjustment = "none"
    else:
        max_failure = float(df["Raw_failure_rate_emp"].max())
        if max_failure < 0.15:
            adjustment = "bajar local_radius, subir ruido, o bajar budget floor"
        else:
            adjustment = "subir local_radius, bajar ruido, o subir budget floor"

    lines = [
        "# Gate 0 Regime Probe",
        "",
        "Diagnostic only: not canonical, not part of verify/reference.",
        "",
        (
            f"- profile: {config['profile']}; instances: {config['instance_ids']}; "
            f"candidate_count: {config['candidate_count']}; replicates: {config['replicates']}; "
            f"budget_grid: {config['budget_grid']}"
        ),
        "",
        "| instance | budget | Raw_failure_rate_emp | Raw_gri_full | max_delta_full_minus_diag | selector_changed_any |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in df.to_dict(orient="records"):
        lines.append(
            "| {instance} | {budget} | {Raw_failure_rate_emp:.6f} | "
            "{Raw_gri_full:.6f} | {max_delta_full_minus_diag:.6e} | "
            "{selector_changed_any} |".format(**row)
        )
    lines.extend(
        [
            "",
            f"- regime_ok: {regime_ok}",
            f"- adjustment_if_false: {adjustment}",
        ]
    )
    out = staging / REGIME_PROBE_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return df


def run_generation(output_root: Path, profile: str = "smoke") -> list[Path]:
    config = load_config(profile)
    produced = []
    for instance_id in config["instance_ids"]:
        generate_instance_raw(output_root, instance_id, config)
        rel = _raw_relpath_for_config(instance_id, config)
        produced.append(output_root / rel)
    return produced


def run_analysis(output_root: Path, profile: str = "smoke") -> pd.DataFrame:
    config = load_config(profile)
    return analyze_gate0(output_root, output_root, config)


def run(output_root: Path = DEFAULT_OUTPUT_ROOT, profile: str = "smoke") -> pd.DataFrame:
    if profile == "regime_probe":
        config = load_config(profile)
        run_generation(output_root, profile=profile)
        return build_regime_probe_report(output_root, output_root, config)
    if bool(load_config(profile).get("raw_generation_only", False)):
        run_generation(output_root, profile=profile)
        return pd.DataFrame()
    run_generation(output_root, profile=profile)
    return run_analysis(output_root, profile=profile)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--profile", default="smoke")
    args = parser.parse_args(argv)
    run(Path(args.output).resolve(), profile=args.profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
