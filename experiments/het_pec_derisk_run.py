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

import experiments.a3_pullback_frontier as a3
from daqem.candidates import build_candidate_landscape_for_graph
from daqem.gap_kernel import nearest_psd
from daqem.pec import (
    HET_DERISK_CONFIG_PATH,
    heterogeneous_circuit_gamma,
    heterogeneous_depolarizing_noise_model,
    heterogeneous_noise_model_from_config,
    load_het_pec_derisk_config,
)
from daqem.qaoa import default_angles
from daqem.risk import gri_risk


OUTPUT_DIR = REPO_ROOT / "results" / "het_pec_derisk"
PRIMARY_INSTANCE_ID = "HET_PEC_DERISK_P0"


def _edges(graph) -> tuple[tuple[int, int], ...]:
    return tuple(sorted(tuple(sorted((int(i), int(j)))) for i, j in graph.edges()))


def _mean_abs_offdiag_corr(sigma: np.ndarray) -> float:
    diag = np.sqrt(np.maximum(np.diag(sigma), 0.0))
    denom = np.outer(diag, diag)
    corr = np.divide(sigma, denom, out=np.zeros_like(sigma), where=denom > 0.0)
    if corr.shape[0] < 2:
        return 0.0
    mask = ~np.eye(corr.shape[0], dtype=bool)
    return float(np.mean(np.abs(corr[mask])))


def _primitive_moments_on_locked_graph(
    *,
    instance_id: str,
    graph,
    gate0_config: dict[str, Any],
    noise_model_factory,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, bool]:
    """Call A3 moment code on the preregistered graph without editing frozen modules."""

    channel_edges = _edges(graph)
    a3_graph = graph.copy()
    graph_match = channel_edges == _edges(a3_graph)
    if not graph_match:
        raise ValueError("heterogeneous channel graph and A3 graph do not match")

    original_landscape_for_instance = a3.landscape_for_instance
    original_maxcut_graph_for_instance = a3.maxcut_graph_for_instance

    def locked_landscape_for_instance(
        requested_instance_id: str,
        *,
        candidate_count: int = 25,
        depth: int = 2,
        num_qubits: int = 10,
        graph_degree: int = 3,
        local_radius: float = 0.16,
        search_radius: float = 0.55,
        search_count: int | None = None,
    ):
        if int(num_qubits) != graph.number_of_nodes():
            raise ValueError("A3 requested a graph with a different number of qubits")
        return build_candidate_landscape_for_graph(
            requested_instance_id,
            graph,
            candidate_count=int(candidate_count),
            depth=int(depth),
            local_radius=float(local_radius),
            search_radius=float(search_radius),
            search_count=None if search_count is None else int(search_count),
        )

    def locked_maxcut_graph_for_instance(
        requested_instance_id: str,
        *,
        num_qubits: int = 10,
        degree: int = 3,
    ):
        if int(num_qubits) != graph.number_of_nodes():
            raise ValueError("A3 requested a graph with a different number of qubits")
        if int(degree) != int(gate0_config["graph_degree"]):
            raise ValueError("A3 requested a graph with a different degree")
        return graph.copy()

    a3.landscape_for_instance = locked_landscape_for_instance
    a3.maxcut_graph_for_instance = locked_maxcut_graph_for_instance
    try:
        moments = a3._primitive_objective_moments(
            instance_id=instance_id,
            gate0_config=gate0_config,
            noise_model_factory=noise_model_factory,
        )
    finally:
        a3.landscape_for_instance = original_landscape_for_instance
        a3.maxcut_graph_for_instance = original_maxcut_graph_for_instance
    return (*moments, graph_match)


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


