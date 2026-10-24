"""Retrospective analytic noise sweep; generation never promotes reference data."""
from __future__ import annotations
import argparse
import copy
import csv
import json
from pathlib import Path
import numpy as np
import experiments.proof_of_mechanism_run as pom

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = REPO_ROOT / "results" / "phase_diagram"
INSTANCE_ID = "POM_001"
METHODS = ("Raw", "CDR", "PEC")
P1_GRID = (0.0025, 0.005, 0.0075, 0.01, 0.015, 0.02, 0.03, 0.04)
# Numerical integration screening tolerance, not a statistical interval.
GRI_TOL = 2e-6
MSE_RTOL = 1e-12


def noise_cell(p1: float, *, evidence_dir: Path | None = None) -> list[dict]:
    config = copy.deepcopy(pom.load_config())
    ratio = float(config["noise"]["p2"]) / float(config["noise"]["p1"])
    config["noise"].update(p1=float(p1), p2=ratio * float(p1))
    config.setdefault("scope", {}).update(
        no_rate_sweep=False, analysis="retrospective_noise_sweep",
        pec_model="ideal_multinomial_floor_B_over_gamma_squared")
    analytics = pom.instance_analytics(INSTANCE_ID, config, allow_infeasible_pec=True)
    if evidence_dir is not None:
        pom.write_evidence([analytics], [], config, evidence_dir / f"p1_{p1:.6g}")
    rows = []
    for budget in map(int, config["budget_grid"]):
        for method in METHODS:
            item = analytics["analytic_by_budget"][str(budget)][method]
            rows.append(dict(instance_id=INSTANCE_ID, p1=float(p1), p2=config["noise"]["p2"],
                budget=budget, method=method, mse=item["MSE_expected"], gri=item["GRI"],
                feasible=item.get("feasible", True), reason=item.get("reason", ""),
                gamma_squared=analytics["gamma_squared"],
                effective_shots=item.get("effective_shots", budget)))
    return rows


def phase_rows(*, evidence_dir: Path | None = None) -> list[dict]:
    return [row for p1 in P1_GRID for row in noise_cell(p1, evidence_dir=evidence_dir)]


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["instance_id", "p1", "p2", "budget", "method", "mse", "gri",
               "feasible", "reason", "gamma_squared", "effective_shots"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _feasible(row: dict) -> bool:
    return row.get("feasible", True) not in (False, "False", "false", "0")


def minimizer_sets(rows: list[dict]) -> tuple[set[str], set[str]]:
    available = [r for r in rows if _feasible(r)]
    if not available:
        raise ValueError("Cell has no feasible methods")
    result = []
    for metric in ("mse", "gri"):
        values = np.asarray([float(r[metric]) for r in available])
        if not np.isfinite(values).all() or np.any(values < 0):
            raise ValueError(f"Invalid feasible {metric}")
        best = float(values.min())
        tol = GRI_TOL if metric == "gri" else MSE_RTOL * max(abs(best), 1e-15)
        result.append({str(r["method"]) for r, v in zip(available, values) if v <= best + tol})
    return result[0], result[1]


def cell_separations(rows: list[dict]) -> list[dict]:
    grouped = {}
    for row in rows:
        grouped.setdefault((int(row["budget"]), float(row["p1"])), []).append(row)
    result = []
    for (budget, p1), cell_rows in sorted(grouped.items()):
        mse, gri = minimizer_sets(cell_rows)
        result.append(dict(budget=budget, p1=p1, mse_minimizers=sorted(mse),
                           gri_minimizers=sorted(gri), forced_separation=mse.isdisjoint(gri)))
    return result


def separation_by_budget(rows: list[dict]) -> dict[int, list[tuple[float, str, str]]]:
    result = {}
    for cell in cell_separations(rows):
        examples = result.setdefault(cell["budget"], [])
        if cell["forced_separation"]:
            examples.append((cell["p1"], "/".join(cell["mse_minimizers"]),
                             "/".join(cell["gri_minimizers"])))
    return result


def save_results(rows: list[dict], output_dir: Path) -> dict:
    write_csv(rows, output_dir / "grid.csv")
    summary = dict(scope="retrospective_analytic_single_instance_noise_sweep",
                   pec_model="ideal_multinomial_floor_B_over_gamma_squared",
                   gri_numerical_tolerance=GRI_TOL, mse_relative_tolerance=MSE_RTOL,
                   infeasible_rows=sum(not _feasible(r) for r in rows),
                   cells=cell_separations(rows))
    (output_dir / "separation.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=RESULT_DIR)
    args = parser.parse_args()
    summary = save_results(phase_rows(evidence_dir=args.output_dir / "evidence"), args.output_dir)
    print(json.dumps(dict(output=str(args.output_dir), infeasible_rows=summary["infeasible_rows"],
                          separated_cells=sum(c["forced_separation"] for c in summary["cells"]))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
