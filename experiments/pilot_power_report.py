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
from scipy.stats import norm

from daqem.risk import gri_risk
from daqem.rng import make_rng
from daqem.selectors import da_selector, mse_selector

from experiments.gate0_pilot_full_vs_diagonal import (
    _covariance,
    _method_gap_samples,
    confirmatory_raw_relpath,
    empirical_decision_failure_rate,
    load_config as load_gate0_config,
    raw_relpath,
)


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "results"
REPORT_REL = Path("pilot") / "pilot_power_report.md"

CRITICAL_BAND_LOW = 0.15
CRITICAL_BAND_HIGH = 0.70
STATIC_PRIMARY_MIN_PAIRED_DECISIONS = 1500
CONFIRMATORY_INSTANCES = 48
CONFIRMATORY_REPLICATES = 40
MIN_DETECTABLE_RELATIVE_FAILURE_REDUCTION = 0.15
BOOTSTRAP_REPETITIONS = 10_000
ALPHA = 0.05


def _method_coefficients_from_gap_samples(
    method: str,
    primitive_objective_estimates: np.ndarray,
    ideal_values: np.ndarray,
    x_star: int,
    budget_idx: int,
    config: dict,
) -> np.ndarray:
    from daqem.qem_methods import (
        accuracy_zne_coeffs,
        decision_optimal_zne_coeffs,
        richardson_constraints,
    )

    scales = np.asarray(config["zne_lambdas"], dtype=float)
    order = int(config["zne_order"])
    if method == "Accuracy-ZNE":
        return accuracy_zne_coeffs(scales, p=order)
    if method == "Decision-ZNE":
        estimates = np.asarray(primitive_objective_estimates, dtype=float)
        competitors = [idx for idx in range(len(ideal_values)) if idx != int(x_star)]
        primitive_gaps = (
            estimates[:, :, competitors, budget_idx]
            - estimates[:, :, [int(x_star)], budget_idx]
        )
        true_mu = np.asarray(ideal_values, dtype=float)[competitors] - float(
            ideal_values[int(x_star)]
        )
        mu_lower = np.maximum(true_mu, float(config["decision_zne_mu_floor"]))
        q_list = [
            _covariance(primitive_gaps[:, :, gap_idx], shrinkage=False)
            for gap_idx in range(primitive_gaps.shape[2])
        ]
        A, rho = richardson_constraints(scales, p=order)
        return decision_optimal_zne_coeffs(q_list, mu_lower, A, rho)
    if method == "Raw":
        coeffs = np.zeros(scales.size, dtype=float)
        coeffs[0] = 1.0
        return coeffs
    raise ValueError(f"unknown method: {method}")


def method_objective_samples(
    primitive_objective_estimates: np.ndarray,
    ideal_values: np.ndarray,
    x_star: int,
    budget_idx: int,
    config: dict,
) -> dict[str, np.ndarray]:
    estimates = np.asarray(primitive_objective_estimates, dtype=float)
    methods = {}
    for method in config["method_menu_core"]:
        coeffs = _method_coefficients_from_gap_samples(
            method,
            estimates,
            ideal_values,
            x_star,
            budget_idx,
            config,
        )
        methods[method] = np.einsum("s,rsc->rc", coeffs, estimates[:, :, :, budget_idx])
    return methods


def method_mse_by_method(
    objective_samples: dict[str, np.ndarray],
    ideal_values: np.ndarray,
) -> dict[str, float]:
    ideal = np.asarray(ideal_values, dtype=float)
    return {
        method: float(np.mean((np.asarray(samples, dtype=float) - ideal[None, :]) ** 2))
        for method, samples in objective_samples.items()
    }


def method_gri_by_method(
    gap_samples: dict[str, np.ndarray],
    *,
    shrinkage: bool,
) -> dict[str, float]:
    risks = {}
    for method, samples in gap_samples.items():
        arr = np.asarray(samples, dtype=float)
        mu = np.mean(arr, axis=0)
        sigma = _covariance(arr, shrinkage=shrinkage)
        risks[method] = gri_risk(mu, sigma, B=1.0)
    return risks


