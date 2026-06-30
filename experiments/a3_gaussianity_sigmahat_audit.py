from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
import yaml
from scipy import stats

from daqem.gap_kernel import nearest_psd
from daqem.risk import gri_risk
from daqem.rng import make_rng
from experiments.a3_pullback_frontier import (
    FROZEN_REL_DIR,
    _covariance,
    _method_samples_from_raw,
    _order_label,
)
from experiments.gate0_pilot_full_vs_diagonal import empirical_decision_failure_rate, raw_relpath


CONFIG_PATH = REPO_ROOT / "reproducibility" / "config" / "a3_gaussianity.yaml"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "results"
GAUSSIANITY_REL = Path("pilot") / "a3_gaussianity.md"
SIGMAHAT_AUDIT_REL = Path("pilot") / "a3_sigmahat_audit.md"


def load_config(profile: str = "smoke") -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    profiles = raw.get("profiles", {})
    if profile not in profiles:
        raise ValueError(f"unknown F1c-A profile: {profile}")
    config = dict(raw.get("defaults", {}))
    config.update(profiles[profile])
    config["profile"] = profile
    return config


def load_raw_frozen(output_root: Path, instance_id: str):
    raw_path = output_root / raw_relpath(instance_id)
    frozen_path = output_root / FROZEN_REL_DIR / f"{instance_id}.npz"
    if not raw_path.exists():
        raise FileNotFoundError(raw_path)
    if not frozen_path.exists():
        raise FileNotFoundError(frozen_path)
    return (
        np.load(raw_path, allow_pickle=False),
        np.load(frozen_path, allow_pickle=False),
    )


def method_samples(raw, frozen, budget_idx: int) -> dict[str, np.ndarray]:
    method_names = [str(value) for value in frozen["method_names"]]
    return _method_samples_from_raw(
        raw,
        budget_idx=budget_idx,
        method_names=method_names,
        method_coefficients=np.asarray(frozen["method_coefficients"], dtype=float),
    )


def _anderson_reject_5(sample: np.ndarray) -> tuple[float, bool]:
    if np.std(sample, ddof=1) <= 0.0:
        return 0.0, False
    result = stats.anderson(sample, dist="norm", method="interpolate")
    if hasattr(result, "pvalue"):
        return float(result.statistic), bool(float(result.pvalue) < 0.05)
    levels = np.asarray(result.significance_level, dtype=float)
    idx = int(np.argmin(np.abs(levels - 5.0)))
    return float(result.statistic), bool(result.statistic > result.critical_values[idx])


def tail_ratios(sample: np.ndarray, thresholds: list[float]) -> dict[float, float]:
    standardized = (sample - np.mean(sample)) / max(float(np.std(sample, ddof=1)), 1e-12)
    ratios = {}
    for threshold in thresholds:
        empirical = float(np.mean(np.abs(standardized) > float(threshold)))
        normal = float(2.0 * stats.norm.sf(float(threshold)))
        ratios[float(threshold)] = empirical / normal if normal > 0.0 else 0.0
    return ratios


def henze_zirkler_statistic(samples: np.ndarray) -> float | None:
    x = np.asarray(samples, dtype=float)
    if x.ndim != 2 or x.shape[0] < 8 or x.shape[1] < 2:
        return None
    n, p = x.shape
    centered = x - np.mean(x, axis=0, keepdims=True)
    cov = np.cov(centered, rowvar=False, ddof=1)
    if np.linalg.matrix_rank(cov) < p:
        return None
    inv = np.linalg.pinv(cov)
    beta = (1.0 / np.sqrt(2.0)) * (((2.0 * p + 1.0) / 4.0) ** (1.0 / (p + 4.0))) * (
        n ** (1.0 / (p + 4.0))
    )
    diffs = centered[:, None, :] - centered[None, :, :]
    pairwise = np.einsum("...i,ij,...j->...", diffs, inv, diffs)
    mahal = np.einsum("...i,ij,...j->...", centered, inv, centered)
    term1 = float(np.mean(np.exp(-0.5 * beta * beta * pairwise)))
    term2 = float(
        2.0
        * ((1.0 + beta * beta) ** (-p / 2.0))
        * np.mean(np.exp(-0.5 * beta * beta / (1.0 + beta * beta) * mahal))
    )
    term3 = float((1.0 + 2.0 * beta * beta) ** (-p / 2.0))
    return float(n * (term1 - term2 + term3))


