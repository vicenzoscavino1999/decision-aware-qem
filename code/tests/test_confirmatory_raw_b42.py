from pathlib import Path

import numpy as np

from daqem.candidates import landscape_for_instance, maxcut_graph_for_instance
from experiments import gate0_pilot_full_vs_diagonal as gate0


def _edges(graph):
    return tuple(sorted((int(i), int(j)) for i, j in graph.edges()))


def test_confirmatory_raw_relpath_is_separate_from_pilot_raw():
    assert gate0.raw_relpath("P001") == Path("pilot/raw/P001.npz")
    assert gate0.confirmatory_raw_relpath("C001") == Path("confirmatory/raw/C001.npz")

    config = gate0.load_config("confirmatory_smoke")
    assert gate0._raw_relpath_for_config("C001", config) == Path(
        "confirmatory/raw/C001.npz"
    )


def test_confirmatory_graph_and_landscape_use_shared_helpers():
    config = gate0.load_config("confirmatory_smoke")
    graph, landscape = gate0._graph_and_landscape_for_config("C001", config)
    helper_graph = maxcut_graph_for_instance("C001")
    helper_landscape = landscape_for_instance(
        "C001",
        candidate_count=int(config["candidate_count"]),
        depth=int(config["depth"]),
        num_qubits=int(config["qubits"]),
        graph_degree=int(config["graph_degree"]),
        local_radius=float(config["local_radius"]),
        search_radius=float(config["search_radius"]),
        search_count=int(config["search_count"]),
    )

    assert _edges(graph) == _edges(helper_graph)
    assert landscape.graph_seed == helper_landscape.graph_seed
    assert landscape.graph_edges == helper_landscape.graph_edges
    assert np.array_equal(landscape.angles, helper_landscape.angles)
    assert np.array_equal(landscape.ideal_values, helper_landscape.ideal_values)


def test_pilot_profile_still_resolves_pilot_raw_path_and_namespace():
    config = gate0.load_config("smoke")

    assert config["output_namespace"] == "pilot"
    assert gate0._raw_relpath_for_config("P001", config) == Path("pilot/raw/P001.npz")
    assert config["instance_ids"] == ["P001"]
