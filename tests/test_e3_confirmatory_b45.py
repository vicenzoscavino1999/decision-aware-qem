import numpy as np
import pandas as pd

from experiments import a3_pullback_frontier as a3
from experiments import e3_bstar_prediction as e3


def test_e3_reuses_a3_analyze_function():
    assert e3.analyze_cell_from_frozen_prediction is a3.analyze_cell_from_frozen_prediction
    assert a3._raw_relpath_for_config("C001", {"output_namespace": "confirmatory"}).as_posix() == (
        "confirmatory/raw/C001.npz"
    )
    assert a3._raw_relpath_for_config("P001", {}).as_posix() == "pilot/raw/P001.npz"


def test_directional_summary_counts_active_ordering_matches():
    rows = pd.DataFrame(
        [
            {
                "problem_cell": "C001",
                "active_pair": True,
                "ordering_match": True,
                "pass_label": "directionally_sensitive_pass",
                "a3_status": "pass",
            },
            {
                "problem_cell": "C001",
                "active_pair": True,
                "ordering_match": False,
                "pass_label": "fail",
                "a3_status": "fail",
            },
            {
                "problem_cell": "C001",
                "active_pair": False,
                "ordering_match": True,
                "pass_label": "ambiguous",
                "a3_status": "ambiguous",
            },
        ]
    )

    by_instance, aggregate = e3.directional_summary(rows)

    assert aggregate["active_pairs"] == 2
    assert aggregate["ordering_matches"] == 1
    assert aggregate["directional_match_fraction"] == 0.5
    assert int(by_instance.iloc[0]["directionally_sensitive_pass"]) == 1


def test_e3_wrapper_reads_confirmatory_frozen_and_writes_confirmatory_outputs(
    tmp_path,
    monkeypatch,
):
    frozen = tmp_path / "confirmatory" / "a3_frozen_prediction" / "C001.npz"
    frozen.parent.mkdir(parents=True, exist_ok=True)
    np.savez(frozen, value=np.asarray([1.0]))

    monkeypatch.setattr(
        e3,
        "_profile_config",
        lambda profile: {
            "profile": profile,
            "instance_ids": ["C001"],
            "output_namespace": "confirmatory",
        },
    )

    observed = {}

    def fake_analyze(*, instance_id, frozen_path, frozen_hash, output_root, config):
        observed["instance_id"] = instance_id
        observed["frozen_path"] = frozen_path
        observed["frozen_hash"] = frozen_hash
        observed["output_root"] = output_root
        observed["config"] = dict(config)
        return pd.DataFrame(
            [
                {
                    "problem_cell": "C001",
                    "pair_id": "Raw_vs_Accuracy-ZNE",
                    "budget": 512,
                    "active_pair": True,
                    "delta_rank_projected": 0.1,
                    "tau_flip_projected": 1.0,
                    "projected_error_over_tolerance": 0.1,
                    "frobenius_error_over_tolerance": 2.0,
                    "predicted_order": "Raw<Accuracy-ZNE",
                    "empirical_order": "Raw<Accuracy-ZNE",
                    "ordering_match": True,
                    "a3_status": "pass",
                    "pass_label": "directionally_sensitive_pass",
                    "_frozen_hash": frozen_hash,
                }
            ]
        )

    monkeypatch.setattr(e3, "analyze_cell_from_frozen_prediction", fake_analyze)

    result = e3.run(tmp_path, profile="confirmatory_e3_smoke")

    assert observed["frozen_path"] == frozen
    assert observed["frozen_hash"].startswith("sha256:")
    assert observed["output_root"] == tmp_path
    assert result["rows"] == 1
    assert (tmp_path / e3.E3_CSV_REL).exists()
    assert (tmp_path / e3.E3_REPORT_REL).exists()
    assert not (tmp_path / "pilot" / "pullback_frontier.csv").exists()
