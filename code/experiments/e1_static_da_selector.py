from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
import yaml

from experiments.gate0_pilot_full_vs_diagonal import (
    confirmatory_raw_relpath,
    load_config as load_gate0_config,
)
from experiments.pilot_power_report import (
    ALPHA,
    build_power_table,
    paired_test_rejects,
)


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "results"
DESIGN_CONFIG = REPO_ROOT / "reproducibility" / "config" / "confirmatory_design.yaml"
MANIFEST_REL = Path("frozen") / "confirmatory_instance_manifest.csv"
E1_CSV_REL = Path("confirmatory") / "e1_static_decision_failure.csv"
SELECTOR_TABLE_REL = Path("confirmatory") / "e1_static_selector_table.csv"
REPORT_REL = Path("confirmatory") / "e1_static_decision_failure.md"


def _load_design() -> dict:
    with DESIGN_CONFIG.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _b_star_from_design() -> int:
    return int(_load_design()["regime"]["B_star_operational"])


def _confirmatory_manifest(output_root: Path) -> pd.DataFrame:
    path = output_root / MANIFEST_REL
    if not path.exists():
        raise FileNotFoundError(f"missing confirmatory manifest: {path}")
    return pd.read_csv(path)


def _decision_gap_from_raw(output_root: Path, instance_id: str) -> float:
    raw = np.load(output_root / confirmatory_raw_relpath(instance_id), allow_pickle=False)
    ideal_values = np.asarray(raw["ideal_values"], dtype=float)
    order = np.argsort(ideal_values, kind="mergesort")
    if order.size < 2:
        raise ValueError("at least two candidates are required")
    return float(ideal_values[order[1]] - ideal_values[order[0]])


def _tercile_labels(values: pd.Series, *, lower_is_harder: bool) -> pd.Series:
    ordered = values.sort_values(ascending=lower_is_harder, kind="mergesort")
    n = len(ordered)
    labels = {}
    for pos, idx in enumerate(ordered.index):
        frac = (pos + 0.5) / float(n)
        if frac <= 1.0 / 3.0:
            label = "hard"
        elif frac <= 2.0 / 3.0:
            label = "medium"
        else:
            label = "easy"
        labels[idx] = label
    return pd.Series(labels).reindex(values.index)


def attach_confirmatory_covariates(table: pd.DataFrame, output_root: Path) -> pd.DataFrame:
    manifest = _confirmatory_manifest(output_root)[
        ["instance_id", "epsilon_opt_ideal", "difficulty_tercile"]
    ].rename(
        columns={
            "instance_id": "cell",
            "difficulty_tercile": "epsilon_opt_tercile",
        }
    )
    out = table.merge(manifest, on="cell", how="left", validate="many_to_one")
    if out["epsilon_opt_ideal"].isna().any():
        missing = sorted(out.loc[out["epsilon_opt_ideal"].isna(), "cell"].unique())
        raise ValueError(f"missing manifest rows for confirmatory cells: {missing}")
    gaps = {
        cell: _decision_gap_from_raw(output_root, str(cell))
        for cell in sorted(out["cell"].unique())
    }
    out["decision_gap_ideal"] = out["cell"].map(gaps).astype(float)
    unique = (
        out[["cell", "decision_gap_ideal"]]
        .drop_duplicates()
        .set_index("cell")["decision_gap_ideal"]
    )
    gap_terciles = _tercile_labels(unique, lower_is_harder=True)
    out["decision_gap_tercile"] = out["cell"].map(gap_terciles.to_dict())
    return out


def e1_table(
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    *,
    profile: str = "confirmatory_e1_smoke",
) -> pd.DataFrame:
    config = load_gate0_config(profile)
    if str(config.get("output_namespace")) != "confirmatory":
        raise ValueError("E1 must use a confirmatory Gate 0 raw profile")
    table = build_power_table(
        output_root,
        config=config,
        raw_path_func=confirmatory_raw_relpath,
        expected_profile=profile,
    )
    return attach_confirmatory_covariates(table, output_root)


def aggregate_at_bstar(table: pd.DataFrame, b_star: int) -> dict[str, object]:
    subset = table[table["budget"] == int(b_star)].copy()
    if subset.empty:
        raise ValueError(f"E1 table has no rows at B*={b_star}")
    both_fail = int(subset["both_fail"].sum())
    both_ok = int(subset["both_ok"].sum())
    b = int(subset["b"].sum())
    c = int(subset["c"].sum())
    n = int(subset["paired_n"].sum())
    failure_mse = (both_fail + b) / float(n)
    failure_da = (both_fail + c) / float(n)
    rel_reduction = (
        (failure_mse - failure_da) / failure_mse if failure_mse > 0.0 else 0.0
    )
    return {
        "B_star_operational": int(b_star),
        "instances": int(len(subset)),
        "paired_n": n,
        "both_fail": both_fail,
        "both_ok": both_ok,
        "b_DA_better": b,
        "c_DA_worse": c,
        "failure_rate_MSE": float(failure_mse),
        "failure_rate_DA": float(failure_da),
        "observed_rel_reduction": float(rel_reduction),
        "alpha": float(ALPHA),
        "mcnemar_one_sided_reject": paired_test_rejects(
            b=b,
            c=c,
            n=n,
            alpha=ALPHA,
        ),
    }


