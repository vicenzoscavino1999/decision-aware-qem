import pandas as pd

from daqem.budget import amortized_cost, total_cost, validate_ledger


def _row(**overrides):
    data = {
        "method": "Raw",
        "selector": "MSE",
        "task": "static",
        "B_nominal": 256,
        "C_train": 1.0,
        "C_select": 2.0,
        "C_eval": 3.0,
        "C_calib": 4.0,
        "C_noiselearn": 5.0,
        "C_Sigmahat": 6.0,
        "C_overhead": 7.0,
        "C_total": 28.0,
        "amortization_flag": "non_amortized",
    }
    data.update(overrides)
    return data


def test_total_and_amortized_cost():
    row = _row()
    assert total_cost(row) == 28.0
    assert amortized_cost(row) == 10.0


def test_validate_ledger_accepts_clean_row():
    df = pd.DataFrame([_row()])
    assert validate_ledger(df) == []


def test_validate_ledger_detects_bad_total_and_flag():
    df = pd.DataFrame([_row(C_total=27.0, amortization_flag="bad")])
    errors = validate_ledger(df)
    assert any("C_total" in err for err in errors)
    assert any("amortization_flag" in err for err in errors)
