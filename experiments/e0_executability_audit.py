from __future__ import annotations

import argparse
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
CSV_NAME = "executability_budget_table.csv"
MD_NAME = "executability_budget_table.md"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_configs() -> tuple[dict, dict]:
    return load_yaml(PHASE0_CONFIG), load_yaml(CDEV_CONFIG)


def benchmark_qaoa_cell(config: dict) -> dict[int, dict[str, float]]:
    """Measure median transpile+run wall seconds for each budget in the grid."""

    cell = config["benchmark_cell"]
    graph = maxcut_graph(
        num_qubits=int(cell["qubits"]),
        degree=int(cell.get("graph_degree", 3)),
        seed=int(cell.get("graph_seed", 1)),
    )
    depth = int(cell["depth"])
    repetitions = int(config.get("benchmark_repetitions", 3))
    noise_model = depolarizing_noise_model()
    timings: dict[int, dict[str, float]] = {}
    for budget in config["budget_grid"]:
        budget = int(budget)
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
        simulator.run(transpiled, shots=budget).result()
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


def build_budget_table(
    config: dict,
    cdev_config: dict,
    timings: dict[int, dict[str, float]],
    batch_timing: dict[str, float | int | list[float]],
) -> tuple[pd.DataFrame, dict]:
    grid = [int(v) for v in config["budget_grid"]]
    t_by_budget = {budget: float(timings[budget]["median_seconds"]) for budget in grid}
    sum_grid = float(sum(grid))
    b_max = max(grid)
    t_batched = float(batch_timing["amortized_seconds_per_circuit"])
    methods = len(config["method_menu_core"])
    e1_n = float(config["power_mins"]["E1"])
    e2_n = float(config["power_mins"]["E2"])
    candidates = float(config["candidate_count"])
    rounds = float(config["dynamic_rounds"])
    per_round = float(config["dynamic_candidates_per_round"])
    sigma_reps = float(config["e3_sigma_hat_replicates"])
    ceiling = float(config["max_wall_hours_per_sim_block"])

    e1_multiplier = e1_n * candidates * methods
    e2_multiplier = e2_n * rounds * per_round * methods
    e3_multiplier = methods * sigma_reps
    cdev_circuits = float(cdev_config["characterization_circuits"])
    cdev_shots_per_circuit = float(cdev_config["shots_per_circuit"])
    cdev_epochs = float(cdev_config["epochs"])

    def sim_decision(wall_hours: float) -> str:
        return "go" if wall_hours <= ceiling else "no-go"

    def naive_wall_from_grid(multiplier: float) -> float:
        return float(sum(multiplier * t_by_budget[budget] for budget in grid) / 3600.0)

    def batched_wall(n_evals: float) -> float:
        return float(n_evals * t_batched / 3600.0)

    e1_wall = batched_wall(e1_multiplier)
    e2_wall = batched_wall(e2_multiplier)
    e3_wall = batched_wall(e3_multiplier)
    # Sparse-PL characterization is also batched in the execution model; use the
    # batched amortized per-circuit time (measured at B_max, conservative for the
    # smaller characterization budget).
    sparse_wall = float(cdev_circuits * cdev_epochs * t_batched / 3600.0)

    hardware_flags = config.get("hardware_schedulable", {})
    sigma_hardware_decision = hardware_decision(hardware_flags.get("sigma_microcell"))
    ordering_hardware_decision = hardware_decision(hardware_flags.get("three_budget_ordering"))

    # Explicit order-of-magnitude hardware multipliers. These are schedulability
    # estimates only; no real hardware job is submitted in Phase 0.
    hardware_sigma_gaps = 3.0
    hardware_sigma_replicates = 200.0
    hardware_sigma_shots = 4096.0
    hardware_ordering_budgets = 3.0
    hardware_ordering_batches = 25.0
    hardware_ordering_shots = 4096.0
    scaling_sizes = 3.0
    scaling_budgets = 3.0
    scaling_candidates = 5.0
    scaling_shots = 1024.0
    scaling_evals = scaling_sizes * scaling_budgets * scaling_candidates * methods
    scaling_wall = batched_wall(scaling_evals)

    rows = [
        {
            "block": "E1_static",
            "primary_unit": "paired_decisions",
            "N_minimum": e1_n,
            "estimated_shots": e1_multiplier * b_max,
            "wall_hours": e1_wall,
            "backend_or_resource": "sim/Aer",
            "risk": "sim wall clock exceeds ceiling" if e1_wall > ceiling else "within sim ceiling",
            "decision": sim_decision(e1_wall),
        },
        {
            "block": "E2_dynamic",
            "primary_unit": "trajectories",
            "N_minimum": e2_n,
            "estimated_shots": e2_multiplier * b_max,
            "wall_hours": e2_wall,
            "backend_or_resource": "sim/Aer",
            "risk": "sim wall clock exceeds ceiling" if e2_wall > ceiling else "within sim ceiling",
            "decision": sim_decision(e2_wall),
        },
        {
            "block": "E3_pullback",
            "primary_unit": "Sigma_hat_replicates",
            "N_minimum": sigma_reps,
            "estimated_shots": e3_multiplier * b_max,
            "wall_hours": e3_wall,
            "backend_or_resource": "sim/Aer",
            "risk": "sim wall clock exceeds ceiling" if e3_wall > ceiling else "within sim ceiling",
            "decision": sim_decision(e3_wall),
        },
        {
            "block": "Sparse_PL_Cdev",
            "primary_unit": "characterization_circuits",
            "N_minimum": cdev_circuits,
            "estimated_shots": cdev_circuits * cdev_shots_per_circuit * cdev_epochs,
            "wall_hours": sparse_wall,
            "backend_or_resource": "sim/Aer",
            "risk": "sim wall clock exceeds ceiling" if sparse_wall > ceiling else "within sim ceiling",
            "decision": sim_decision(sparse_wall),
        },
        {
            "block": "Hardware_Sigma_microcell",
            "primary_unit": "schedulability_only",
            "N_minimum": hardware_sigma_replicates,
            "estimated_shots": hardware_sigma_gaps * methods * hardware_sigma_replicates * hardware_sigma_shots,
            "wall_hours": 0.0,
            "backend_or_resource": "IBM_hardware",
            "risk": "schedulability only; no hardware submitted",
            "decision": sigma_hardware_decision,
        },
        {
            "block": "Hardware_3budget_ordering",
            "primary_unit": "schedulability_only",
            "N_minimum": hardware_ordering_batches,
            "estimated_shots": hardware_ordering_budgets * hardware_ordering_batches * hardware_ordering_shots,
            "wall_hours": 0.0,
            "backend_or_resource": "IBM_hardware",
            "risk": "schedulability only; no hardware submitted",
            "decision": ordering_hardware_decision,
        },
        {
            "block": "Scaling_4_6_8",
            "primary_unit": "trend_only",
            "N_minimum": scaling_sizes,
            "estimated_shots": scaling_sizes * scaling_budgets * scaling_candidates * methods * scaling_shots,
            "wall_hours": scaling_wall,
            "backend_or_resource": "sim/Aer",
            "risk": "trend only small scaling probe",
            "decision": sim_decision(scaling_wall),
        },
    ]
    table = pd.DataFrame(rows)
    decision_by_block = {row["block"]: row["decision"] for row in rows}
    prxq_go = (
        decision_by_block["E1_static"] == "go"
        and decision_by_block["E2_dynamic"] == "go"
        and decision_by_block["E3_pullback"] == "go"
        and decision_by_block["Hardware_Sigma_microcell"] in {"go", "conditional"}
    )
    summary = {
        "global_gate": "go" if prxq_go else "no-go",
        "recommended_track": "PRXQ" if prxq_go else "Quantum_or_QEM_methods",
        "seconds_per_shot": {
            str(budget): timings[budget]["seconds_per_shot"] for budget in grid
        },
        "timings": timings,
        "batch_timing": batch_timing,
        "execution_model": {
            "B_max": b_max,
            "batch_size": int(batch_timing["batch_size"]),
            "amortized_seconds_per_circuit": t_batched,
        },
        "naive_upper_bound": {
            "E1_static": {
                "estimated_shots": e1_multiplier * sum_grid,
                "wall_hours": naive_wall_from_grid(e1_multiplier),
            },
            "E2_dynamic": {
                "estimated_shots": e2_multiplier * sum_grid,
                "wall_hours": naive_wall_from_grid(e2_multiplier),
            },
        },
        "multipliers": {
            "E1_static": "1500 * 25 * 3 evaluations * B_max shots",
            "E2_dynamic": "1200 * 20 * 5 * 3 evaluations * B_max shots",
            "E3_pullback": "3 methods * 200 evaluations * B_max shots",
            "Sparse_PL_Cdev": "200 * 4096 * 1",
            "Hardware_Sigma_microcell": "3 gaps * 3 methods * 200 replicates * 4096 shots",
            "Hardware_3budget_ordering": "3 budgets * 25 batches * 4096 shots",
            "Scaling_4_6_8": "3 sizes * 3 budgets * 5 candidates * 3 methods * 1024 shots; batched wall time",
        },
    }
    return table, summary


