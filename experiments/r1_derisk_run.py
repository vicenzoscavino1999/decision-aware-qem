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
from daqem.qaoa import maxcut_graph
from daqem.risk import gri_risk
from daqem.selectors import da_selector, mse_selector
from daqem.structured_noise import (
    R1_DERISK_CONFIG_PATH,
    load_r1_structured_noise_config,
    structured_noise_model_factory,
)


OUTPUT_DIR = REPO_ROOT / "results" / "r1_derisk"


def _edges(graph) -> tuple[tuple[int, int], ...]:
    return tuple(sorted(tuple(sorted((int(i), int(j)))) for i, j in graph.edges()))


def _primary_graph(config: dict):
    cell = config["primary_cell"]
    return maxcut_graph(
        num_qubits=int(cell["num_qubits"]),
        degree=int(cell["degree"]),
        seed=int(cell["graph_seed"]),
    )


def _primitive_moments_on_primary_graph(
    *,
    config: dict,
    gate0_config: dict[str, Any],
    noise_model_factory,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, bool]:
    """Reuse A3 primitive moments on the R1 primary graph without editing A3."""

    graph = _primary_graph(config)
    channel_edges = _edges(graph)
    a3_graph = graph.copy()
    graph_match = channel_edges == _edges(a3_graph)
    if not graph_match:
        raise ValueError("structured-noise graph and A3 graph do not match")

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
        del requested_instance_id
        if int(num_qubits) != graph.number_of_nodes():
            raise ValueError("A3 requested a graph with a different number of qubits")
        if int(degree) != int(config["primary_cell"]["degree"]):
            raise ValueError("A3 requested a graph with a different degree")
        return graph.copy()

    a3.landscape_for_instance = locked_landscape_for_instance
    a3.maxcut_graph_for_instance = locked_maxcut_graph_for_instance
    try:
        moments = a3._primitive_objective_moments(
            instance_id=str(config["primary_cell"]["instance_id"]),
            gate0_config=gate0_config,
            noise_model_factory=noise_model_factory,
        )
    finally:
        a3.landscape_for_instance = original_landscape_for_instance
        a3.maxcut_graph_for_instance = original_maxcut_graph_for_instance
    return (*moments, graph_match)


def _method_values(coefficients: np.ndarray, means: np.ndarray) -> np.ndarray:
    return np.einsum("s,sk->k", np.asarray(coefficients, dtype=float), np.asarray(means, dtype=float))