def paired_outcome_counts(
    mse_gap_samples: np.ndarray,
    da_gap_samples: np.ndarray,
) -> dict[str, float]:
    """Count paired decision outcomes for MSE and DA on the same replicates."""

    mse = np.asarray(mse_gap_samples, dtype=float)
    da = np.asarray(da_gap_samples, dtype=float)
    if mse.shape != da.shape:
        raise ValueError("MSE and DA gap samples must have identical shape")
    if mse.ndim != 2 or mse.shape[0] == 0 or mse.shape[1] == 0:
        raise ValueError("gap samples must have shape (replicates, gaps)")
    mse_fail = np.any(mse <= 0.0, axis=1)
    da_fail = np.any(da <= 0.0, axis=1)
    both_fail = int(np.sum(mse_fail & da_fail))
    both_ok = int(np.sum(~mse_fail & ~da_fail))
    b = int(np.sum(mse_fail & ~da_fail))
    c = int(np.sum(~mse_fail & da_fail))
    n = int(mse.shape[0])
    failure_mse = (both_fail + b) / float(n)
    failure_da = (both_fail + c) / float(n)
    rel_reduction = (
        (failure_mse - failure_da) / failure_mse if failure_mse > 0.0 else 0.0
    )
    return {
        "both_fail": both_fail,
        "both_ok": both_ok,
        "b": b,
        "c": c,
        "paired_n": n,
        "observed_rel_reduction": float(rel_reduction),
    }


def paired_test_rejects(*, b: int, c: int, n: int, alpha: float) -> bool:
    """One-sided paired z-test for DA reducing failure relative to MSE."""

    if int(n) <= 1:
        return False
    values = np.concatenate(
        [
            np.ones(int(b), dtype=float),
            -np.ones(int(c), dtype=float),
            np.zeros(int(n) - int(b) - int(c), dtype=float),
        ]
    )
    mean = float(np.mean(values))
    se = float(np.std(values, ddof=1) / np.sqrt(int(n)))
    if se <= 0.0:
        return mean > 0.0
    return mean / se > float(norm.ppf(1.0 - float(alpha)))


def pooled_observed_effect(table: pd.DataFrame, budget: int) -> dict[str, object] | None:
    """Pool paired outcomes over in-band pilot cells at the operative budget."""

    subset = table[(table["budget"] == int(budget)) & (table["in_band"])].copy()
    if subset.empty:
        return None
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
        "budget": int(budget),
        "pilot_instances": int(len(subset)),
        "paired_n_pilot": n,
        "both_fail": both_fail,
        "both_ok": both_ok,
        "b": b,
        "c": c,
        "failure_rate_MSE_pooled": float(failure_mse),
        "failure_rate_DA_pooled": float(failure_da),
        "observed_rel_reduction_pooled": float(rel_reduction),
        "mde_reached": bool(rel_reduction >= MIN_DETECTABLE_RELATIVE_FAILURE_REDUCTION),
    }


def static_power(
    *,
    pooled_counts: dict[str, object],
    paired_decisions: int,
    alpha: float,
    repetitions: int,
) -> float:
    total = int(pooled_counts["both_fail"]) + int(pooled_counts["both_ok"]) + int(
        pooled_counts["b"]
    ) + int(pooled_counts["c"])
    if total <= 0:
        raise ValueError("pooled_counts must contain at least one observed pair")
    probabilities = np.asarray(
        [
            int(pooled_counts["both_fail"]) / float(total),
            int(pooled_counts["both_ok"]) / float(total),
            int(pooled_counts["b"]) / float(total),
            int(pooled_counts["c"]) / float(total),
        ],
        dtype=float,
    )
    rng = make_rng(
        instance_id="pilot_power_report",
        method="static_power",
        budget=int(paired_decisions),
        replicate_id=0,
        stream="paired_observed_outcome_bootstrap",
    )
    rejections = 0
    n = int(paired_decisions)
    for _ in range(int(repetitions)):
        _both_fail, _both_ok, b, c = rng.multinomial(n, probabilities)
        if paired_test_rejects(b=int(b), c=int(c), n=n, alpha=alpha):
            rejections += 1
    return rejections / float(repetitions)


