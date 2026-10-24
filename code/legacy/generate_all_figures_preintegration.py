from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


REPO_ROOT = Path(__file__).resolve().parents[1]
FIGURE_DIR = REPO_ROOT / "figures"

PROOF_JSON = REPO_ROOT / "reproducibility/reference_extension/proof_of_mechanism/result.json"
CLAIMS_JSON = REPO_ROOT / "reproducibility/reference_confirmatory/confirmatory_claims_summary.json"
E1_CSV = REPO_ROOT / "reproducibility/reference_confirmatory/e1/e1_static_decision_failure.csv"
E3_CSV = REPO_ROOT / "reproducibility/reference_confirmatory/e3/e3_pullback_frontier.csv"
GATE0_CSV = REPO_ROOT / "results/pilot/gate0_full_vs_diagonal.csv"

PDFS = [
    "F1_accuracy_decision_separation.pdf",
    "F3_dynamic_success.pdf",
    "F4_e1_epsilon_terciles.pdf",
    "F5_e3_directional_ordering.pdf",
    "F6_gate0_full_vs_diagonal.pdf",
]


def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"required figure source is missing: {path}")


def load_json(path: Path) -> dict:
    require_file(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    require_file(path)
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def as_float(value: str | int | float) -> float:
    return float(value)


def as_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    lowered = value.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise ValueError(f"not a boolean value: {value!r}")


def savefig(name: str) -> Path:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURE_DIR / name
    plt.tight_layout()
    plt.savefig(path, format="pdf", bbox_inches="tight")
    plt.close()
    return path


def figure_f1() -> Path:
    data = load_json(PROOF_JSON)
    rows = data["aggregate"]["table"]
    methods = ["Raw", "CDR", "PEC"]
    by_method = {method: [] for method in methods}
    for row in rows:
        method = row["method"]
        if method in by_method:
            by_method[method].append(row)
    for method, method_rows in by_method.items():
        if not method_rows:
            raise ValueError(f"F1 missing method in proof-of-mechanism aggregate: {method}")
        method_rows.sort(key=lambda r: r["budget"])

    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.4), sharex=True)
    markers = {"Raw": "o", "CDR": "s", "PEC": "^"}
    labels = {"Raw": "Raw", "CDR": "CDR affine control", "PEC": "PEC proxy"}
    for method in methods:
        budgets = [row["budget"] for row in by_method[method]]
        mse = [row["MSE_mean"] for row in by_method[method]]
        gri = [row["GRI_mean"] for row in by_method[method]]
        axes[0].plot(budgets, mse, marker=markers[method], label=labels[method])
        axes[1].plot(budgets, gri, marker=markers[method], label=labels[method])

    axes[0].set_title("Estimator accuracy")
    axes[0].set_ylabel("MSE")
    axes[0].set_xscale("log", base=2)
    axes[0].grid(True, alpha=0.25)
    axes[1].set_title("Decision risk")
    axes[1].set_ylabel("GRI")
    axes[1].set_xscale("log", base=2)
    axes[1].grid(True, alpha=0.25)
    for axis in axes:
        axis.set_xlabel("Evaluation budget per candidate")
    axes[1].legend(frameon=False, loc="best")
    fig.suptitle("Accuracy-decision separation", y=1.02)
    return savefig("F1_accuracy_decision_separation.pdf")


def figure_f3() -> Path:
    data = load_json(CLAIMS_JSON)
    success = data["e2"]["aggregate_success_decision"]
    threshold = 0.80
    budgets = sorted(int(value) for value in success["DA"].keys())

    plt.figure(figsize=(5.5, 3.5))
    for selector, marker in [("DA", "o"), ("MSE", "s")]:
        values = [success[selector][str(budget)] for budget in budgets]
        plt.plot(budgets, values, marker=marker, label=selector)
    plt.axhline(threshold, color="black", linestyle="--", linewidth=1, label="0.80 target")
    plt.xscale("log", base=2)
    plt.ylim(0.4, 0.86)
    plt.xlabel("Nominal budget")
    plt.ylabel("P(success)")
    plt.title("Dynamic success-to-budget endpoint")
    plt.grid(True, alpha=0.25)
    plt.legend(frameon=False)
    return savefig("F3_dynamic_success.pdf")


