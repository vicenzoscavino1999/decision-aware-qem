from __future__ import annotations

import argparse
import json
import platform
import sys
import os
import statistics
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from qiskit import transpile
from qiskit_aer import AerSimulator

from daqem.noise import depolarizing_noise_model
from daqem.qaoa import (
    default_angles,
    maxcut_graph,
    qaoa_maxcut_circuit,
    qaoa_maxcut_expectation_aer,
)
from daqem.rng import make_rng


REPO_ROOT = Path(__file__).resolve().parents[1]
PHASE0_CONFIG = REPO_ROOT / "reproducibility" / "config" / "phase0_executability.yaml"
CDEV_CONFIG = REPO_ROOT / "reproducibility" / "config" / "cdev_learning.yaml"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "results"
CSV_NAME = "executability_diagnostic.csv"
MD_NAME = "executability_diagnostic.md"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_configs() -> tuple[dict, dict]:
    from experiments.gate0_pilot_full_vs_diagonal import load_config as gate_config
    from experiments.e2_dynamic_batch_candidate_optimizer import load_config as dynamic_config
    from experiments.cdev_learned_arm import load_config as learning_config
    config = load_yaml(PHASE0_CONFIG)
    config["static_workload"] = gate_config(config["static_profile"])
    config["pilot_workload"] = gate_config(config["pilot_profile"])
    config["dynamic_workload"] = dynamic_config(config["dynamic_profile"])
    return config, learning_config(config["cdev_profile"])


def benchmark_qaoa_cell(config: dict) -> dict[int, dict[str, float]]:
    """Measure median transpile+run wall seconds for each budget in the grid."""

    cell = config["benchmark_cell"]
    graph = maxcut_graph(
        num_qubits=int(cell["qubits"]),
        degree=int(cell.get("graph_degree", 3)),
        seed=int(cell.get("graph_seed", 1)),
    )
    depth = int(cell["depth"])
    repetitions = positive_int(config.get("benchmark_repetitions", 3), "benchmark_repetitions")
    noise_model = depolarizing_noise_model()
    timings: dict[int, dict[str, float]] = {}
    for budget in config["budget_grid"]:
        budget = positive_int(budget, "budget")
        samples = []
        for rep in range(repetitions):
            start = time.perf_counter()
            qaoa_maxcut_expectation_aer(
                graph,
                depth=depth,
                shots=budget,
                noise_model=noise_model,
                instance_id=f"phase0_{cell['qubits']}q_depth{depth}",
                method="Raw",
                replicate_id=rep,
                stream="executability",
            )
            samples.append(time.perf_counter() - start)
        median_seconds = float(statistics.median(samples))
        timings[budget] = {
            "median_seconds": median_seconds,
            "seconds_per_shot": median_seconds / float(budget),
            "samples_seconds": samples,
        }
    return timings


def benchmark_qaoa_batch(config: dict) -> dict[str, float | int | list[float]]:
    """Measure a realistic batch of candidate circuits at the maximum budget."""

    cell = config["benchmark_cell"]
    graph = maxcut_graph(
        num_qubits=int(cell["qubits"]),
        degree=int(cell.get("graph_degree", 3)),
        seed=int(cell.get("graph_seed", 1)),
    )
    depth = int(cell["depth"])
    budget = max(int(value) for value in config["budget_grid"])
    batch_size = int(config.get("batch_size", 50))
    repetitions = int(config.get("benchmark_repetitions", 3))
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if repetitions <= 0:
        raise ValueError("benchmark_repetitions must be positive")

    base_gammas, base_betas = default_angles(depth)
    noise_model = depolarizing_noise_model()
    samples: list[float] = []
    for rep in range(repetitions):
        rng = make_rng(
            instance_id=f"phase0_{cell['qubits']}q_depth{depth}",
            method="batched_candidates",
            budget=budget,
            replicate_id=rep,
            stream="executability_batch",
        )
        seed = int(rng.integers(1, 2**31 - 1))
        start = time.perf_counter()
        simulator = AerSimulator(noise_model=noise_model, seed_simulator=seed)
        circuits = []
        for _ in range(batch_size):
            gammas = base_gammas + rng.uniform(-0.05, 0.05, size=depth)
            betas = base_betas + rng.uniform(-0.05, 0.05, size=depth)
            circuits.append(
                qaoa_maxcut_circuit(
                    graph,
                    depth=depth,
                    gammas=gammas,
                    betas=betas,
                    measure=True,
                )
            )
        transpiled = transpile(circuits, simulator, seed_transpiler=seed)
        simulator.run(transpiled, shots=budget, memory=True).result()
        samples.append(time.perf_counter() - start)

    median_total = float(statistics.median(samples))
    return {
        "batch_size": batch_size,
        "budget": budget,
        "median_total_seconds": median_total,
        "amortized_seconds_per_circuit": median_total / float(batch_size),
        "samples_seconds": samples,
    }


