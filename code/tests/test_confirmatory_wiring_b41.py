from pathlib import Path

import numpy as np
import pandas as pd

from daqem.candidates import (
    build_candidate_landscape,
    landscape_for_instance,
    maxcut_graph_for_instance,
    pilot_maxcut_graph,
)
from experiments import confirmatory_instance_manifest as cim


def _edges(graph):
    return tuple(sorted((int(i), int(j)) for i, j in graph.edges()))


def test_maxcut_graph_helper_matches_pilot_wrapper_and_accepts_confirmatory():
    pilot = pilot_maxcut_graph("P001")
    via_helper = maxcut_graph_for_instance("P001")
    confirmatory = maxcut_graph_for_instance("C001")

    assert _edges(via_helper) == _edges(pilot)
    assert confirmatory.number_of_nodes() == 10
    assert all(degree == 3 for _, degree in confirmatory.degree())


def test_landscape_helper_matches_pilot_wrapper_byte_identical():
    kwargs = {
        "candidate_count": 6,
        "depth": 2,
        "num_qubits": 10,
        "graph_degree": 3,
        "local_radius": 0.16,
        "search_radius": 0.55,
        "search_count": 64,
    }
    wrapped = build_candidate_landscape("P001", **kwargs)
    helper = landscape_for_instance("P001", **kwargs)

    assert wrapped.instance_id == helper.instance_id
    assert wrapped.graph_seed == helper.graph_seed
    assert wrapped.depth == helper.depth
    assert wrapped.x_star == helper.x_star
    assert wrapped.graph_edges == helper.graph_edges
    assert np.array_equal(wrapped.angles, helper.angles)
    assert np.array_equal(wrapped.ideal_values, helper.ideal_values)


def test_full_manifest_regeneration_matches_frozen_bytes_and_hash():
    frozen_path = Path(__file__).resolve().parents[1] / "results/frozen/confirmatory_instance_manifest.csv"
    regenerated, _ = cim.build_manifest()
    frozen = pd.read_csv(frozen_path)

    exact_columns = [
        "instance_id",
        "graph_family",
        "depth",
        "n_qubits",
        "degree",
        "graph_seed",
        "difficulty_tercile",
        "in_E1",
        "in_E2",
        "in_E3",
    ]
    # Byte identity is relaxed for cross-platform ULP differences in BLAS-backed
    # floating point work; decisions stay exact and the float is checked tightly.
    pd.testing.assert_frame_equal(
        regenerated[exact_columns].reset_index(drop=True),
        frozen[exact_columns].reset_index(drop=True),
        check_dtype=False,
    )
    assert np.allclose(
        regenerated["epsilon_opt_ideal"].to_numpy(),
        frozen["epsilon_opt_ideal"].to_numpy(),
        atol=1e-9,
        rtol=0.0,
    )
