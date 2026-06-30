from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.proof_of_mechanism_run import (  # noqa: E402
    OUTPUT_DIR,
    instance_analytics,
    load_config,
    select_instances,
)


CSV_PATH = OUTPUT_DIR / "coexistence_by_instance.csv"
EXPECTED_SELECTED = [
    "POM_001",
    "POM_003",
    "POM_004",
    "POM_012",
    "POM_015",
    "POM_017",
    "POM_018",
    "POM_022",
]
EXPECTED_COUNTS = {
    768: {"mse_better": 5, "decision_worse": 8, "coexist": 5, "without": {"POM_004", "POM_015", "POM_018"}},
    1536: {"mse_better": 7, "decision_worse": 8, "coexist": 7, "without": {"POM_004"}},
    3072: {"mse_better": 8, "decision_worse": 7, "coexist": 7, "without": {"POM_004"}},
    6144: {"mse_better": 8, "decision_worse": 7, "coexist": 7, "without": {"POM_004"}},
}


def build_rows() -> list[dict]:
    config = load_config()
    budgets = [int(budget) for budget in config["budget_grid"]]
    selected = [row for row in select_instances(config) if row["selected"]]
    selected_ids = [str(row["instance_id"]) for row in selected]
    if selected_ids != EXPECTED_SELECTED:
        raise AssertionError(f"selected instances diverged: {selected_ids} != {EXPECTED_SELECTED}")

    rows: list[dict] = []
    for instance_row in selected:
        instance_id = str(instance_row["instance_id"])
        analytics = instance_analytics(instance_id, config)
        for budget in budgets:
            bd = analytics["analytic_by_budget"][str(budget)]
            mse_raw = float(bd["Raw"]["MSE_expected"])
            mse_pec = float(bd["PEC"]["MSE_expected"])
            gri_raw = float(bd["Raw"]["GRI"])
            gri_pec = float(bd["PEC"]["GRI"])
            mse_better = mse_pec < mse_raw
            decision_worse = gri_pec > gri_raw
            coexist = bool(mse_better and decision_worse)
            rows.append(
                {
                    "instance_id": instance_id,
                    "budget": int(budget),
                    "mse_raw": mse_raw,
                    "mse_pec": mse_pec,
                    "gri_raw": gri_raw,
                    "gri_pec": gri_pec,
                    "mse_better": bool(mse_better),
                    "decision_worse": bool(decision_worse),
                    "coexist": coexist,
                }
            )
    return rows


def summarize(rows: list[dict]) -> dict[int, dict]:
    summary: dict[int, dict] = {}
    budgets = sorted({int(row["budget"]) for row in rows})
    for budget in budgets:
        budget_rows = [row for row in rows if int(row["budget"]) == budget]
        summary[budget] = {
            "mse_better": sum(bool(row["mse_better"]) for row in budget_rows),
            "decision_worse": sum(bool(row["decision_worse"]) for row in budget_rows),
            "coexist": sum(bool(row["coexist"]) for row in budget_rows),
            "without": {str(row["instance_id"]) for row in budget_rows if not bool(row["coexist"])},
        }
    return summary


def self_check(summary: dict[int, dict]) -> None:
    for budget, expected in EXPECTED_COUNTS.items():
        if budget not in summary:
            raise AssertionError(f"missing budget {budget}")
        actual = summary[budget]
        for key in ("mse_better", "decision_worse", "coexist"):
            if int(actual[key]) != int(expected[key]):
                raise AssertionError(
                    f"{budget} {key} diverged: actual={actual[key]} expected={expected[key]}"
                )
        if set(actual["without"]) != set(expected["without"]):
            raise AssertionError(
                f"{budget} without diverged: actual={sorted(actual['without'])} "
                f"expected={sorted(expected['without'])}"
            )


def write_csv(rows: list[dict]) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "instance_id",
        "budget",
        "mse_raw",
        "mse_pec",
        "gri_raw",
        "gri_pec",
        "mse_better",
        "decision_worse",
        "coexist",
    ]
    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    rows = build_rows()
    summary = summarize(rows)
    self_check(summary)
    write_csv(rows)
    print("PROOF COEXISTENCE TABLE PASS")
    for budget in sorted(summary):
        item = summary[budget]
        without = ", ".join(sorted(item["without"])) if item["without"] else "none"
        print(
            f"budget={budget} "
            f"MSE<Raw={item['mse_better']}/8 "
            f"GRI>Raw={item['decision_worse']}/8 "
            f"COEXIST={item['coexist']}/8 "
            f"without={without}"
        )
    print(f"wrote={CSV_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