def gaussianity_rows(output_root: Path, config: dict) -> tuple[list[dict], list[dict]]:
    gaussian_rows = []
    calibration_rows = []
    for instance_id in config["instance_ids"]:
        raw, frozen = load_raw_frozen(output_root, instance_id)
        budgets = [int(value) for value in frozen["budgets"]]
        method_names = [str(value) for value in frozen["method_names"]]
        mu = np.asarray(frozen["mu"], dtype=float)
        active_masks = np.asarray(frozen["active_masks"], dtype=bool)
        for budget_idx, budget in enumerate(budgets):
            samples_by_method = method_samples(raw, frozen, budget_idx)
            for method_idx, method in enumerate(method_names):
                samples = samples_by_method[method]
                active = np.flatnonzero(active_masks[method_idx, budget_idx])
                active_samples = samples[:, active]
                flagged = []
                ad_stats = []
                skew_values = []
                kurt_values = []
                tail2 = []
                tail3 = []
                for local_idx, gap_idx in enumerate(active):
                    sample = active_samples[:, local_idx]
                    ad_stat, ad_reject = _anderson_reject_5(sample)
                    skew = float(stats.skew(sample, bias=False))
                    kurt = float(stats.kurtosis(sample, fisher=True, bias=False))
                    tails = tail_ratios(sample, list(config["tail_thresholds"]))
                    ratio2 = tails.get(2.0, 0.0)
                    ratio3 = tails.get(3.0, 0.0)
                    ad_stats.append(ad_stat)
                    skew_values.append(skew)
                    kurt_values.append(kurt)
                    tail2.append(ratio2)
                    tail3.append(ratio3)
                    if (
                        ad_reject
                        or abs(skew) > float(config["skew_abs_flag"])
                        or abs(kurt) > float(config["excess_kurtosis_abs_flag"])
                        or ratio2 < float(config["tail_ratio_low_flag"])
                        or ratio2 > float(config["tail_ratio_high_flag"])
                        or ratio3 < float(config["tail_ratio_low_flag"])
                        or ratio3 > float(config["tail_ratio_high_flag"])
                    ):
                        flagged.append(int(gap_idx))
                hz = (
                    henze_zirkler_statistic(active_samples)
                    if active_samples.shape[1] <= int(config["hz_max_dim"])
                    else None
                )
                gaussian_rows.append(
                    {
                        "problem_cell": instance_id,
                        "method": method,
                        "budget": budget,
                        "active_gaps": ",".join(str(int(i)) for i in active),
                        "flagged_gaps": ",".join(str(i) for i in flagged) or "none",
                        "max_anderson_darling": max(ad_stats) if ad_stats else 0.0,
                        "max_abs_skewness": max((abs(v) for v in skew_values), default=0.0),
                        "max_abs_excess_kurtosis": max((abs(v) for v in kurt_values), default=0.0),
                        "max_tail_ratio_2sigma": max(tail2, default=0.0),
                        "max_tail_ratio_3sigma": max(tail3, default=0.0),
                        "henze_zirkler": hz if hz is not None else float("nan"),
                    }
                )
                sigma = _covariance(samples, shrinkage=True)
                mu_sample = np.mean(samples, axis=0)
                gri_at_sample_mean = gri_risk(mu_sample, sigma, B=1.0)
                gri_at_true_mean = gri_risk(mu, sigma, B=1.0)
                empirical = empirical_decision_failure_rate(samples)
                abs_diff_gaussianity = abs(gri_at_sample_mean - empirical)
                abs_diff_true_mean = abs(gri_at_true_mean - empirical)
                calibration_rows.append(
                    {
                        "problem_cell": instance_id,
                        "method": method,
                        "budget": budget,
                        "gri_at_sample_mean": gri_at_sample_mean,
                        "gri_at_true_mean": gri_at_true_mean,
                        "empirical_failure_rate": empirical,
                        "abs_diff_gaussianity": abs_diff_gaussianity,
                        "abs_diff_true_mean": abs_diff_true_mean,
                        "tau_R": float(config["tau_R"]),
                        "valid_mask": bool(abs_diff_gaussianity <= float(config["tau_R"])),
                    }
                )
    return gaussian_rows, calibration_rows


