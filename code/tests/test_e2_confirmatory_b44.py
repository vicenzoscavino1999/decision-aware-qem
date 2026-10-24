from pathlib import Path

import numpy as np
import pandas as pd

from experiments import e2_dynamic_batch_candidate_optimizer as e2


def _write_confirmatory_selector_table(root: Path) -> None:
    path = root / e2.CONFIRMATORY_SELECTOR_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "cell": "C001",
                "budget": 512,
                "MSE_selected_method": "Accuracy-ZNE",
                "DA_selected_method": "Raw",
            }
        ]
    ).to_csv(path, index=False)


def _write_a3_coefficients(root: Path, instance_id: str) -> None:
    path = root / "confirmatory" / "a3_frozen_prediction" / f"{instance_id}.npz"
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        method_names=np.asarray(["Raw", "Accuracy-ZNE", "Decision-ZNE"]),
        method_coefficients=np.asarray(
            [
                [1.0, 0.0, 0.0],
                [1.3333333333333333, 0.3333333333333333, -0.6666666666666666],
                [1.2, 0.4, -0.6],
            ],
            dtype=float,
        ),
    )


def test_confirmatory_static_selector_map_reads_e1_table(tmp_path):
    _write_confirmatory_selector_table(tmp_path)

    mapping = e2._static_selector_map(tmp_path, "C001", [512, 1024])

    assert mapping[512] == {"MSE": "Accuracy-ZNE", "DA": "Raw", "source_budget": "512"}
    assert mapping[1024] == {"MSE": "Accuracy-ZNE", "DA": "Raw", "source_budget": "512"}


def test_pilot_static_selector_map_still_uses_power_table(tmp_path, monkeypatch):
    observed = {}

    def fake_build_power_table(output_root):
        observed["output_root"] = output_root
        return pd.DataFrame(
            [
                {
                    "cell": "P001",
                    "budget": 256,
                    "MSE_selected_method": "Decision-ZNE",
                    "DA_selected_method": "Raw",
                }
            ]
        )

    monkeypatch.setattr(e2, "build_power_table", fake_build_power_table)

    mapping = e2._static_selector_map(tmp_path, "P001", [256])

    assert observed["output_root"] == tmp_path
    assert mapping[256] == {"MSE": "Decision-ZNE", "DA": "Raw", "source_budget": "256"}


def test_method_coefficients_dispatches_to_confirmatory_a3(tmp_path):
    _write_a3_coefficients(tmp_path, "C001")

    coeffs = e2._method_coefficients(
        tmp_path,
        "C001",
        ["Raw", "Accuracy-ZNE", "Decision-ZNE"],
    )

    np.testing.assert_allclose(coeffs["Raw"], [1.0, 0.0, 0.0])
    assert e2._a3_frozen_prediction_path(tmp_path, "C001") == (
        tmp_path / "confirmatory" / "a3_frozen_prediction" / "C001.npz"
    )
    assert e2._a3_frozen_prediction_path(tmp_path, "P001") == (
        tmp_path / "pilot" / "a3_frozen_prediction" / "P001.npz"
    )


def test_confirmatory_profiles_are_scoped_to_confirmatory_outputs():
    smoke = e2.load_config("confirmatory_dyn_smoke")
    full = e2.load_config("full")

    assert smoke["instance_ids"] == ["C001"]
    assert smoke["output_namespace"] == "confirmatory"
    assert smoke["budget_grid"] == [512]
    assert full["instance_ids"][0] == "C001"
    assert full["instance_ids"][-1] == "C032"
    assert int(full["trajectories"]) == 40
    assert float(full["candidate_radius"]) == 0.24
    assert float(full["epsilon_quantile"]) == 0.01
    assert bool(full["checkpoint_by_instance"])
    assert e2.report_rel("full") == Path("confirmatory/e2_dynamic_full.md")
    assert e2._dynamic_instance_paths(Path("results"), "full", "C001")["results"] == (
        Path("results") / "confirmatory" / "full" / "instances" / "C001_results.csv"
    )
