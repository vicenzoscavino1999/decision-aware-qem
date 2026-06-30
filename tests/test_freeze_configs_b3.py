from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from daqem.gap_kernel import contrast_matrix


ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_contrast_matrix_artifact_matches_gap_kernel_and_a3_dimensions():
    artifact = np.load(ROOT / "results" / "frozen" / "contrast_matrices.npz", allow_pickle=False)
    L = np.asarray(artifact["L"], dtype=float)

    assert int(artifact["n"]) == 25
    assert int(artifact["ref"]) == 0
    assert L.shape == (24, 25)
    np.testing.assert_allclose(L, contrast_matrix(25, ref=0))

    a3 = np.load(
        ROOT / "results" / "pilot" / "a3_frozen_prediction" / "P001.npz",
        allow_pickle=False,
    )
    sigma_pred = np.asarray(a3["sigma_pred"], dtype=float)
    gap_maps = np.asarray(a3["gap_maps"], dtype=float)
    assert L.shape[0] == 24 == sigma_pred.shape[-1] == sigma_pred.shape[-2]
    assert L.shape[0] == gap_maps.shape[1]


def test_critical_bands_artifact_transcribes_in_band_rows_and_metadata():
    df = pd.read_csv(ROOT / "results" / "frozen" / "critical_bands.csv")

    assert set(df["in_band"].astype(str).str.lower()) == {"true"}
    assert sorted(df["cell"].unique().tolist()) == ["P001", "P002", "P004"]
    assert len(df) == 13
    assert set(df["critical_band_low"].unique()) == {0.15}
    assert set(df["critical_band_high"].unique()) == {0.70}
    assert set(df["B_star_operational"].unique()) == {512}
    assert {
        ("P001", 256),
        ("P001", 512),
        ("P001", 1024),
        ("P001", 2048),
        ("P001", 4096),
        ("P002", 256),
        ("P002", 512),
        ("P004", 256),
        ("P004", 512),
        ("P004", 1024),
        ("P004", 2048),
        ("P004", 4096),
        ("P004", 8192),
    } == set(zip(df["cell"], df["budget"], strict=True))


def test_pullback_prediction_spec_fields_match_a3_config():
    spec = _load_yaml(ROOT / "reproducibility" / "config" / "pullback_prediction_spec.yaml")
    a3_config = _load_yaml(ROOT / "reproducibility" / "config" / "a3_pullback_frontier.yaml")
    defaults = a3_config["defaults"]

    assert spec["formula"]["composed_form"] == "Sigma_m = (L M_m) C_dev (L M_m)^T"
    assert spec["channel"]["parameter_count"] == 75
    assert spec["expected_shapes"]["gap_maps"] == [3, 24, 75]
    assert spec["expected_shapes"]["sigma_pred"] == [3, 6, 24, 24]
    assert spec["projected_flip_gate"]["rho_flip"] == defaults["rho_flip"] == 0.50
    assert spec["projected_flip_gate"]["mde_absolute"] == defaults["mde_absolute"] == 0.005
    assert spec["gradient"]["perturbation_relative"] == defaults["perturbation_relative"]
    assert spec["gradient"]["min_active_gaps"] == defaults["min_active_gaps"]
    assert spec["gradient"]["max_active_gaps"] == defaults["max_active_gaps"]
    assert spec["sources"]["materialized_prediction_npz"] == (
        "results/pilot/a3_frozen_prediction/*.npz"
    )