def hardware_decision(flag) -> str:
    if flag is None:
        return "conditional"
    if isinstance(flag, (bool, np.bool_)):
        return "go" if bool(flag) else "no-go"
    if isinstance(flag, str):
        normalized = flag.strip().lower()
        if normalized in {"true", "yes", "go", "schedulable"}:
            return "go"
        if normalized in {"false", "no", "no-go", "unschedulable"}:
            return "no-go"
    raise ValueError(f"invalid hardware_schedulable flag: {flag!r}")


def positive_int(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


def primitive_workload(config, *, dynamic=False):
    """Actual acquisition count, shared across methods and nested budgets.

    E2's proposal is updated from Raw at B_max, independently of the selectors
    and lower-budget decisions. This reuse is specific to that implemented task.
    """
    ids = config["instance_ids"]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("instance IDs must be nonempty and unique")
    budgets = [positive_int(b, "budget") for b in config["budget_grid"]]
    if not budgets or len(set(budgets)) != len(budgets) or config["B_max"] != max(budgets):
        raise ValueError("B_max must match the unique positive budget grid")
    scales = np.asarray(config["zne_lambdas"], dtype=float)
    if scales.ndim != 1 or not len(scales) or not np.isfinite(scales).all() or np.any(scales <= 0) or len(set(scales)) != len(scales):
        raise ValueError("scales must be distinct finite positive numbers")
    replicates = positive_int(config["trajectories" if dynamic else "replicates"], "replicates")
    candidates = positive_int(config["candidates_per_round" if dynamic else "candidate_count"], "candidates")
    rounds = positive_int(config["max_rounds"], "max_rounds") if dynamic else 1
    circuits = len(ids) * replicates * rounds * candidates * len(scales)
    return dict(instances=len(ids), replicates_per_instance=replicates, rounds=rounds,
        candidates=candidates, scales=len(scales), B_max=max(budgets), circuits=circuits,
        shots=circuits * max(budgets))


def characterization_workload(cdev_config):
    from experiments.cdev_learned_arm import build_generator_basis
    generators = build_generator_basis(cdev_config)
    depths = cdev_config["characterization_depths"]
    if not depths or len(set(depths)) != len(depths):
        raise ValueError("characterization depths must be nonempty and unique")
    for d in depths: positive_int(d, "characterization depth")
    repeats = positive_int(cdev_config["pauli_twirls"], "identical repeats")
    shots = positive_int(cdev_config["shots_per_circuit"], "shots_per_circuit")
    circuits = len(generators) * len(depths) * repeats
    if circuits < 1: raise ValueError("characterization basis must be nonempty")
    return dict(basis_labels=len(generators), depths=len(depths), identical_repeats=repeats,
        circuits=circuits, shots_per_circuit=shots, shots=circuits*shots,
        learning_runs=1, model_scope="uniform_two_parameter_depolarizing_channel")


def build_budget_table(config, cdev_config, timings, batch_timing):
    grid = [positive_int(b, "benchmark budget") for b in config["budget_grid"]]
    if not grid or len(set(grid)) != len(grid): raise ValueError("invalid benchmark grid")
    seconds = float(batch_timing["amortized_seconds_per_circuit"])
    if not np.isfinite(seconds) or seconds <= 0: raise ValueError("batch timing must be positive")
    if int(batch_timing["budget"]) != max(grid): raise ValueError("benchmark budget mismatch")
    ceiling = float(config["max_wall_hours_per_sim_block"])
    if not np.isfinite(ceiling) or ceiling < 0: raise ValueError("invalid wall ceiling")
    workloads = {
        "E1_static": primitive_workload(config["static_workload"]),
        "E2_dynamic": primitive_workload(config["dynamic_workload"], dynamic=True),
        "Pilot_shared": primitive_workload(config["pilot_workload"]),
        "Uniform_Cdev": characterization_workload(cdev_config),
    }
    rows = []
    for block, work in workloads.items():
        # Only a QAOA proxy at the measured B_max is reported. Characterization
        # uses different circuits; it has no runtime estimate from this benchmark.
        source = {"E1_static": "static_workload", "E2_dynamic": "dynamic_workload",
                  "Pilot_shared": "pilot_workload"}.get(block)
        comparable = source is not None
        if comparable:
            cell = config["benchmark_cell"]; experiment = config[source]
            comparable = (work["B_max"] == int(batch_timing["budget"]) and
                all(experiment[k] == cell[k] for k in ("qubits", "depth", "graph_degree")))
        proxy = work["circuits"] * seconds / 3600 if comparable else None
        rows.append(dict(block=block, acquisition_circuits=work["circuits"],
            estimated_shots=work["shots"], wall_hours_proxy=proxy,
            timing_status="single_worker_QAOA_proxy" if comparable else "not_measured",
            proxy_exceeds_ceiling=(proxy > ceiling) if proxy is not None else None,
            decision="conditional"))
    rows.append(dict(block="E3_pullback", acquisition_circuits=0, estimated_shots=0,
        wall_hours_proxy=None, timing_status="reuses_E1_raw_analysis_time_not_measured",
        proxy_exceeds_ceiling=None, decision="conditional"))
    flags=config.get("hardware_schedulable", {})
    summary = dict(schema_version=2, global_gate="conditional", workloads=workloads,
        cost_scope="acquisition_for_implemented_profiles_not_per_method_deployment_cost",
        E3_scope="E1 raw reused; analytic predictions and postprocessing consume time but no shots",
        nested_reuse="static prefixes; E2 common Raw_Bmax proposal for all budgets and selectors",
        timing_scope="proxy only: one graph, base noise, one worker; excludes parallel speedup, memory extraction, numerical analysis and differences between noise scales",
        timings=timings, batch_timing=batch_timing,
        unresolved_blocks={
            "Hardware_Sigma_microcell":dict(estimated_shots=None,wall_hours=None,schedulability=hardware_decision(flags.get("sigma_microcell"))),
            "Hardware_3budget_ordering":dict(estimated_shots=None,wall_hours=None,schedulability=hardware_decision(flags.get("three_budget_ordering"))),
            "Scaling_4_6_8":dict(estimated_shots=None,wall_hours=None,reason="no executable profile connected to this diagnostic")},
        unresolved_scope="use the separately audited hardware archive/runner; no invented hardware cost or runtime",
        journal_recommendation=None)
    return pd.DataFrame(rows), summary


def render_markdown(table, summary, config):
    lines = ["# Executability diagnostic", "",
        "Counts follow the executable profiles. Runtime values are a single-worker QAOA proxy, not a campaign ETA or a publication gate.", "",
        "E1 and E3 share raw data. E2 shares the Raw-at-B_max proposal and shot prefixes across budgets and selectors.", "",
        "Characterization is one uniform two-parameter learning run. Hardware and unconfigured scaling costs remain unknown.", "",
        "| block | acquisition circuits | shots | runtime proxy (hours) | timing scope |", "|---|---:|---:|---:|---|"]
    for row in table.to_dict(orient="records"):
        proxy = row["wall_hours_proxy"]
        shown = "not measured" if pd.isna(proxy) else f"{proxy:.6g}"
        lines.append(f"| {row['block']} | {row['acquisition_circuits']} | {row['estimated_shots']} | {shown} | {row['timing_status']} |")
    lines.extend(["", summary["timing_scope"], "", "The JSON file records resolved configurations, all timing samples and unknown quantities as null."])
    return "\n".join(lines) + "\n"


def run(output_root: Path = DEFAULT_OUTPUT_ROOT):
    if any((output_root / "pilot" / name).exists() for name in (CSV_NAME, MD_NAME, "executability_diagnostic.json")):
        raise FileExistsError("Executability evidence exists; use a new output directory")
    config, cdev_config = load_configs()
    # Validate workloads before spending time on the benchmark.
    primitive_workload(config["static_workload"])
    primitive_workload(config["dynamic_workload"], dynamic=True)
    primitive_workload(config["pilot_workload"])
    characterization_workload(cdev_config)
    timings = benchmark_qaoa_cell(config)
    batch_timing = benchmark_qaoa_batch(config)
    table, summary = build_budget_table(config, cdev_config, timings, batch_timing)
    summary["resolved_config"] = config
    summary["resolved_cdev_config"] = cdev_config
    summary["environment"] = dict(python=sys.version, platform=platform.platform(),
        threads={k:os.environ.get(k) for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS")})
    summary["rows"] = json.loads(table.to_json(orient="records"))
    pilot_dir = output_root / "pilot"; pilot_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(pilot_dir / CSV_NAME, index=False)
    (pilot_dir / MD_NAME).write_text(render_markdown(table, summary, config), encoding="utf-8")
    (pilot_dir / "executability_diagnostic.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    return table, summary


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument("--output",default=str(DEFAULT_OUTPUT_ROOT))
    args=parser.parse_args(argv);run(Path(args.output).resolve());return 0


if __name__ == "__main__":
    raise SystemExit(main())
