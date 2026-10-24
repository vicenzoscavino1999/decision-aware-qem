"""Plot the three E3 comparisons from matching, validated source tables."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
KEYS = ["instance", "budget", "pair"]
INPUT_ORDERS = [
    "old_covariance_order", "old_all40_failure_order",
    "method_mean_train_order", "test_failure_order",
]


def _validate_keys(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    frame = frame.copy()
    if frame[KEYS].isna().any().any():
        raise ValueError(f"{label}: missing instance, budget or pair")
    for col in ("instance", "pair"):
        if not frame[col].map(lambda v: isinstance(v, str) and bool(v.strip())).all():
            raise ValueError(f"{label}: invalid {col}")
    budgets = pd.to_numeric(frame.budget, errors="raise")
    if not (np.isfinite(budgets) & (budgets > 0) & (budgets == np.floor(budgets))).all():
        raise ValueError(f"{label}: budgets must be positive integers")
    frame["budget"] = budgets.astype(np.int64)
    if frame.duplicated(KEYS).any():
        raise ValueError(f"{label}: duplicate instance/budget/pair")
    return frame


def _require_columns(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"{label}: missing columns {sorted(missing)}")


def _validate_orders(frame: pd.DataFrame, columns: list[str]) -> None:
    for pair, group in frame.groupby("pair", sort=False):
        parts = pair.split("_vs_")
        if len(parts) != 2 or not all(parts) or parts[0] == parts[1]:
            raise ValueError(f"Invalid method pair: {pair!r}")
        left, right = parts
        allowed = {"tie", f"{left}<{right}", f"{right}<{left}"}
        for col in columns:
            if not group[col].isin(allowed).all():
                raise ValueError(f"Invalid order label in {col} for {pair}")


def comparison_series(comparisons: pd.DataFrame, frontier: pd.DataFrame) -> pd.DataFrame:
    """Calculate strict matches; all active pairs, including ties, stay in denominators."""
    _require_columns(comparisons, KEYS + INPUT_ORDERS, "comparisons")
    _require_columns(frontier, ["problem_cell", "budget", "pair_id", "active_pair",
                                "predicted_order", "empirical_order"], "frontier")
    comparisons = _validate_keys(comparisons[KEYS + INPUT_ORDERS], "comparisons")
    frontier = frontier[["problem_cell", "budget", "pair_id", "active_pair",
                         "predicted_order", "empirical_order"]].rename(
        columns={"problem_cell": "instance", "pair_id": "pair",
                 "predicted_order": "frontier_prediction", "empirical_order": "frontier_estimate"})
    frontier = _validate_keys(frontier, "frontier")
    active = frontier.active_pair.map(lambda value: str(value).strip().lower())
    if not active.isin(["true", "false"]).all():
        raise ValueError("frontier: active_pair must contain only True/False")
    frontier = frontier.loc[active == "true"].drop(columns="active_pair")
    if comparisons.empty or frontier.empty:
        raise ValueError("No active pairs to plot")
    joined = comparisons.merge(frontier, on=KEYS, how="outer", validate="one_to_one", indicator=True)
    if (joined["_merge"] != "both").any():
        raise ValueError("The comparisons and frontier must contain exactly the same active keys")
    _validate_orders(joined, INPUT_ORDERS + ["frontier_prediction", "frontier_estimate"])
    if not (joined.old_covariance_order == joined.frontier_prediction).all():
        raise ValueError("Covariance predictions disagree between the two input tables")

    rows = []
    for budget, group in joined.groupby("budget", sort=True):
        row = {"budget": int(budget), "active_pairs": len(group)}
        for label, predicted, observed in (
            ("covariance", "frontier_prediction", "frontier_estimate"),
            ("historical_failure", "old_covariance_order", "old_all40_failure_order"),
            ("method_mean", "method_mean_train_order", "test_failure_order"),
        ):
            strict = (group[predicted] == group[observed]) & (group[predicted] != "tie")
            row[f"{label}_matches"] = int(strict.sum())
            row[f"{label}_fraction"] = float(strict.mean())
        rows.append(row)
    return pd.DataFrame(rows)


def render_figure(series: pd.DataFrame, output: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    budgets = series.budget.to_numpy()
    fig, ax = plt.subplots(figsize=(7.4, 4.3))
    try:
        ax.plot(budgets, series.covariance_fraction, "o-", color="#0072B2",
                label="Fixed ideal mean: predicted vs estimated covariance score")
        ax.plot(budgets, series.historical_failure_fraction, "s-", color="#D55E00",
                label="Covariance prediction vs observed failure (40 repetitions)")
        ax.plot(budgets, series.method_mean_fraction, "^-", color="#009E73",
                label="Method-specific mean (20 train) vs failure (20 test)")
        for row in series.itertuples():
            ax.annotate(f"n={row.active_pairs}", (row.budget, row.covariance_fraction),
                        xytext=(0, 7), textcoords="offset points", ha="center", fontsize=8)
        ax.set_xscale("log", base=2)
        ax.set_xticks(budgets, labels=budgets)
        ax.set(xlabel="Archived nominal budget", ylabel="Strict order matches / all active pairs",
               ylim=(0, 1.13), title="Three distinct E3 comparisons")
        ax.grid(alpha=.2)
        ax.legend(loc="lower left", frameon=False, fontsize=8)
        fig.tight_layout()
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output)
    finally:
        plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "results/e3_independent_mean_and_failure.csv")
    parser.add_argument("--frontier", type=Path,
                        default=ROOT / "inputs/results/confirmatory/e3_pullback_frontier.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "manuscript/figures/F9_e3_comparisons.pdf")
    parser.add_argument("--series-output", type=Path, help="Optional CSV of the plotted counts and fractions")
    args = parser.parse_args(argv)
    series = comparison_series(pd.read_csv(args.input), pd.read_csv(args.frontier))
    render_figure(series, args.output)
    if args.series_output is not None:
        args.series_output.parent.mkdir(parents=True, exist_ok=True)
        series.to_csv(args.series_output, index=False)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
