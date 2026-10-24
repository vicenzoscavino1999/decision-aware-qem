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
from scipy.stats import binom
from daqem.decisions import integer_shot_sums, zne_failures

from daqem.risk import gri_risk
from daqem.rng import make_rng
from daqem.selectors import da_selector, mse_selector

from experiments.gate0_pilot_full_vs_diagonal import (
    _covariance,
    _method_gap_samples,
    confirmatory_raw_relpath,
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
    if not np.isfinite(mse).all() or not np.isfinite(da).all():
        raise ValueError("gap samples must be finite")
    return paired_failure_counts(np.any(mse <= 0.0, axis=1), np.any(da <= 0.0, axis=1))


def paired_failure_counts(mse_fail: np.ndarray, da_fail: np.ndarray) -> dict:
    mse_fail, da_fail = np.asarray(mse_fail), np.asarray(da_fail)
    if (mse_fail.dtype != bool or da_fail.dtype != bool or mse_fail.ndim != 1
            or mse_fail.size == 0 or mse_fail.shape != da_fail.shape):
        raise ValueError("paired failures must be nonempty Boolean vectors of equal shape")
    both_fail = int(np.sum(mse_fail & da_fail))
    both_ok = int(np.sum(~mse_fail & ~da_fail))
    b = int(np.sum(mse_fail & ~da_fail))
    c = int(np.sum(~mse_fail & da_fail))
    return dict(both_fail=both_fail, both_ok=both_ok, b=b, c=c,
                paired_n=int(mse_fail.size),
                observed_rel_reduction=(b-c)/(both_fail+b) if both_fail+b else None)


def _count(value, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not np.isfinite(value) or int(value) != value or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return int(value)


def paired_test_rejects(*, b: int, c: int, n: int, alpha: float) -> bool:
    """Exact one-sided McNemar test; independent pairs are assumed.

    b counts MSE failures with DA success; c counts the reverse. Repeated
    decisions within one instance need cluster-aware inference separately.
    """
    b, c, n = _count(b, "b"), _count(c, "c"), _count(n, "n")
    if b+c > n or not 0 < alpha < 1:
        raise ValueError("Require b+c <= n and 0 < alpha < 1")
    return bool(b+c > 0 and binom.sf(b-1, b+c, 0.5) <= alpha)


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
        (failure_mse - failure_da) / failure_mse if failure_mse > 0.0 else None
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
        "observed_rel_reduction_pooled": rel_reduction,
        "observed_effect_meets_target": bool(rel_reduction is not None and rel_reduction >= MIN_DETECTABLE_RELATIVE_FAILURE_REDUCTION),
    }


def static_power(
    *,
    pooled_counts: dict[str, object],
    paired_decisions: int,
    alpha: float,
    repetitions: int,
) -> float:
    probabilities = _pair_probabilities(pooled_counts)
    n = _count(paired_decisions, "paired_decisions")
    repetitions = _count(repetitions, "repetitions")
    if n == 0 or repetitions == 0 or not 0 < alpha < 1:
        raise ValueError("Require positive simulation sizes and 0 < alpha < 1")
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


def _pair_probabilities(pooled_counts: dict) -> np.ndarray:
    counts = np.array([_count(pooled_counts[k], k) for k in ("both_fail", "both_ok", "b", "c")], dtype=float)
    if counts.sum() <= 0:
        raise ValueError("At least one observed pair is required")
    return counts / counts.sum()


def exact_iid_power(*, pooled_counts: dict, paired_decisions: int, alpha: float) -> float:
    """Exact power of the plug-in iid multinomial planning model, not cluster power.

    Condition on D discordant pairs, then B | D ~ Binomial(D, p_b/(p_b+p_c)).
    Summing rejection probabilities removes Monte Carlo rounding to 1.
    """
    probabilities = _pair_probabilities(pooled_counts)
    n = _count(paired_decisions, "paired_decisions")
    if n == 0 or not 0 < alpha < 1:
        raise ValueError("Require positive paired_decisions and 0 < alpha < 1")
    pd = probabilities[2] + probabilities[3]
    if pd == 0:
        return 0.0
    discordant = np.arange(n+1)
    critical = binom.ppf(1-alpha, discordant, .5).astype(int) + 1
    # Check the discrete tail directly, including exact boundary equality.
    critical -= (binom.sf(critical-2, discordant, .5) <= alpha)
    tail = binom.sf(critical-1, discordant, probabilities[2]/pd)
    return float(np.dot(binom.pmf(discordant, n, pd), tail))


def exact_method_failures(estimates: np.ndarray, x_star: int, budget: int, coefficients: dict) -> dict:
    counts = integer_shot_sums(estimates, budget)
    competitors = [i for i in range(counts.shape[2]) if i != x_star]
    if not competitors or not 0 <= x_star < counts.shape[2]:
        raise ValueError("Invalid optimum or candidate menu")
    return {
        "Raw": np.any(counts[:, 0, competitors] <= counts[:, 0, [x_star]], axis=1),
        "Accuracy-ZNE": zne_failures(estimates, x_star, budget),
        "Decision-ZNE": zne_failures(estimates, x_star, budget, coefficients=coefficients["Decision-ZNE"]),
    }


def build_power_table(
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    *,
    config: dict | None = None,
    profile: str = "full",
    raw_path_func=raw_relpath,
    expected_profile: str | None = "full",
    evidence_dir: Path | None = None,
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
        if (budgets != sorted(map(int, config["budget_grid"]))
                or metadata.get("budget_grid") != budgets
                or metadata.get("instance_id") != instance_id
                or str(raw["instance_id"].item()) != instance_id
                or estimates.shape != (int(config["replicates"]), 3, int(config["candidate_count"]), len(budgets))
                or metadata.get("candidate_count") != len(ideal_values)
                or metadata.get("replicates") != estimates.shape[0]
                or ideal_values.shape != (int(config["candidate_count"]),)
                or not np.isfinite(ideal_values).all()
                or x_star != int(np.argmin(ideal_values))
                or not np.array_equal(raw["zne_lambdas"], [1., 2., 3.])
                or list(config["zne_lambdas"]) != [1., 2., 3.]
                or config["zne_order"] != 1):
            raise ValueError(f"{instance_id}: raw/config mismatch")
        raw.close()
        for budget_idx, budget in enumerate(budgets):
            primitive = estimates[:, :, :, budget_idx]
            # Reject incompatible shot records before fitting or taking decisions.
            integer_shot_sums(primitive, budget)
            gap_samples, coefficients = _method_gap_samples(
                estimates, ideal_values, x_star, budget_idx, config, return_coefficients=True)
            objective_samples = {method: np.einsum("s,rsc->rc", coefficients[method], primitive)
                                 for method in config["method_menu_core"]}
            mse_by_method = method_mse_by_method(objective_samples, ideal_values)
            gri_by_method = method_gri_by_method(
                gap_samples,
                shrinkage=bool(config["use_ledoit_wolf"]),
            )
            mse_method = mse_selector(mse_by_method)
            da_method = da_selector(gri_by_method, gri_valid=True)
            failures = exact_method_failures(primitive, x_star, budget, coefficients)
            failure_mse = float(np.mean(failures[mse_method]))
            failure_da = float(np.mean(failures[da_method]))
            failure_raw = float(np.mean(failures["Raw"]))
            paired = paired_failure_counts(failures[mse_method], failures[da_method])
            if evidence_dir is not None:
                evidence_dir.mkdir(parents=True, exist_ok=True)
                methods = list(config["method_menu_core"])
                np.savez_compressed(evidence_dir / f"{instance_id}_B{budget}.npz",
                    shot_sums=integer_shot_sums(primitive, budget), budget=budget, x_star=x_star,
                    ideal_values=ideal_values, methods=np.array(methods),
                    coefficients=np.array([coefficients[m] for m in methods]),
                    failures=np.array([failures[m] for m in methods]),
                    mse=np.array([mse_by_method[m] for m in methods]),
                    gri=np.array([gri_by_method[m] for m in methods]),
                    selected=np.array([mse_method, da_method]))
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


def planning_summary(table: pd.DataFrame, primary: dict | None) -> dict:
    n = CONFIRMATORY_INSTANCES * CONFIRMATORY_REPLICATES
    result = dict(scope="same_sample_oracle_pilot_planning", independent_pairs_assumed=True,
                  cluster_power_established=False, minimum_detectable_effect_established=False,
                  primary_cell=None if primary is None else str(primary["cell"]),
                  primary_budget=None if primary is None else int(primary["budget"]),
                  planned_pairs=n, alpha=ALPHA, effect_target=MIN_DETECTABLE_RELATIVE_FAILURE_REDUCTION)
    if primary is not None:
        pooled = pooled_observed_effect(table, int(primary["budget"]))
        result.update(pooled=pooled, exact_iid_plugin_power=exact_iid_power(
            pooled_counts=pooled, paired_decisions=n, alpha=ALPHA),
            monte_carlo_iid_plugin_power=static_power(pooled_counts=pooled,
            paired_decisions=n, alpha=ALPHA, repetitions=BOOTSTRAP_REPETITIONS),
            monte_carlo_repetitions=BOOTSTRAP_REPETITIONS)
    return result


def render_report(*, output_root: Path, table: pd.DataFrame, primary: dict | None,
                  summary: dict | None = None) -> Path:
    out = output_root / REPORT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    summary = planning_summary(table, primary) if summary is None else summary
    lines = ["# Pilot planning diagnostic", "",
        "The same pilot samples fit the coefficients, select the methods and evaluate failure. Ideal margins enter the fit. These are descriptive oracle results, not held-out performance.", "",
        "Failure includes every exact tie, reconstructed from integer MaxCut shot sums and exact rational comparison keys. Relative reduction is undefined when baseline failure is zero.", "",
        "B is shots per candidate per noise scale: Raw uses B and ZNE uses 3B. The selection menu shares primitive records. These cells do not compare equal total policy costs.", "",
        f"Primary rule: failure in [{CRITICAL_BAND_LOW}, {CRITICAL_BAND_HIGH}], maximum distance to band edges, then lower failure, budget and cell id. The chosen budget is a planning convention, not a certified theoretical B*.", "",
        "Power uses the exact one-sided McNemar test under a plug-in iid multinomial model of the pooled in-band pilot pairs. It assumes fixed selectors and independent future pairs with the same pooled probabilities. It does not account for instance clustering, fitting/selection uncertainty, or pilot-based choice of cells and budget.", "",
        "The 48 x 40 design below is the historical planning target, not a claim about the size or power of the completed campaign. Comparing the observed reduction to 0.15 does not establish a minimum detectable effect or power at that target. A Monte Carlo value of 1 is not certainty.", "",
        "## Planning summary", "", "```json", json.dumps(summary, indent=2, allow_nan=False), "```", "",
        "## All pilot cells", "",
        "| cell | B | MSE method | GRI method | MSE failure | GRI failure | Raw failure | relative reduction | b | c | in band |",
        "|---|---:|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for row in table.sort_values(["cell", "budget"]).to_dict("records"):
        reduction = row["observed_rel_reduction"]
        label = "undefined" if pd.isna(reduction) else f"{reduction:.9g}"
        lines.append("| {cell} | {budget} | {MSE_selected_method} | {DA_selected_method} | "
            "{failure_rate_MSE:.9g} | {failure_rate_DA:.9g} | {failure_rate_Raw:.9g} | ".format(**row)
            + label + " | {b} | {c} | {in_band} |".format(**row))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def run(output_root: Path = DEFAULT_OUTPUT_ROOT) -> dict[str, object]:
    config = load_gate0_config("full")
    table = build_power_table(output_root, config=config, evidence_dir=output_root / "pilot/power_evidence")
    primary = choose_primary_cell(table)
    summary = planning_summary(table, primary)
    render_report(output_root=output_root, table=table, primary=primary, summary=summary)
    (output_root / "pilot/power_config_used.json").write_text(json.dumps(config, indent=2)+"\n", encoding="utf-8")
    table.to_json(output_root / "pilot/power_table.json", orient="records", indent=2, double_precision=15)
    (output_root / "pilot/power_summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    result = dict(output=REPORT_REL.as_posix(), rows=len(table), critical_band_rows=int(table["in_band"].sum()),
                  primary_cell=summary["primary_cell"], primary_budget=summary["primary_budget"])
    print(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()
    run(Path(args.output).resolve())


if __name__ == "__main__":
    main()
