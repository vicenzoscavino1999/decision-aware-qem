from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "reproducibility" / "config"


def _load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_b1_selector_config_matches_gate0_source():
    selectors = _load_yaml(CONFIG / "selectors.yaml")
    gate0 = _load_yaml(CONFIG / "gate0_pilot.yaml")

    assert selectors["method_menu_core"] == gate0["defaults"]["method_menu_core"]
    assert selectors["da_selector_rule"]["criterion_when_gri_valid"] == "argmin_gri_by_method"
    assert selectors["da_selector_rule"]["fallback_when_gri_invalid"]["criterion"] == (
        "argmin_empirical_risk_by_method"
    )
    assert selectors["mse_selector_rule"]["criterion"] == "argmin_mse_by_method"
    assert selectors["shared"]["argmin_tie_breaking_implemented"] == "lexicographic_by_method_name"


def test_b1_decision_aware_qem_config_matches_gate0_source():
    qem = _load_yaml(CONFIG / "decision_aware_qem.yaml")
    gate0 = _load_yaml(CONFIG / "gate0_pilot.yaml")

    assert qem["method_menu_core"] == gate0["defaults"]["method_menu_core"]
    assert qem["zne_lambdas"] == gate0["defaults"]["zne_lambdas"]
    assert qem["zne_order"] == gate0["defaults"]["zne_order"]
    assert qem["methods"]["Decision-ZNE"]["decision_zne_mu_floor"] == gate0["defaults"][
        "decision_zne_mu_floor"
    ]
    assert len(qem["methods"]["Accuracy-ZNE"]["active_scales"]) == len(
        gate0["defaults"]["zne_lambdas"]
    )
    assert len(qem["methods"]["Decision-ZNE"]["active_scales"]) == len(
        gate0["defaults"]["zne_lambdas"]
    )


def test_b1_budget_allocation_matches_confirmatory_design_and_qem():
    allocation = _load_yaml(CONFIG / "budget_allocation.yaml")
    design = _load_yaml(CONFIG / "confirmatory_design.yaml")
    qem = _load_yaml(CONFIG / "decision_aware_qem.yaml")

    assert allocation["budget_grid"] == design["budgets"]
    assert allocation["B_star_operational"] == design["regime"]["B_star_operational"]
    assert allocation["method_menu_core"] == qem["method_menu_core"]
    assert allocation["active_scales"]["Raw"] == 1
    assert allocation["active_scales"]["Accuracy-ZNE"] == len(qem["zne_lambdas"])
    assert allocation["active_scales"]["Decision-ZNE"] == len(qem["zne_lambdas"])
    assert allocation["confirmatory_counts"]["E1"]["instances"] == design["counts"]["E1"][
        "instances"
    ]
    assert allocation["confirmatory_counts"]["E1"]["replicates_per_instance"] == design["counts"][
        "E1"
    ]["replicates_per_instance"]
    assert allocation["confirmatory_counts"]["E2"]["instances"] == design["counts"]["E2"][
        "instances"
    ]
    assert allocation["confirmatory_counts"]["E2"]["trajectories_per_instance"] == design[
        "counts"
    ]["E2"]["trajectories_per_instance"]
    assert allocation["confirmatory_counts"]["E3"]["same_instances_as"] == design["counts"]["E3"][
        "same_instances_as"
    ]
