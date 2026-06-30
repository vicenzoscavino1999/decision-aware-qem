"""Budget ledger and cost accounting.

TODO: A2
"""

from __future__ import annotations

COMPONENT_COLUMNS = [
    "C_train",
    "C_select",
    "C_eval",
    "C_calib",
    "C_noiselearn",
    "C_Sigmahat",
    "C_overhead",
]

LEDGER_COLUMNS = [
    "method",
    "selector",
    "task",
    "B_nominal",
    *COMPONENT_COLUMNS,
    "C_total",
    "amortization_flag",
]

VALID_AMORTIZATION_FLAGS = {"non_amortized", "amortized"}


def total_cost(row) -> float:
    """Sum the seven PAP cost components."""

    return float(sum(float(row[col]) for col in COMPONENT_COLUMNS))


def amortized_cost(row) -> float:
    """Return the amortized cost C_eval + C_overhead."""

    return float(row["C_eval"]) + float(row["C_overhead"])


def validate_ledger(df) -> list[str]:
    """Return validation errors for a budget ledger DataFrame."""

    errors: list[str] = []
    missing = [col for col in LEDGER_COLUMNS if col not in df.columns]
    if missing:
        errors.append(f"missing columns: {missing}")
        return errors

    for idx, row in df.iterrows():
        expected = total_cost(row)
        observed = float(row["C_total"])
        if abs(observed - expected) > 1e-9:
            errors.append(
                f"row {idx}: C_total={observed} != component sum={expected}"
            )
        if row["amortization_flag"] not in VALID_AMORTIZATION_FLAGS:
            errors.append(f"row {idx}: invalid amortization_flag={row['amortization_flag']}")
    return errors