def _method_unit_variance_by_candidate(coefficients: np.ndarray, variances: np.ndarray) -> np.ndarray:
    coeffs = np.asarray(coefficients, dtype=float)
    return np.einsum("s,sk->k", coeffs * coeffs, np.asarray(variances, dtype=float))


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
    config = load_r1_structured_noise_config(R1_DERISK_CONFIG_PATH)
    graph = _primary_graph(config)
    cell = config["primary_cell"]
    gate0_config = dict(a3.load_gate0_config("full"))
    gate0_config.update(
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
    noise_factory = structured_noise_model_factory(config, graph)
    means, variances, ideal_values, x_star_arr, graph_match = _primitive_moments_on_primary_graph(
        config=config,
        gate0_config=gate0_config,
        noise_model_factory=noise_factory,
    )
    x_star = int(x_star_arr)
    candidate_count = len(ideal_values)
    competitors = [idx for idx in range(candidate_count) if idx != x_star]
    ideal_values = np.asarray(ideal_values, dtype=float)
    method_names = list(gate0_config["method_menu_core"])
    coeffs_by_method = a3.method_coefficients_from_true_cdev(
        primitive_variance_unit=variances,
        ideal_values=ideal_values,
        x_star=x_star,
        gate0_config=gate0_config,
    )
    cdev_diag = np.asarray(variances, dtype=float).reshape(-1)

    method_data: dict[str, dict[str, Any]] = {}
    for method in method_names:
        coeffs = np.asarray(coeffs_by_method[method], dtype=float)
        values = _method_values(coeffs, means)
        mu = values[competitors] - float(values[x_star])
        gap_map = a3._gap_map(coeffs, candidate_count, x_star)
        sigma_unit = nearest_psd((gap_map * cdev_diag) @ gap_map.T)
        unit_var_by_candidate = _method_unit_variance_by_candidate(coeffs, variances)
        method_data[method] = {
            "coefficients": coeffs,
            "values": values,
            "mu": mu,
            "sigma_unit": sigma_unit,
            "unit_var_by_candidate": unit_var_by_candidate,
        }

    ideal_argmin = int(np.argmin(ideal_values))
    raw_argmin = int(np.argmin(means[0]))
    ranking_flip = bool(raw_argmin != ideal_argmin)
    budgets = [int(budget) for budget in gate0_config["budget_grid"]]
    budget_rows = []
    for budget in budgets:
        gri_by_method: dict[str, float] = {}
        mse_by_method: dict[str, float] = {}
        for method, data in method_data.items():
            gri_by_method[method] = float(gri_risk(data["mu"], data["sigma_unit"], B=budget))
            bias_sq = (np.asarray(data["values"], dtype=float) - ideal_values) ** 2
            mse_by_method[method] = float(
                np.mean(bias_sq + np.asarray(data["unit_var_by_candidate"], dtype=float) / float(budget))
            )
        da_method = da_selector(gri_by_method)
        mse_method = mse_selector(mse_by_method)
        mitigated_methods = [method for method in method_names if method != "Raw"]
        best_mitigated = min(mitigated_methods, key=lambda method: (gri_by_method[method], method))
        raw_gri = gri_by_method["Raw"]
        da_gri = gri_by_method[da_method]
        da_relative_savings = None if raw_gri <= 0.0 else float((raw_gri - da_gri) / raw_gri)
        rho_gap_noise = None if da_relative_savings is None else float(da_relative_savings / 0.20)
        budget_rows.append(
            {
                "budget": budget,
                "GRI": gri_by_method,
                "MSE": mse_by_method,
                "DA_selected_method": da_method,
                "MSE_selected_method": mse_method,
                "DA_beats_Raw": bool(da_gri < raw_gri),
                "best_mitigated_method": best_mitigated,
                "best_mitigated_beats_Raw": bool(gri_by_method[best_mitigated] < raw_gri),
                "relative_savings_DA_vs_Raw": da_relative_savings,
                "rho_gap_noise": rho_gap_noise,
            }
        )

    result = {
        "config_path": str(R1_DERISK_CONFIG_PATH.relative_to(REPO_ROOT)),
        "output_note": "No confirmatory ids, no rate sweep, no R1-full.",
        "graph_consistency": {
            "structured_noise_graph_equals_a3_graph": bool(graph_match),
            "num_qubits": int(graph.number_of_nodes()),
            "num_edges": int(graph.number_of_edges()),
            "edges": _edges(graph),
        },
        "channel": {
            "family": config["structured_noise_channel"]["family"],
            "gamma_amplitude_damping": float(config["structured_noise_channel"]["gamma_amplitude_damping"]),
            "gamma_phase_damping": float(config["structured_noise_channel"]["gamma_phase_damping"]),
            "scale_policy": config["structured_noise_channel"]["scale_policy"],
        },
        "ranking_diagnostic": {
            "ideal_argmin": ideal_argmin,
            "raw_lambda1_argmin": raw_argmin,
            "ranking_flip": ranking_flip,
            "raw_lambda1_value_at_ideal_argmin": float(means[0, ideal_argmin]),
            "raw_lambda1_best_value": float(np.min(means[0])),
            "ideal_best_value": float(np.min(ideal_values)),
        },
        "method_coefficients": {
            method: np.asarray(coeffs_by_method[method], dtype=float).tolist()
            for method in method_names
        },
        "budgets": budget_rows,
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
        "# R1 Structured-Noise De-risk Result",
        "",
        "This computes the locked R1 de-risk cell from `r1_structured_noise_derisk.yaml`.",
        "No confirmatory ids are used and no rate sweep is performed.",
        "",
        "## Graph Gate",
        "",
        f"- structured_noise_graph_equals_a3_graph: {result['graph_consistency']['structured_noise_graph_equals_a3_graph']}",
        f"- num_qubits: {result['graph_consistency']['num_qubits']}",
        f"- num_edges: {result['graph_consistency']['num_edges']}",
        "",
        "## Channel",
        "",
        f"- family: {result['channel']['family']}",
        f"- gamma_amplitude_damping: {result['channel']['gamma_amplitude_damping']:.12g}",
        f"- gamma_phase_damping: {result['channel']['gamma_phase_damping']:.12g}",
        f"- scale_policy: {result['channel']['scale_policy']}",
        "",
        "## Ranking Diagnostic",
        "",
        f"- ideal_argmin: {result['ranking_diagnostic']['ideal_argmin']}",
        f"- raw_lambda1_argmin: {result['ranking_diagnostic']['raw_lambda1_argmin']}",
        f"- ranking_flip: {result['ranking_diagnostic']['ranking_flip']}",
        "",
        "## Budget Table",
        "",
        "| budget | GRI_Raw | GRI_Accuracy-ZNE | GRI_Decision-ZNE | DA_selected | MSE_selected | DA<Raw | best_mitigated | best_mitigated<Raw | rho_gap_noise |",
        "|---:|---:|---:|---:|:---|:---|:---:|:---|:---:|---:|",
    ]
    for row in result["budgets"]:
        rho = row["rho_gap_noise"]
        lines.append(
            "| {budget} | {raw:.12g} | {acc:.12g} | {dec:.12g} | {da} | {mse} | {da_win} | {best} | {best_win} | {rho} |".format(
                budget=row["budget"],
                raw=row["GRI"]["Raw"],
                acc=row["GRI"]["Accuracy-ZNE"],
                dec=row["GRI"]["Decision-ZNE"],
                da=row["DA_selected_method"],
                mse=row["MSE_selected_method"],
                da_win=str(row["DA_beats_Raw"]),
                best=row["best_mitigated_method"],
                best_win=str(row["best_mitigated_beats_Raw"]),
                rho="NA" if rho is None else f"{rho:.12g}",
            )
        )
    lines.extend(
        [
            "",
            "## Secondary Frontier Summary",
            "",
            f"- rho_c: {result['rho_c']:.12g}",
            "- rho_gap_noise is reported per budget as relative_GRI_savings_DA_vs_Raw / 0.20.",
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
    print("R1 STRUCTURED-NOISE DERISK COMPLETE")
    print(f"graph_match={result['graph_consistency']['structured_noise_graph_equals_a3_graph']}")
    print(f"ranking_flip={result['ranking_diagnostic']['ranking_flip']}")
    for row in result["budgets"]:
        print(
            "budget={budget} GRI_Raw={raw:.12g} GRI_Accuracy-ZNE={acc:.12g} "
            "GRI_Decision-ZNE={dec:.12g} DA_selected={da} DA_beats_Raw={da_win} "
            "rho={rho}".format(
                budget=row["budget"],
                raw=row["GRI"]["Raw"],
                acc=row["GRI"]["Accuracy-ZNE"],
                dec=row["GRI"]["Decision-ZNE"],
                da=row["DA_selected_method"],
                da_win=row["DA_beats_Raw"],
                rho="NA" if row["rho_gap_noise"] is None else f"{row['rho_gap_noise']:.12g}",
            )
        )
    print(f"wrote={json_path.relative_to(REPO_ROOT)}")
    print(f"wrote={md_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