def build_power_table(
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    *,
    config: dict | None = None,
    profile: str = "full",
    raw_path_func=raw_relpath,
    expected_profile: str | None = "full",
) -> pd.DataFrame:
    config = load_gate0_config(profile) if config is None else dict(config)
    rows = []
    for instance_id in config["instance_ids"]:
        raw = np.load(output_root / raw_path_func(instance_id), allow_pickle=False)
        metadata = json.loads(str(raw["metadata_json"].item()))
        if expected_profile is not None and metadata.get("profile") != expected_profile:
            raise ValueError(f"{instance_id} raw is not {expected_profile} profile")
        budgets = [int(value) for value in raw["budgets"]]
        ideal_values = np.asarray(raw["ideal_values"], dtype=float)
        x_star = int(raw["x_star"])
        estimates = np.asarray(raw["primitive_objective_estimates"], dtype=float)
        for budget_idx, budget in enumerate(budgets):
            gap_samples = _method_gap_samples(estimates, ideal_values, x_star, budget_idx, config)
            objective_samples = method_objective_samples(
                estimates,
                ideal_values,
                x_star,
                budget_idx,
                config,
            )
            mse_by_method = method_mse_by_method(objective_samples, ideal_values)
            gri_by_method = method_gri_by_method(
                gap_samples,
                shrinkage=bool(config["use_ledoit_wolf"]),
            )
            mse_method = mse_selector(mse_by_method)
            da_method = da_selector(gri_by_method, gri_valid=True)
            failure_mse = empirical_decision_failure_rate(gap_samples[mse_method])
            failure_da = empirical_decision_failure_rate(gap_samples[da_method])
            failure_raw = empirical_decision_failure_rate(gap_samples["Raw"])
            paired = paired_outcome_counts(gap_samples[mse_method], gap_samples[da_method])
            rows.append(
                {
                    "cell": instance_id,
                    "budget": budget,
                    "MSE_selected_method": mse_method,
                    "DA_selected_method": da_method,
                    "failure_rate_MSE": failure_mse,
                    "failure_rate_DA": failure_da,
                    "failure_rate_Raw": failure_raw,
                    "both_fail": paired["both_fail"],
                    "both_ok": paired["both_ok"],
                    "b": paired["b"],
                    "c": paired["c"],
                    "paired_n": paired["paired_n"],
                    "observed_rel_reduction": paired["observed_rel_reduction"],
                    "MSE_selected_mse": mse_by_method[mse_method],
                    "DA_selected_gri": gri_by_method[da_method],
                    "in_band": bool(CRITICAL_BAND_LOW <= failure_mse <= CRITICAL_BAND_HIGH),
                    "band_margin": min(
                        failure_mse - CRITICAL_BAND_LOW,
                        CRITICAL_BAND_HIGH - failure_mse,
                    )
                    if CRITICAL_BAND_LOW <= failure_mse <= CRITICAL_BAND_HIGH
                    else -min(
                        abs(failure_mse - CRITICAL_BAND_LOW),
                        abs(failure_mse - CRITICAL_BAND_HIGH),
                    ),
                }
            )
    return pd.DataFrame(rows)


def choose_primary_cell(table: pd.DataFrame) -> dict[str, object] | None:
    band = table[table["in_band"]].copy()
    if band.empty:
        return None
    band = band.sort_values(
        by=["band_margin", "failure_rate_MSE", "budget", "cell"],
        ascending=[False, True, True, True],
        kind="mergesort",
    )
    return dict(band.iloc[0])