def figure_f4() -> Path:
    rows = load_csv(E1_CSV)
    grouped: dict[str, dict[str, float]] = defaultdict(lambda: {"mse_fail": 0.0, "da_fail": 0.0})
    for row in rows:
        if int(row["budget"]) != 512:
            continue
        tercile = row["epsilon_opt_tercile"]
        both_fail = as_float(row["both_fail"])
        b_da_better = as_float(row["b"])
        c_da_worse = as_float(row["c"])
        grouped[tercile]["mse_fail"] += both_fail + b_da_better
        grouped[tercile]["da_fail"] += both_fail + c_da_worse

    order = ["easy", "medium", "hard"]
    reductions = []
    for tercile in order:
        if tercile not in grouped:
            raise ValueError(f"F4 missing epsilon tercile at B*=512: {tercile}")
        mse_fail = grouped[tercile]["mse_fail"]
        da_fail = grouped[tercile]["da_fail"]
        reductions.append((mse_fail - da_fail) / mse_fail if mse_fail else 0.0)

    plt.figure(figsize=(5.5, 3.5))
    plt.bar(order, reductions, color=["#4C78A8", "#F58518", "#54A24B"])
    plt.axhline(0.15, color="black", linestyle="--", linewidth=1, label="Practical threshold")
    plt.ylabel("Relative failure reduction")
    plt.xlabel("epsilon_opt tercile")
    plt.title("Static decision improvement by difficulty")
    plt.ylim(0, max(0.35, max(reductions) * 1.2))
    plt.grid(True, axis="y", alpha=0.25)
    plt.legend(frameon=False)
    return savefig("F4_e1_epsilon_terciles.pdf")


def figure_f5() -> Path:
    rows = load_csv(E3_CSV)
    grouped: dict[int, dict[str, float]] = defaultdict(lambda: {"active": 0.0, "match": 0.0})
    for row in rows:
        if not as_bool(row["active_pair"]):
            continue
        budget = int(row["budget"])
        grouped[budget]["active"] += 1.0
        grouped[budget]["match"] += 1.0 if as_bool(row["ordering_match"]) else 0.0
    if not grouped:
        raise ValueError("F5 has no active E3 pairs")

    budgets = sorted(grouped)
    fractions = [grouped[budget]["match"] / grouped[budget]["active"] for budget in budgets]
    counts = [int(grouped[budget]["active"]) for budget in budgets]

    plt.figure(figsize=(5.5, 3.5))
    plt.plot(budgets, fractions, marker="o", color="#4C78A8")
    for budget, fraction, count in zip(budgets, fractions, counts):
        plt.text(budget, min(1.02, fraction + 0.015), f"n={count}", ha="center", fontsize=8)
    plt.xscale("log", base=2)
    plt.ylim(0, 1.08)
    plt.xlabel("Budget")
    plt.ylabel("Predicted/observed ordering match")
    plt.title("A3 directional ordering validation")
    plt.grid(True, alpha=0.25)
    return savefig("F5_e3_directional_ordering.pdf")


def figure_f6() -> Path:
    rows = load_csv(GATE0_CSV)
    if not rows:
        raise ValueError("F6 Gate0 CSV is empty")

    changed = [row for row in rows if as_bool(row["selector_changed"])]
    unchanged = [row for row in rows if not as_bool(row["selector_changed"])]

    plt.figure(figsize=(4.8, 4.4))
    for label, group, marker, color in [
        ("selector unchanged", unchanged, "o", "#4C78A8"),
        ("selector changed", changed, "x", "#E45756"),
    ]:
        if not group:
            continue
        x = [as_float(row["gri_diagonal"]) for row in group]
        y = [as_float(row["gri_full"]) for row in group]
        plt.scatter(x, y, marker=marker, color=color, label=label, alpha=0.8)
    all_values = [as_float(row["gri_diagonal"]) for row in rows] + [as_float(row["gri_full"]) for row in rows]
    low = max(0.0, min(all_values) - 0.03)
    high = min(1.0, max(all_values) + 0.03)
    plt.plot([low, high], [low, high], color="black", linewidth=1, linestyle="--", label="full = diagonal")
    plt.xlim(low, high)
    plt.ylim(low, high)
    plt.xlabel("GRI diagonal")
    plt.ylabel("GRI full")
    plt.title("Gate 0 full-vs-diagonal risk")
    plt.grid(True, alpha=0.25)
    plt.legend(frameon=False, fontsize=8)
    return savefig("F6_gate0_full_vs_diagonal.pdf")


def main() -> int:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    generated = [
        figure_f1(),
        figure_f3(),
        figure_f4(),
        figure_f5(),
        figure_f6(),
    ]

    missing = [name for name in PDFS if not (FIGURE_DIR / name).exists()]
    if missing:
        raise RuntimeError(f"missing generated figures: {missing}")

    print(f"FIGURES PASS: generated={len(generated)}")
    for path in generated:
        print(f"wrote={path.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