def run_derisk() -> dict[str, Any]:
    config = load_het_pec_derisk_config(HET_DERISK_CONFIG_PATH)
    graph, p1_by_qubit, p2_by_edge, _ = heterogeneous_noise_model_from_config(config)
    primary = config["primary_cell"]
    channel = config["heterogeneous_channel"]
    gate0_config = dict(a3.load_gate0_config("full"))
    gate0_config["candidate_count"] = int(primary["candidate_count"])
    gate0_config["budget_grid"] = [int(budget) for budget in primary["budget_grid"]]
    gate0_config["B_max"] = max(gate0_config["budget_grid"])

    def noise_model_factory(scale_idx: int, scale: float):
        # Raw-vs-PEC de-risk uses the lambda=1 block. A3's primitive layout still
        # has the frozen three-scale shape; the same locked channel is returned
        # for other scale slots, which are unused by the Raw gap map.
        return heterogeneous_depolarizing_noise_model(
            p1_by_qubit=p1_by_qubit,
            p2_by_edge=p2_by_edge,
            one_qubit_gates=channel["p1_per_qubit"]["applies_to_gates"],
            two_qubit_gates=channel["p2_per_edge"]["applies_to_gates"],
        )

    means_het, variances_het, ideal_values, x_star_arr, graph_match = (
        _primitive_moments_on_locked_graph(
            instance_id=PRIMARY_INSTANCE_ID,
            graph=graph,
            gate0_config=gate0_config,
            noise_model_factory=noise_model_factory,
        )
    )
    x_star = int(x_star_arr)
    candidate_count = len(ideal_values)
    competitors = [idx for idx in range(candidate_count) if idx != x_star]
    mu_raw = means_het[0, competitors] - float(means_het[0, x_star])
    mu_ideal = np.asarray(ideal_values, dtype=float)[competitors] - float(ideal_values[x_star])
    cdev_diag_het = np.asarray(variances_het, dtype=float).reshape(-1)
    gap_map_raw = a3._gap_map(np.array([1.0, 0.0, 0.0]), candidate_count, x_star)
    sigma_unit = nearest_psd((gap_map_raw * cdev_diag_het) @ gap_map_raw.T)

    depth = int(primary["depth"])
    gammas, betas = default_angles(depth)
    gamma_het = heterogeneous_circuit_gamma(
        graph,
        depth=depth,
        gammas=gammas,
        betas=betas,
        p1_by_qubit=p1_by_qubit,
        p2_by_edge=p2_by_edge,
    )
    gamma_squared = float(gamma_het * gamma_het)

    budgets = [int(budget) for budget in primary["budget_grid"]]
    rows = []
    for budget in budgets:
        raw_risk = float(gri_risk(mu_raw, sigma_unit, B=budget))
        pec_risk = float(gri_risk(mu_ideal, gamma_squared * sigma_unit, B=budget))
        delta = raw_risk - pec_risk
        relative_savings = None if raw_risk <= 0.0 else float(delta / raw_risk)
        rho_gap_noise = None if relative_savings is None else float(relative_savings / 0.20)
        rows.append(
            {
                "budget": budget,
                "GRI_raw": raw_risk,
                "GRI_pec": pec_risk,
                "delta_raw_minus_pec": float(delta),
                "relative_savings": relative_savings,
                "PEC_wins": bool(pec_risk < raw_risk),
                "rho_gap_noise": rho_gap_noise,
            }
        )

    ideal_argmin = int(np.argmin(ideal_values))
    raw_argmin = int(np.argmin(means_het[0]))
    ranking_flip = bool(raw_argmin != ideal_argmin)
    offdiag_corr = _mean_abs_offdiag_corr(sigma_unit)
    result = {
        "config_path": str(HET_DERISK_CONFIG_PATH.relative_to(REPO_ROOT)),
        "output_note": "No confirmatory effect sizes used; channel/Phi/rho_c read from locked config.",
        "graph_consistency": {
            "channel_graph_equals_a3_graph": bool(graph_match),
            "num_qubits": int(graph.number_of_nodes()),
            "num_edges": int(graph.number_of_edges()),
            "edges": _edges(graph),
        },
        "scale_treatment": (
            "A3 primitive moments keep the frozen three-scale layout. The same locked "
            "heterogeneous channel is supplied for all scale slots; the Raw gap map "
            "uses only lambda=1 coefficients [1,0,0]."
        ),
        "gamma_het": float(gamma_het),
        "gamma_squared_het": gamma_squared,
        "rate_ranges": {
            "p1_min": float(min(p1_by_qubit.values())),
            "p1_max": float(max(p1_by_qubit.values())),
            "p2_min": float(min(p2_by_edge.values())),
            "p2_max": float(max(p2_by_edge.values())),
        },
        "ranking_diagnostic": {
            "ideal_argmin": ideal_argmin,
            "raw_het_argmin": raw_argmin,
            "ranking_flip": ranking_flip,
            "min_mu_raw": float(np.min(mu_raw)),
            "min_mu_ideal": float(np.min(mu_ideal)),
        },
        "sigma_diagnostics": {
            "dimension": int(sigma_unit.shape[0]),
            "min_eigenvalue": float(np.min(np.linalg.eigvalsh(sigma_unit))),
            "mean_abs_offdiag_correlation": offdiag_corr,
        },
        "budgets": rows,
        "rho_c": float(config["regime_frontier"]["rho_c"]),
    }
    return result