def bootstrap_indices(
    *,
    n: int,
    count: int,
    instance_id: str,
    method: str,
    budget: int,
    stream: str,
) -> np.ndarray:
    rng = make_rng(
        instance_id=instance_id,
        method=method,
        budget=int(budget),
        replicate_id=0,
        stream=stream,
    )
    return rng.integers(0, int(n), size=(int(count), int(n)))


def joint_bootstrap_indices(
    *,
    n: int,
    count: int,
    instance_id: str,
    budget: int,
) -> np.ndarray:
    return bootstrap_indices(
        n=n,
        count=count,
        instance_id=instance_id,
        method="joint",
        budget=budget,
        stream="f1c_joint_bootstrap",
    )


def covariance_ci_summary(
    samples: np.ndarray,
    active: np.ndarray,
    *,
    indices: np.ndarray,
    ci: float,
) -> dict[str, float]:
    active_samples = samples[:, active]
    covariances = np.empty((indices.shape[0], active.size, active.size), dtype=float)
    for boot_idx, row in enumerate(indices):
        covariances[boot_idx] = _covariance(active_samples[row], shrinkage=True)
    alpha = (1.0 - float(ci)) / 2.0
    lower = np.quantile(covariances, alpha, axis=0)
    upper = np.quantile(covariances, 1.0 - alpha, axis=0)
    width = upper - lower
    diag_width = np.diag(width)
    offdiag = width[~np.eye(width.shape[0], dtype=bool)] if width.shape[0] > 1 else np.array([0.0])
    return {
        "max_cov_ci_width": float(np.max(width)),
        "max_diag_ci_width": float(np.max(diag_width)),
        "max_offdiag_ci_width": float(np.max(offdiag)),
    }


def risk_order(method_names: list[str], risks: np.ndarray) -> str:
    order = np.argsort(risks, kind="mergesort")
    return "<".join(method_names[int(idx)] for idx in order)


def projected_ratio_for_pair(
    *,
    sigma_left: np.ndarray,
    sigma_right: np.ndarray,
    sigma_pred_left: np.ndarray,
    sigma_pred_right: np.ndarray,
    grad_left: np.ndarray,
    grad_right: np.ndarray,
    tau: float,
    epsilon0: float,
) -> float:
    e_left = sigma_left - sigma_pred_left
    e_right = sigma_right - sigma_pred_right
    projected = abs(float(np.sum(grad_left * e_left)) - float(np.sum(grad_right * e_right)))
    return projected / max(float(tau), float(epsilon0))


