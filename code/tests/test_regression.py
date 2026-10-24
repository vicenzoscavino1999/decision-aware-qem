from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal


REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = REPO_ROOT / "reproducibility" / "reference"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures"


def _assert_csv_equal(left: Path, right: Path) -> None:
    if not left.exists() or not right.exists():
        pytest.skip(f"reference fixture not generated: {left} / {right}")
    assert_frame_equal(pd.read_csv(left), pd.read_csv(right), check_dtype=False)


def test_mini_gate0_reference_matches_canonical_reference():
    _assert_csv_equal(
        FIXTURE_ROOT / "mini_gate0_reference.csv",
        REFERENCE_ROOT / "level1" / "gate0_mini.csv",
    )


def test_mini_a3_reference_matches_canonical_reference():
    _assert_csv_equal(
        FIXTURE_ROOT / "mini_a3_reference.csv",
        REFERENCE_ROOT / "pilot" / "pullback_frontier.csv",
    )


def test_mini_selector_reference_matches_gate0_selector_columns():
    selector_path = FIXTURE_ROOT / "mini_selector_reference.csv"
    gate_path = REFERENCE_ROOT / "level1" / "gate0_mini.csv"
    if not selector_path.exists() or not gate_path.exists():
        pytest.skip("selector reference fixture not generated")
    selector = pd.read_csv(selector_path)
    gate = pd.read_csv(gate_path)[
        ["problem_cell", "method", "budget", "selector_full", "selector_diagonal"]
    ]
    assert_frame_equal(selector, gate, check_dtype=False)
