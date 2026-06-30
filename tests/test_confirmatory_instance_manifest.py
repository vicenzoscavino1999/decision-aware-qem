from pathlib import Path

import numpy as np
import pandas as pd

from daqem.candidates import (
    build_candidate_landscape,
    build_candidate_landscape_for_graph,
    pilot_maxcut_graph,
)
from experiments import confirmatory_instance_manifest as cim


def test_smoke_manifest_is_deterministic():
    ids = ("C001", "C002", "C003")
    left, left_bounds = cim.build_manifest(ids)
    right, right_bounds = cim.build_manifest(ids)

    pd.testing.assert_frame_equal(left, right)
    assert left_bounds == right_bounds


def test_confirmatory_firewall_disjoint_from_pilot():
    cim.verify_firewall_disjointness(cim.CONFIRMATORY_INSTANCE_IDS)

    assert set(cim.CONFIRMATORY_INSTANCE_IDS).isdisjoint(cim.PILOT_INSTANCE_IDS)


def test_e2_subset_e1_and_count_gates():
    cim.verify_design_counts()

    assert set(cim.CONFIRMATORY_E2_INSTANCE_IDS).issubset(cim.CONFIRMATORY_INSTANCE_IDS)
    assert len(cim.CONFIRMATORY_INSTANCE_IDS) * cim.E1_REPLICATES == 1920
    assert len(cim.CONFIRMATORY_E2_INSTANCE_IDS) * cim.E2_TRAJECTORIES == 1280
    assert 1920 >= cim.STATIC_MIN_PAIRED_DECISIONS
    assert 1280 >= cim.DYNAMIC_MIN_PAIRED_TRAJECTORIES


def test_candidate_landscape_core_matches_pilot_wrapper():
    graph = pilot_maxcut_graph("P001")
    wrapped = build_candidate_landscape(
        "P001",
        candidate_count=6,
        depth=2,
        num_qubits=10,
        graph_degree=3,
        local_radius=0.16,
        search_radius=0.55,
        search_count=64,
    )
    core = build_candidate_landscape_for_graph(
        "P001",
        graph,
        candidate_count=6,
        depth=2,
        local_radius=0.16,
        search_radius=0.55,
        search_count=64,
    )

    assert wrapped.instance_id == core.instance_id
    assert wrapped.graph_seed == core.graph_seed
    assert wrapped.depth == core.depth
    assert wrapped.x_star == core.x_star
    assert wrapped.graph_edges == core.graph_edges
    np.testing.assert_allclose(wrapped.angles, core.angles)
    np.testing.assert_allclose(wrapped.ideal_values, core.ideal_values)


def test_epsilon_positive_finite_for_smoke_manifest():
    manifest, bounds = cim.build_manifest(("C001", "C002", "C003"))

    epsilon = manifest["epsilon_opt_ideal"].to_numpy(dtype=float)
    assert np.all(np.isfinite(epsilon))
    assert np.all(epsilon > 0.0)
    assert bounds["hard_medium"] <= bounds["medium_easy"]


def test_cli_smoke_writes_expected_columns(tmp_path):
    output = Path(tmp_path) / "confirmatory_instance_manifest.csv"

    assert cim.main(["--smoke", "--output", str(output)]) == 0
    manifest = pd.read_csv(output)

    assert list(manifest.columns) == [
        "instance_id",
        "graph_family",
        "depth",
        "n_qubits",
        "degree",
        "graph_seed",
        "epsilon_opt_ideal",
        "difficulty_tercile",
        "in_E1",
        "in_E2",
        "in_E3",
    ]
    assert manifest["instance_id"].tolist() == list(cim.SMOKE_IDS)
    assert manifest["in_E1"].all()
    assert manifest["in_E2"].all()
    assert manifest["in_E3"].all()