def render_report(
    *,
    output_root: Path,
    table: pd.DataFrame,
    primary: dict[str, object] | None,
) -> Path:
    out = output_root / REPORT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    paired_decisions = CONFIRMATORY_INSTANCES * CONFIRMATORY_REPLICATES
    pooled = None
    if primary is None:
        power = None
        primary_lines = [
            "No pilot cell/budget has `failure_rate_MSE` in `[0.15, 0.70]`.",
            "",
            "Proposed PAP 5.4 correction order before freezing: B*, epsilon_opt, depth, noise.",
        ]
    else:
        pooled = pooled_observed_effect(table, int(primary["budget"]))
        if pooled is None:
            raise ValueError("primary budget has no in-band pooled paired outcomes")
        power = static_power(
            pooled_counts=pooled,
            paired_decisions=paired_decisions,
            alpha=ALPHA,
            repetitions=BOOTSTRAP_REPETITIONS,
        )
        primary_lines = [
            f"- primary_cell: {primary['cell']}",
            f"- B_star_operational: {int(primary['budget'])}",
            f"- baseline failure_rate_MSE: {float(primary['failure_rate_MSE']):.6g}",
            "- choice rule: maximum distance from the nearest edge of `[0.15, 0.70]`, tie-broken by lower failure, lower budget, then cell id.",
        ]

    lines = [
        "# Pilot Static Power Report",
        "",
        "Diagnostic pilot report; not canonical and not part of verify/reference until freeze.",
        "",
        "## Definitions",
        "",
        "- Baseline is the MSE-selected method at each `(cell, budget)`.",
        "- `MSE_m` is the empirical mean over F1a replicates and candidates of `(hat F_m - F_ideal)^2`.",
        "- DA is selected by full Gaussian risk (GRI) from the same gap samples.",
        "- Failure is the empirical event that at least one residual gap is non-positive.",
        "- Paired decisions are counted as one shared confirmatory instance/replicate decision for MSE and DA at the same `(cell, budget)`.",
        "",
        "## Gate Parameters",
        "",
        f"- critical_band: [{CRITICAL_BAND_LOW}, {CRITICAL_BAND_HIGH}]",
        f"- static_primary_min_paired_decisions: {STATIC_PRIMARY_MIN_PAIRED_DECISIONS}",
        f"- confirmatory_static_design: {CONFIRMATORY_INSTANCES} instances x {CONFIRMATORY_REPLICATES} replicates = {paired_decisions} paired decisions",
        f"- minimum_detectable_relative_failure_reduction: {MIN_DETECTABLE_RELATIVE_FAILURE_REDUCTION}",
        f"- bootstrap_repetitions: {BOOTSTRAP_REPETITIONS}",
        f"- alpha: {ALPHA}",
        "",
        "## Primary Static Cell",
        "",
        *primary_lines,
        "",
    ]

    if primary is None:
        lines.extend(
            [
                "## Observed Paired Effect at B*",
                "",
                "not_computed_no_in_band_cell",
                "",
                "## Static Power Check",
                "",
                "- power_estimated_from_observed_pairs: not_computed_no_in_band_cell",
            ]
        )
    else:
        bstar_rows = table[table["budget"] == int(primary["budget"])].sort_values("cell")
        lines.extend(
            [
                "## Observed Paired Effect at B*",
                "",
                "| cell | in_band | both_fail | both_ok | b_DA_better | c_DA_worse | fail_MSE | fail_DA | observed_rel_reduction | reaches_MDE_0.15 |",
                "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
            ]
        )
        for row in bstar_rows.to_dict("records"):
            reaches = bool(
                float(row["observed_rel_reduction"])
                >= MIN_DETECTABLE_RELATIVE_FAILURE_REDUCTION
            )
            lines.append(
                "| {cell} | {in_band} | {both_fail} | {both_ok} | {b} | {c} | "
                "{failure_rate_MSE:.6g} | {failure_rate_DA:.6g} | "
                "{observed_rel_reduction:.6g} | ".format(**row)
                + f"{reaches} |"
            )
        lines.extend(
            [
                "",
                "| pooled_in_band_at_B* | pilot_instances | paired_n_pilot | both_fail | both_ok | b_DA_better | c_DA_worse | fail_MSE | fail_DA | observed_rel_reduction | reaches_MDE_0.15 |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
                "| B*={budget} | {pilot_instances} | {paired_n_pilot} | {both_fail} | "
                "{both_ok} | {b} | {c} | {failure_rate_MSE_pooled:.6g} | "
                "{failure_rate_DA_pooled:.6g} | "
                "{observed_rel_reduction_pooled:.6g} | {mde_reached} |".format(
                    **pooled
                ),
                "",
                f"- uncertainty_note: pooled effect uses {pooled['pilot_instances']} in-band pilot instances at B*; projected power assumes the confirmatory effect distribution is similar.",
                "",
                "## Static Power Check",
                "",
                f"- paired_decisions_ok: {paired_decisions >= STATIC_PRIMARY_MIN_PAIRED_DECISIONS}",
                f"- power_estimated_from_observed_pairs: {power:.6g}",
                "- simulation_model: multinomial bootstrap from observed pooled paired outcomes `(both_fail, both_ok, b, c)` at B*.",
                "- no_hypothetical_15pct_power_number: true",
            ]
        )

    lines.extend(
        [
            "",
            "## Critical Band",
            "",
            "| cell | budget | failure_rate_MSE | MSE_selected_method | DA_selected_method |",
            "|---|---:|---:|---|---|",
        ]
    )
    band = table[table["in_band"]].copy()
    if band.empty:
        lines.append("| none | NA | NA | NA | NA |")
    else:
        for row in band.sort_values(["cell", "budget"]).to_dict("records"):
            lines.append(
                "| {cell} | {budget} | {failure_rate_MSE:.6g} | {MSE_selected_method} | {DA_selected_method} |".format(
                    **row
                )
            )

    lines.extend(
        [
            "",
            "## Static Pilot Table",
            "",
            "| cell | budget | MSE_selected_method | DA_selected_method | failure_rate_MSE | failure_rate_DA | failure_rate_Raw | observed_rel_reduction | b_DA_better | c_DA_worse | in_band |",
            "|---|---:|---|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in table.sort_values(["cell", "budget"]).to_dict("records"):
        lines.append(
            "| {cell} | {budget} | {MSE_selected_method} | {DA_selected_method} | "
            "{failure_rate_MSE:.6g} | {failure_rate_DA:.6g} | "
            "{failure_rate_Raw:.6g} | {observed_rel_reduction:.6g} | "
            "{b} | {c} | {in_band} |".format(**row)
        )

    lines.extend(
        [
            "",
            "## Pending",
            "",
            "- T_final y potencia dinamica: pendiente Fase B.",
        ]
    )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def run(output_root: Path = DEFAULT_OUTPUT_ROOT) -> dict[str, object]:
    table = build_power_table(output_root)
    primary = choose_primary_cell(table)
    render_report(output_root=output_root, table=table, primary=primary)
    result = {
        "output": REPORT_REL.as_posix(),
        "rows": int(len(table)),
        "critical_band_rows": int(table["in_band"].sum()),
        "primary_cell": None if primary is None else str(primary["cell"]),
        "B_star_operational": None if primary is None else int(primary["budget"]),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()
    run(Path(args.output).resolve())


if __name__ == "__main__":
    main()