def audit_rows_for_case(
    *,
    output_root: Path,
    instance_id: str,
    budget: int,
    config: dict,
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    raw, frozen = load_raw_frozen(output_root, instance_id)
    budgets = [int(value) for value in frozen["budgets"]]
    budget_idx = budgets.index(int(budget))
    method_names = [str(value) for value in frozen["method_names"]]
    mu = np.asarray(frozen["mu"], dtype=float)
    active_masks = np.asarray(frozen["active_masks"], dtype=bool)
    samples_by_method = method_samples(raw, frozen, budget_idx)
    n = next(iter(samples_by_method.values())).shape[0]
    boot_count = int(config["bootstrap_replicates"])
    ci = float(config["bootstrap_ci"])
    sigma_pred = np.asarray(frozen["sigma_pred"], dtype=float)
    gradients = np.asarray(frozen["gradients"], dtype=float)
    tau = np.asarray(frozen["tau_flip_projected"], dtype=float)
    pair_names = [str(value) for value in frozen["pair_names"]]
    epsilon0 = 1e-12

    ci_rows = []
    shrinkage_rows = []
    sufficiency_rows = []
    stability_rows = []

    full_risks_lw = []
    full_risks_raw = []
    active_risks_lw = []
    active_risks_raw = []
    for method_idx, method in enumerate(method_names):
        samples = samples_by_method[method]
        active = np.flatnonzero(active_masks[method_idx, budget_idx])
        indices = bootstrap_indices(
            n=n,
            count=boot_count,
            instance_id=instance_id,
            method=method,
            budget=budget,
            stream="f1c_sigmahat_bootstrap",
        )
        ci_summary = covariance_ci_summary(samples, active, indices=indices, ci=ci)
        ci_rows.append(
            {
                "problem_cell": instance_id,
                "method": method,
                "budget": budget,
                "active_dim": int(active.size),
                **ci_summary,
            }
        )

        sigma_lw = _covariance(samples, shrinkage=True)
        sigma_raw = _covariance(samples, shrinkage=False)
        risk_lw = gri_risk(mu, sigma_lw, B=1.0)
        risk_raw = gri_risk(mu, sigma_raw, B=1.0)
        full_risks_lw.append(risk_lw)
        full_risks_raw.append(risk_raw)
        active_risks_lw.append(gri_risk(mu[active], sigma_lw[np.ix_(active, active)], B=1.0))
        active_risks_raw.append(gri_risk(mu[active], sigma_raw[np.ix_(active, active)], B=1.0))
        shrinkage_rows.append(
            {
                "problem_cell": instance_id,
                "method": method,
                "budget": budget,
                "risk_ledoit_wolf": risk_lw,
                "risk_sample_cov": risk_raw,
                "abs_risk_shift": abs(risk_lw - risk_raw),
            }
        )

        for size in config["subsample_sizes"]:
            size = int(size)
            if size > n:
                continue
            rng = make_rng(
                instance_id=instance_id,
                method=method,
                budget=budget,
                replicate_id=size,
                stream="f1c_sigmahat_subsample",
            )
            chosen = rng.choice(n, size=size, replace=False)
            risk_sub = gri_risk(mu, _covariance(samples[chosen], shrinkage=True), B=1.0)
            sufficiency_rows.append(
                {
                    "problem_cell": instance_id,
                    "method": method,
                    "budget": budget,
                    "subsample_R": size,
                    "risk_subsample": risk_sub,
                    "risk_full_R": risk_lw,
                    "abs_risk_shift_from_full": abs(risk_sub - risk_lw),
                }
            )

    full_order = risk_order(method_names, np.asarray(active_risks_lw, dtype=float))
    raw_order = risk_order(method_names, np.asarray(active_risks_raw, dtype=float))
    boot_orders = []
    joint_indices = joint_bootstrap_indices(
        n=n,
        count=boot_count,
        instance_id=instance_id,
        budget=budget,
    )
    for boot_idx in range(boot_count):
        risks = []
        for method_idx, method in enumerate(method_names):
            samples = samples_by_method[method]
            active = np.flatnonzero(active_masks[method_idx, budget_idx])
            sigma = _covariance(samples[joint_indices[boot_idx]], shrinkage=True)
            risks.append(
                gri_risk(
                    mu[active],
                    sigma[np.ix_(active, active)],
                    B=1.0,
                )
            )
        boot_orders.append(risk_order(method_names, np.asarray(risks, dtype=float)))
    stability_rows.append(
        {
            "problem_cell": instance_id,
            "budget": budget,
            "ordering_ledoit_wolf": full_order,
            "ordering_sample_cov": raw_order,
            "bootstrap_ordering_stability": float(np.mean([order == full_order for order in boot_orders])),
        }
    )

    # Focused A3 ratio bootstrap for active pairs at this case.
    for pair_idx, pair_name in enumerate(pair_names):
        left, right = pair_name.split("_vs_")
        left_idx = method_names.index(left)
        right_idx = method_names.index(right)
        baseline_ratio = projected_ratio_for_pair(
            sigma_left=_covariance(samples_by_method[left], shrinkage=True),
            sigma_right=_covariance(samples_by_method[right], shrinkage=True),
            sigma_pred_left=sigma_pred[left_idx, budget_idx],
            sigma_pred_right=sigma_pred[right_idx, budget_idx],
            grad_left=gradients[left_idx, budget_idx],
            grad_right=gradients[right_idx, budget_idx],
            tau=float(tau[pair_idx, budget_idx]),
            epsilon0=epsilon0,
        )
        ratios = np.empty(boot_count, dtype=float)
        for boot_idx in range(boot_count):
            row_indices = joint_indices[boot_idx]
            ratios[boot_idx] = projected_ratio_for_pair(
                sigma_left=_covariance(samples_by_method[left][row_indices], shrinkage=True),
                sigma_right=_covariance(samples_by_method[right][row_indices], shrinkage=True),
                sigma_pred_left=sigma_pred[left_idx, budget_idx],
                sigma_pred_right=sigma_pred[right_idx, budget_idx],
                grad_left=gradients[left_idx, budget_idx],
                grad_right=gradients[right_idx, budget_idx],
                tau=float(tau[pair_idx, budget_idx]),
                epsilon0=epsilon0,
            )
        lower, upper = np.quantile(ratios, [(1.0 - ci) / 2.0, 1.0 - (1.0 - ci) / 2.0])
        if lower <= 1.0 <= upper:
            verdict = "ci_includes_1_sampling_sensitive"
        elif lower > 1.0:
            verdict = "robust_fail"
        elif upper < 1.0:
            verdict = "robust_pass"
        else:
            verdict = "diagnostic"
        stability_rows.append(
            {
                "problem_cell": instance_id,
                "budget": budget,
                "pair_id": pair_name,
                "baseline_projected_ratio": baseline_ratio,
                "bootstrap_ratio_ci_low": float(lower),
                "bootstrap_ratio_ci_high": float(upper),
                "bootstrap_fail_fraction": float(np.mean(ratios >= 1.0)),
                "verdict": verdict,
            }
        )

    return ci_rows, shrinkage_rows, sufficiency_rows, stability_rows


def render_gaussianity_report(
    output_root: Path,
    gaussian_rows: list[dict],
    calibration_rows: list[dict],
    config: dict,
) -> None:
    out = output_root / GAUSSIANITY_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# A3 Gaussianity And GRI Calibration Smoke",
        "",
        "Diagnostic only: not canonical, not part of verify/reference.",
        "",
        f"- tau_R: {config['tau_R']}",
        "",
        "## Gaussianity On Active Gaps",
        "",
        "| cell | method | B | active_gaps | flagged_gaps | AD_max | skew_max | kurtosis_max | tail2_max | tail3_max | HZ |",
        "|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in gaussian_rows:
        hz = row["henze_zirkler"]
        hz_text = "NA" if not np.isfinite(hz) else f"{hz:.6g}"
        lines.append(
            "| {problem_cell} | {method} | {budget} | {active_gaps} | {flagged_gaps} | "
            "{max_anderson_darling:.6g} | {max_abs_skewness:.6g} | "
            "{max_abs_excess_kurtosis:.6g} | {max_tail_ratio_2sigma:.6g} | "
            "{max_tail_ratio_3sigma:.6g} | "
            f"{hz_text} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## GRI vs Empirical Failure",
            "",
            "| cell | method | B | GRI_sample_mean | GRI_true_mean | empirical_failure | abs_diff_gaussianity | abs_diff_true_mean | tau_R | valid |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in calibration_rows:
        lines.append(
            "| {problem_cell} | {method} | {budget} | {gri_at_sample_mean:.6g} | "
            "{gri_at_true_mean:.6g} | {empirical_failure_rate:.6g} | "
            "{abs_diff_gaussianity:.6g} | {abs_diff_true_mean:.6g} | "
            "{tau_R:.6g} | {valid_mask} |".format(**row)
        )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_sigmahat_report(
    output_root: Path,
    ci_rows: list[dict],
    shrinkage_rows: list[dict],
    sufficiency_rows: list[dict],
    stability_rows: list[dict],
    config: dict,
) -> None:
    out = output_root / SIGMAHAT_AUDIT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# A3 Finite-Sample Sigmahat Audit Smoke",
        "",
        "Diagnostic only: not canonical, not part of verify/reference.",
        "",
        f"- bootstrap_replicates: {config['bootstrap_replicates']}",
        f"- bootstrap_CI: {config['bootstrap_ci']}",
        "",
        "## Active Covariance Bootstrap CI Widths",
        "",
        "| cell | method | B | active_dim | max_cov_width | max_diag_width | max_offdiag_width |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in ci_rows:
        lines.append(
            "| {problem_cell} | {method} | {budget} | {active_dim} | "
            "{max_cov_ci_width:.6g} | {max_diag_ci_width:.6g} | "
            "{max_offdiag_ci_width:.6g} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Shrinkage Sensitivity",
            "",
            "| cell | method | B | risk_LW | risk_sample_cov | abs_shift |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in shrinkage_rows:
        lines.append(
            "| {problem_cell} | {method} | {budget} | {risk_ledoit_wolf:.6g} | "
            "{risk_sample_cov:.6g} | {abs_risk_shift:.6g} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Replicate Count Sufficiency",
            "",
            "| cell | method | B | subsample_R | risk_subsample | risk_full_R | abs_shift |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in sufficiency_rows:
        lines.append(
            "| {problem_cell} | {method} | {budget} | {subsample_R} | "
            "{risk_subsample:.6g} | {risk_full_R:.6g} | "
            "{abs_risk_shift_from_full:.6g} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Ordering And P003 B=256 Projected-Ratio Bootstrap",
            "",
            "| cell | B | item | baseline/order | CI_low | CI_high | fail_fraction/stability | verdict |",
            "|---|---:|---|---|---:|---:|---:|---|",
        ]
    )
    for row in stability_rows:
        if "pair_id" in row:
            lines.append(
                "| {problem_cell} | {budget} | {pair_id} | {baseline_projected_ratio:.6g} | "
                "{bootstrap_ratio_ci_low:.6g} | {bootstrap_ratio_ci_high:.6g} | "
                "{bootstrap_fail_fraction:.6g} | {verdict} |".format(**row)
            )
        else:
            lines.append(
                "| {problem_cell} | {budget} | ordering | {ordering_ledoit_wolf} | "
                "NA | NA | {bootstrap_ordering_stability:.6g} | "
                "sample_cov={ordering_sample_cov} |".format(**row)
            )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(output_root: Path = DEFAULT_OUTPUT_ROOT, *, profile: str = "smoke") -> dict:
    start = time.perf_counter()
    config = load_config(profile)
    gaussian_rows, calibration_rows = gaussianity_rows(output_root, config)

    ci_rows = []
    shrinkage_rows = []
    sufficiency_rows = []
    stability_rows = []
    audit_cases = [(instance_id, int(budget)) for instance_id in config["instance_ids"] for budget in np.load(output_root / FROZEN_REL_DIR / f"{instance_id}.npz", allow_pickle=False)["budgets"]]
    for focus in config.get("focus_cases", []):
        case = (str(focus["instance_id"]), int(focus["budget"]))
        if case not in audit_cases:
            audit_cases.append(case)
    for instance_id, budget in audit_cases:
        ci, shrink, suff, stable = audit_rows_for_case(
            output_root=output_root,
            instance_id=instance_id,
            budget=budget,
            config=config,
        )
        ci_rows.extend(ci)
        shrinkage_rows.extend(shrink)
        sufficiency_rows.extend(suff)
        stability_rows.extend(stable)

    render_gaussianity_report(output_root, gaussian_rows, calibration_rows, config)
    render_sigmahat_report(
        output_root,
        ci_rows,
        shrinkage_rows,
        sufficiency_rows,
        stability_rows,
        config,
    )
    result = {
        "profile": profile,
        "instances": config["instance_ids"],
        "tau_R": float(config["tau_R"]),
        "gaussianity_rows": len(gaussian_rows),
        "calibration_rows": len(calibration_rows),
        "audit_cases": len(audit_cases),
        "duration_seconds": time.perf_counter() - start,
        "outputs": [GAUSSIANITY_REL.as_posix(), SIGMAHAT_AUDIT_REL.as_posix()],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--profile", default="smoke")
    args = parser.parse_args(argv)
    run(Path(args.output).resolve(), profile=args.profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