def render_markdown(table: pd.DataFrame, summary: dict, config: dict) -> str:
    execution = summary["execution_model"]
    lines = [
        "# Phase 0 Executability Audit",
        "",
        "This is a feasibility order-of-magnitude gate, not confirmatory accounting.",
        "",
        "## Benchmark Cell",
        "",
        (
            f"- Qubits: {config['benchmark_cell']['qubits']}; "
            f"QAOA-MaxCut depth: {config['benchmark_cell']['depth']}; "
            f"budget grid: {config['budget_grid']}"
        ),
        f"- Max wall hours per sim block: {config['max_wall_hours_per_sim_block']}",
        "",
        "## Execution Model Assumptions",
        "",
        (
            f"- Nested budget subsampling: each candidate evaluation runs once at "
            f"B_max={execution['B_max']}; lower budgets reuse prefixes/common random numbers. "
            "Shot cost is proportional to B_max, not sum(grid)."
        ),
        (
            f"- Circuit batching: K_batch={execution['batch_size']} candidate circuits are "
            "submitted in one AerSimulator.run([...]) call."
        ),
        (
            "- Refined simulation wall time uses the measured batched amortized time per circuit; "
            "timings are machine-dependent and warning-only."
        ),
        (
            "- Sparse-PL characterization is also batched and uses the conservative per-circuit "
            "time measured at B_max, although its characterization budget is smaller."
        ),
        "",
        "## Measured Single-Circuit Timing",
        "",
        "| shots | median_seconds | seconds_per_shot |",
        "|---:|---:|---:|",
    ]
    timings = summary["timings"]
    for budget in sorted(int(v) for v in timings):
        item = timings[budget]
        lines.append(
            f"| {budget} | {item['median_seconds']:.6f} | {item['seconds_per_shot']:.9f} |"
        )
    batch = summary["batch_timing"]
    lines.extend(
        [
            "",
            "## Measured Batched Timing",
            "",
            "| shots | K_batch | median_total_seconds | amortized_seconds_per_circuit |",
            "|---:|---:|---:|---:|",
            (
                f"| {int(batch['budget'])} | {int(batch['batch_size'])} | "
                f"{float(batch['median_total_seconds']):.6f} | "
                f"{float(batch['amortized_seconds_per_circuit']):.9f} |"
            ),
            "",
            "## Refined vs Naive Upper Bound",
            "",
            "The naive upper bound repeats every evaluation at every grid budget and uses one Aer call per circuit.",
            "",
            "| block | refined_estimated_shots | refined_wall_hours | naive_estimated_shots | naive_wall_hours |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    by_block = table.set_index("block")
    for block in ["E1_static", "E2_dynamic"]:
        refined = by_block.loc[block]
        naive = summary["naive_upper_bound"][block]
        lines.append(
            f"| {block} | {float(refined['estimated_shots']):.0f} | "
            f"{float(refined['wall_hours']):.6f} | "
            f"{float(naive['estimated_shots']):.0f} | {float(naive['wall_hours']):.6f} |"
        )
    lines.extend(
        [
            "",
            "## Cost Multipliers",
            "",
        ]
    )
    for block, formula in summary["multipliers"].items():
        lines.append(f"- {block}: `{formula}`")
    lines.extend(
        [
            "",
            "## Executability Budget Table",
            "",
            "| block | primary_unit | N_minimum | estimated_shots | wall_hours | backend_or_resource | risk | decision |",
            "|---|---|---:|---:|---:|---|---|---|",
        ]
    )
    for row in table.to_dict(orient="records"):
        lines.append(
            "| {block} | {primary_unit} | {N_minimum:.0f} | {estimated_shots:.0f} | "
            "{wall_hours:.6f} | {backend_or_resource} | {risk} | {decision} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Gate Global",
            "",
            f"- global_gate: {summary['global_gate']}",
            f"- recommended_track: {summary['recommended_track']}",
            "- PRXQ gate rule: E1, E2, and E3 must be go, and Hardware-Sigma must be go or conditional-pending.",
        ]
    )
    return "\n".join(lines) + "\n"


def run(output_root: Path = DEFAULT_OUTPUT_ROOT) -> tuple[pd.DataFrame, dict]:
    config, cdev_config = load_configs()
    timings = benchmark_qaoa_cell(config)
    batch_timing = benchmark_qaoa_batch(config)
    table, summary = build_budget_table(config, cdev_config, timings, batch_timing)
    pilot_dir = output_root / "pilot"
    pilot_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(pilot_dir / CSV_NAME, index=False)
    (pilot_dir / MD_NAME).write_text(render_markdown(table, summary, config), encoding="utf-8")
    return table, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args(argv)
    run(Path(args.output).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
