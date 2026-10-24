from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "reproducibility" / "config"


def _load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_b2_gri_calibration_matches_a3_gaussianity_source():
    gri = _load_yaml(CONFIG / "gri_calibration.yaml")
    a3 = _load_yaml(CONFIG / "a3_gaussianity.yaml")

    assert gri["calibration"]["tau_R"] == a3["defaults"]["tau_R"] == 0.05
    assert gri["calibration"]["valid_mask_rule"] == "abs_diff_gaussianity <= tau_R"
    assert gri["fallback_when_invalid"]["fallback_metric"] == "empirical_risk_by_method"
    assert gri["fallback_when_invalid"]["condition"] == "gri_valid == false"


def test_b2_inference_matches_gate0_and_power_gate_sources():
    inference = _load_yaml(CONFIG / "inference.yaml")
    gate0 = _load_yaml(CONFIG / "gate0_pilot.yaml")

    assert inference["covariance_estimator"]["use_ledoit_wolf"] is True
    assert inference["covariance_estimator"]["use_ledoit_wolf"] == gate0["defaults"][
        "use_ledoit_wolf"
    ]
    assert inference["static_primary_test"]["alpha_primary"] == 0.05
    assert inference["static_primary_test"]["bootstrap_repetitions"] == 10000
    assert inference["power_gate"]["minimum_detectable_relative_failure_reduction"] == 0.15
    assert inference["power_gate"]["minimum_detectable_shot_savings"] == 0.20
    assert inference["sigmahat_audit"]["bootstrap_CI"] == 0.95


def test_b2_claim_registry_preserves_pap_gatekeeping_order_and_contingency():
    registry = _load_yaml(CONFIG / "claim_registry.yaml")

    assert registry["primary_family"]["alpha_primary"] == 0.05
    assert registry["primary_family"]["gatekeeping_order"] == [
        "Claim 2",
        "Claim 1",
        "Claim 3A",
    ]
    assert "Si Claim 2 falla" in registry["primary_family"]["contingency_rule_2647"]
    assert "soporte, no headline" in registry["primary_family"]["contingency_rule_2647"]
    assert registry["secondary_scans"]["procedure"] == "Romano-Wolf_step-down_or_descriptive"
    assert registry["stratified_reporting"]["role"] == "descriptive"
    assert registry["stratified_reporting"]["alpha_protected"] is False
