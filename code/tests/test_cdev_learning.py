import numpy as np

from daqem.cdev import (
    PauliLindbladGenerator,
    characterization_circuit,
    fit_depolarizing_rate,
    sparse_pl_basis,
    support_f1_score,
    weighted_relative_l1_error,
)
from experiments.cdev_learned_arm import build_generator_basis, load_config


def test_sparse_pl_basis_uses_one_qubit_and_graph_edge_generators():
    generators = sparse_pl_basis(num_qubits=3, graph_edges=[(0, 1), (1, 2)])

    assert [gen.name for gen in generators] == [
        "1q:0",
        "1q:1",
        "1q:2",
        "2q:0-1",
        "2q:1-2",
    ]
    assert [gen.kind for gen in generators].count("one_qubit") == 3
    assert [gen.kind for gen in generators].count("two_qubit") == 2


def test_characterization_circuit_preserves_depth_with_barriers():
    generator = PauliLindbladGenerator(name="1q:0", kind="one_qubit", qubits=(0,))
    circuit = characterization_circuit(generator, depth=4)

    assert circuit.count_ops()["x"] == 4
    assert circuit.count_ops()["barrier"] == 4


def test_fit_depolarizing_rate_recovers_power_decay():
    depths = np.array([1, 2, 4, 8], dtype=float)
    p = 0.03
    expectations = (1.0 - p) ** depths

    assert abs(fit_depolarizing_rate(depths, expectations) - p) < 1e-12


def test_support_f1_and_weighted_relative_error():
    true = np.array([0.01, 0.03, 0.0])
    learned = np.array([0.011, 0.028, 0.0])
    weights = np.array([0.2, 0.7, 0.1])

    precision, recall, f1 = support_f1_score(true, learned, threshold=1e-4)
    assert precision == 1.0
    assert recall == 1.0
    assert f1 == 1.0
    assert weighted_relative_l1_error(learned, true, weights, eps0=1e-12) < 0.08


def test_smoke_config_builds_p001_sparse_basis():
    config = load_config("smoke")
    generators = build_generator_basis(config)

    assert config["instance_ids"] == ["P001"]
    assert len(generators) == 25
    assert generators[0].kind == "one_qubit"
