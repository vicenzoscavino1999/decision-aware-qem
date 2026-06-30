from pathlib import Path

import pytest

from experiments.e0_executability_audit import build_budget_table, hardware_decision
from reproducibility.verify import VerificationError, _load_yaml, _validate_schema


REPO_ROOT = Path(__file__).resolve().parents[1]


def _config():
    return {
        "benchmark_cell": {"qubits": 10, "depth": 2},
        "budget_grid": [256, 512, 1024, 2048, 4096, 8192],
        "power_mins": {"E1": 1500, "E2": 1200},
        "method_menu_core": ["Raw", "Accuracy-ZNE", "Decision-ZNE"],
        "candidate_count": 25,
        "dynamic_candidates_per_round": 5,
        "dynamic_rounds": 20,
        "e3_sigma_hat_replicates": 200,
        "max_wall_hours_per_sim_block": 48,
        "batch_size": 50,
        "hardware_schedulable": {
            "sigma_microcell": None,
            "three_budget_ordering": None,
        },
    }


def _cdev_config():
    return {
        "backend": "sim/Aer",
        "characterization_circuits": 200,
        "shots_per_circuit": 4096,
        "epochs": 1,
    }


def _timings(seconds_per_shot: float = 1e-8):
    grid = _config()["budget_grid"]
    return {
        budget: {
            "median_seconds": budget * seconds_per_shot,
            "seconds_per_shot": seconds_per_shot,
        }
        for budget in grid
    }


def _batch_timing(seconds_per_circuit: float = 0.01):
    return {
        "batch_size": 50,
        "budget": 8192,
        "median_total_seconds": 50 * seconds_per_circuit,
        "amortized_seconds_per_circuit": seconds_per_circuit,
        "samples_seconds": [50 * seconds_per_circuit] * 3,
    }


def test_e0_budget_table_schema_rows_decisions_and_deterministic_shots():
    table, summary = build_budget_table(
        _config(), _cdev_config(), _timings(), _batch_timing()
    )
    schema = _load_yaml(REPO_ROOT / "reproducibility" / "config" / "schemas.yaml")
    _validate_schema(table, "executability_budget_table.csv", schema)

    assert len(table) == 7
    assert set(table["decision"]) <= {"go", "no-go", "conditional"}
    assert summary["global_gate"] == "go"
    assert summary["recommended_track"] == "PRXQ"
    decisions = dict(zip(table["block"], table["decision"], strict=True))
    assert all(decisions[block] == "go" for block in ["E1_static", "E2_dynamic", "E3_pullback"])
    assert decisions["Hardware_Sigma_microcell"] in {"go", "conditional"}

    shots = dict(zip(table["block"], table["estimated_shots"], strict=True))
    assert shots["E1_static"] == 921_600_000
    assert shots["E2_dynamic"] == 2_949_120_000
    assert shots["E3_pullback"] == 4_915_200
    assert shots["Sparse_PL_Cdev"] == 819_200
    assert shots["Hardware_Sigma_microcell"] == 7_372_800
    assert shots["Hardware_3budget_ordering"] == 307_200
    assert shots["Scaling_4_6_8"] == 138_240
    walls = dict(zip(table["block"], table["wall_hours"], strict=True))
    assert walls["Scaling_4_6_8"] == pytest.approx(135 * 0.01 / 3600)
    assert walls["Sparse_PL_Cdev"] == pytest.approx(200 * 0.01 / 3600)
    assert walls["Hardware_Sigma_microcell"] == 0.0


def test_e0_gate_recommends_methods_track_when_core_sim_blocks_exceed_ceiling():
    table, summary = build_budget_table(
        _config(), _cdev_config(), _timings(), _batch_timing(seconds_per_circuit=2.0)
    )
    decisions = dict(zip(table["block"], table["decision"], strict=True))
    assert decisions["E1_static"] == "no-go"
    assert decisions["E2_dynamic"] == "no-go"
    assert summary["global_gate"] == "no-go"
    assert summary["recommended_track"] == "Quantum_or_QEM_methods"


@pytest.mark.parametrize(
    ("ceiling", "seconds_per_circuit"),
    [(48.0, 0.01), (0.0, 0.01), (48.0, 2.0)],
)
def test_all_sim_decisions_follow_wall_clock_ceiling(ceiling, seconds_per_circuit):
    config = _config()
    config["max_wall_hours_per_sim_block"] = ceiling
    table, _ = build_budget_table(
        config,
        _cdev_config(),
        _timings(),
        _batch_timing(seconds_per_circuit=seconds_per_circuit),
    )
    sim_rows = table[table["backend_or_resource"] == "sim/Aer"]
    for row in sim_rows.to_dict(orient="records"):
        expected = "go" if row["wall_hours"] <= ceiling else "no-go"
        assert row["decision"] == expected, row["block"]


def test_global_gate_rejects_unschedulable_hardware_sigma():
    config = _config()
    config["hardware_schedulable"]["sigma_microcell"] = False
    table, summary = build_budget_table(
        config, _cdev_config(), _timings(), _batch_timing()
    )
    decisions = dict(zip(table["block"], table["decision"], strict=True))
    assert all(decisions[block] == "go" for block in ["E1_static", "E2_dynamic", "E3_pullback"])
    assert decisions["Hardware_Sigma_microcell"] == "no-go"
    assert summary["global_gate"] == "no-go"
    assert summary["recommended_track"] == "Quantum_or_QEM_methods"


def test_e0_schema_still_rejects_invalid_warning_only_decision():
    table, _ = build_budget_table(
        _config(), _cdev_config(), _timings(), _batch_timing()
    )
    invalid = table.copy()
    invalid.loc[0, "decision"] = "maybe"
    schema = _load_yaml(REPO_ROOT / "reproducibility" / "config" / "schemas.yaml")
    with pytest.raises(VerificationError, match="disallowed values"):
        _validate_schema(invalid, "executability_budget_table.csv", schema)


@pytest.mark.parametrize("value", [True, "true", "YES", "go", "schedulable"])
def test_hardware_decision_accepts_strict_go_values(value):
    assert hardware_decision(value) == "go"


@pytest.mark.parametrize("value", [False, "false", "NO", "no-go", "unschedulable"])
def test_hardware_decision_accepts_strict_no_go_values(value):
    assert hardware_decision(value) == "no-go"


def test_hardware_decision_none_is_conditional_and_invalid_values_raise():
    assert hardware_decision(None) == "conditional"
    for value in [1, 0, "maybe", [], {}]:
        with pytest.raises(ValueError, match="invalid hardware_schedulable flag"):
            hardware_decision(value)