def write_outputs(result: dict[str, Any], output_dir: Path = OUTPUT_DIR) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "derisk_result.json"
    md_path = output_dir / "derisk_result.md"
    json_path.write_text(
        json.dumps(_jsonable(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Heterogeneous PEC De-risk Result",
        "",
        "This computes the locked 2b de-risk metric from `het_pec_derisk.yaml`.",
        "No confirmatory effect sizes are used.",
        "",
        "## Graph Gate",
        "",
        f"- channel_graph_equals_a3_graph: {result['graph_consistency']['channel_graph_equals_a3_graph']}",
        f"- num_qubits: {result['graph_consistency']['num_qubits']}",
        f"- num_edges: {result['graph_consistency']['num_edges']}",
        "",
        "## PEC Overhead",
        "",
        f"- gamma_het: {result['gamma_het']:.12g}",
        f"- gamma_squared_het: {result['gamma_squared_het']:.12g}",
        f"- p1_range: [{result['rate_ranges']['p1_min']:.12g}, {result['rate_ranges']['p1_max']:.12g}]",
        f"- p2_range: [{result['rate_ranges']['p2_min']:.12g}, {result['rate_ranges']['p2_max']:.12g}]",
        "",
        "## Ranking Diagnostic",
        "",
        f"- ideal_argmin: {result['ranking_diagnostic']['ideal_argmin']}",
        f"- raw_het_argmin: {result['ranking_diagnostic']['raw_het_argmin']}",
        f"- ranking_flip: {result['ranking_diagnostic']['ranking_flip']}",
        f"- min_mu_raw: {result['ranking_diagnostic']['min_mu_raw']:.12g}",
        f"- min_mu_ideal: {result['ranking_diagnostic']['min_mu_ideal']:.12g}",
        "",
        "## Budget Table",
        "",
        "| budget | GRI_raw | GRI_pec | raw_minus_pec | relative_savings | PEC_wins | rho_gap_noise |",
        "|---:|---:|---:|---:|---:|:---:|---:|",
    ]
    for row in result["budgets"]:
        rel = row["relative_savings"]
        rho = row["rho_gap_noise"]
        lines.append(
            "| {budget} | {raw:.12g} | {pec:.12g} | {delta:.12g} | {rel} | {wins} | {rho} |".format(
                budget=row["budget"],
                raw=row["GRI_raw"],
                pec=row["GRI_pec"],
                delta=row["delta_raw_minus_pec"],
                rel="NA" if rel is None else f"{rel:.12g}",
                wins=str(row["PEC_wins"]),
                rho="NA" if rho is None else f"{rho:.12g}",
            )
        )
    lines.extend(
        [
            "",
            "## Scale Treatment",
            "",
            str(result["scale_treatment"]),
            "",
            "## Secondary Frontier Summary",
            "",
            f"- rho_c: {result['rho_c']:.12g}",
            "- rho_gap_noise is reported per budget as relative_savings / 0.20.",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)
    result = run_derisk()
    json_path, md_path = write_outputs(result, args.output_dir)
    print("HET PEC DERISK COMPLETE")
    print(f"graph_match={result['graph_consistency']['channel_graph_equals_a3_graph']}")
    print(f"gamma_het={result['gamma_het']:.12g}")
    print(f"gamma_squared_het={result['gamma_squared_het']:.12g}")
    print(f"ranking_flip={result['ranking_diagnostic']['ranking_flip']}")
    for row in result["budgets"]:
        print(
            "budget={budget} GRI_raw={raw:.12g} GRI_pec={pec:.12g} "
            "PEC_wins={wins} rho={rho}".format(
                budget=row["budget"],
                raw=row["GRI_raw"],
                pec=row["GRI_pec"],
                wins=row["PEC_wins"],
                rho="NA" if row["rho_gap_noise"] is None else f"{row['rho_gap_noise']:.12g}",
            )
        )
    print(f"wrote={json_path.relative_to(REPO_ROOT)}")
    print(f"wrote={md_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