def _stratified_summary(table: pd.DataFrame, column: str, b_star: int) -> pd.DataFrame:
    subset = table[table["budget"] == int(b_star)].copy()
    rows = []
    for label, group in subset.groupby(column, sort=True):
        both_fail = int(group["both_fail"].sum())
        b = int(group["b"].sum())
        c = int(group["c"].sum())
        n = int(group["paired_n"].sum())
        rows.append(
            {
                "stratifier": column,
                "stratum": str(label),
                "instances": int(len(group)),
                "paired_n": n,
                "failure_rate_MSE": (both_fail + b) / float(n),
                "failure_rate_DA": (both_fail + c) / float(n),
                "b_DA_better": b,
                "c_DA_worse": c,
            }
        )
    return pd.DataFrame(rows)


def selector_table(table: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "cell",
        "budget",
        "MSE_selected_method",
        "DA_selected_method",
        "MSE_selected_mse",
        "DA_selected_gri",
        "failure_rate_MSE",
        "failure_rate_DA",
        "failure_rate_Raw",
        "epsilon_opt_ideal",
        "epsilon_opt_tercile",
        "decision_gap_ideal",
        "decision_gap_tercile",
    ]
    return table[columns].copy()


def write_report(
    *,
    output_root: Path,
    table: pd.DataFrame,
    aggregate: dict[str, object],
    stratified: pd.DataFrame,
    profile: str,
) -> Path:
    out = output_root / REPORT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    b_star = int(aggregate["B_star_operational"])
    lines = [
        "# E1 Static Decision Failure",
        "",
        "Confirmatory smoke/full runner for Claim 1. Reuses pilot_power_report primitives; outputs are under results/confirmatory.",
        "",
        "## Configuration",
        "",
        f"- profile: {profile}",
        f"- B_star_operational: {b_star}",
        f"- alpha: {ALPHA}",
        "- selector_rules: daqem.selectors.mse_selector / daqem.selectors.da_selector",
        "- covariance_estimator: Ledoit-Wolf via pilot_power_report.method_gri_by_method",
        "",
        "## Aggregate at B*",
        "",
        "| instances | paired_n | both_fail | both_ok | b_DA_better | c_DA_worse | failure_rate_MSE | failure_rate_DA | observed_rel_reduction | mcnemar_one_sided_reject |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        "| {instances} | {paired_n} | {both_fail} | {both_ok} | {b_DA_better} | {c_DA_worse} | "
        "{failure_rate_MSE:.6g} | {failure_rate_DA:.6g} | {observed_rel_reduction:.6g} | "
        "{mcnemar_one_sided_reject} |".format(**aggregate),
        "",
        "## Instance Rows at B*",
        "",
        "| cell | epsilon_tercile | gap_tercile | MSE_selected_method | DA_selected_method | failure_rate_MSE | failure_rate_DA | b_DA_better | c_DA_worse |",
        "|---|---|---|---|---|---:|---:|---:|---:|",
    ]
    for row in table[table["budget"] == b_star].sort_values("cell").to_dict("records"):
        lines.append(
            "| {cell} | {epsilon_opt_tercile} | {decision_gap_tercile} | "
            "{MSE_selected_method} | {DA_selected_method} | {failure_rate_MSE:.6g} | "
            "{failure_rate_DA:.6g} | {b} | {c} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Stratified Report",
            "",
            "| stratifier | stratum | instances | paired_n | failure_rate_MSE | failure_rate_DA | b_DA_better | c_DA_worse |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in stratified.to_dict("records"):
        lines.append(
            "| {stratifier} | {stratum} | {instances} | {paired_n} | "
            "{failure_rate_MSE:.6g} | {failure_rate_DA:.6g} | "
            "{b_DA_better} | {c_DA_worse} |".format(**row)
        )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def run(
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    *,
    profile: str = "confirmatory_e1_smoke",
) -> dict[str, object]:
    b_star = _b_star_from_design()
    table = e1_table(output_root, profile=profile)
    aggregate = aggregate_at_bstar(table, b_star)
    stratified = pd.concat(
        [
            _stratified_summary(table, "epsilon_opt_tercile", b_star),
            _stratified_summary(table, "decision_gap_tercile", b_star),
        ],
        ignore_index=True,
    )
    output_root.mkdir(parents=True, exist_ok=True)
    e1_csv = output_root / E1_CSV_REL
    selector_csv = output_root / SELECTOR_TABLE_REL
    e1_csv.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(e1_csv, index=False)
    selector_csv.parent.mkdir(parents=True, exist_ok=True)
    selector_table(table).to_csv(selector_csv, index=False)
    write_report(
        output_root=output_root,
        table=table,
        aggregate=aggregate,
        stratified=stratified,
        profile=profile,
    )
    result = {
        "profile": profile,
        "output": E1_CSV_REL.as_posix(),
        "selector_table": SELECTOR_TABLE_REL.as_posix(),
        "report": REPORT_REL.as_posix(),
        "rows": int(len(table)),
        "aggregate": aggregate,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--profile", default="confirmatory_e1_smoke")
    args = parser.parse_args(argv)
    run(Path(args.output).resolve(), profile=args.profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
