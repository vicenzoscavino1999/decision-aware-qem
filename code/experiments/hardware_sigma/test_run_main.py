from __future__ import annotations

import json

import numpy as np

from daqem.gap_kernel import contrast_matrix
from daqem.qem_methods import richardson_constraints

from experiments.hardware_sigma import run_main as hsmc


def test_folding_lambda2_deterministic_and_lambda3_global() -> None:
    base = hsmc.build_candidate_circuits()[0]
    folded_a, scale_a = hsmc.partial_fold_lambda2_from_left(base)
    folded_b, scale_b = hsmc.partial_fold_lambda2_from_left(base)
    assert hsmc.circuit_signature(folded_a) == hsmc.circuit_signature(folded_b)
    base_twoq = hsmc.count_two_qubit_gates(hsmc.remove_measurements(base))
    assert scale_a == scale_b
    assert scale_a == hsmc.count_two_qubit_gates(folded_a) / base_twoq

    global_folded, global_scale = hsmc.global_fold_lambda3(base)
    assert global_scale == 3.0
    assert hsmc.count_two_qubit_gates(global_folded) == 3 * base_twoq


def test_richardson_effective_scale_constraints_and_known_exact_case() -> None:
    coeffs = hsmc.zne_coefficients_from_effective_scales((1.0, 2.0, 3.0))
    np.testing.assert_allclose(coeffs, np.array([4.0 / 3.0, 1.0 / 3.0, -2.0 / 3.0]), atol=1e-12)
    A, rho = richardson_constraints(np.array([1.0, 2.0, 3.0]), 1)
    np.testing.assert_allclose(A @ coeffs, rho, atol=1e-12)

    effective = hsmc.effective_scale_tuple()
    eff_coeffs = hsmc.zne_coefficients_from_effective_scales(effective)
    A_eff, rho_eff = richardson_constraints(np.asarray(effective), 1)
    np.testing.assert_allclose(A_eff @ eff_coeffs, rho_eff, atol=1e-10)


def test_isa_anti_cancellation_assert_passes_and_detects_cancelled_fold() -> None:
    base = hsmc.build_candidate_circuits()[0]
    isa_by_scale = {}
    effective_by_scale = {}
    for scale in hsmc.SCALES_NOMINAL:
        isa, effective = hsmc.isa_for_candidate_scale(base, scale)
        isa_by_scale[float(scale)] = isa
        effective_by_scale[float(scale)] = effective
    ratios = hsmc.assert_folded_isa_anti_cancellation(isa_by_scale, effective_by_scale)
    assert ratios["cz_ratio_lambda2"] == effective_by_scale[2.0]
    assert ratios["cz_ratio_lambda3"] == 3.0

    bad_by_scale = dict(isa_by_scale)
    bad_by_scale[3.0] = isa_by_scale[1.0]
    try:
        hsmc.assert_folded_isa_anti_cancellation(bad_by_scale, effective_by_scale)
    except RuntimeError as exc:
        assert "lambda=3" in str(exc)
    else:
        raise AssertionError("anti-cancellation assert failed to detect a collapsed fold")


def test_isa_mapping_and_clbit_assertion() -> None:
    isa, _ = hsmc.isa_for_candidate_scale(hsmc.build_candidate_circuits()[0], 1.0)
    assert hsmc.measurement_physical_by_clbit(isa) == {0: 14, 1: 15, 2: 19, 3: 35}
    compact = hsmc.compact_isa_circuit(isa)
    assert compact.num_qubits == 4

    bad = hsmc.QuantumCircuit(max(hsmc.PHYSICAL_QUBITS) + 1, 4)
    bad.measure(14, 1)
    bad.measure(15, 0)
    bad.measure(19, 2)
    bad.measure(35, 3)
    try:
        hsmc.assert_isa_mapping(bad)
    except RuntimeError as exc:
        assert "mapping mismatch" in str(exc)
    else:
        raise AssertionError("expected mapping/clbit assertion to fail")


def test_sparse_pl_recovers_known_rates_and_gate_c1_fail_stops(tmp_path) -> None:
    true_rates = np.array([0.004, 0.003, 0.002, 0.005, 0.001, 0.0015, 0.0025])
    tasks, counts = hsmc.synthetic_characterization_counts_test_only(true_rates)
    design = hsmc.characterization_design(tasks)
    observations = hsmc.characterization_observations_from_counts(tasks, counts)
    learned = hsmc.learn_sparse_pl_rates(design, observations)
    np.testing.assert_allclose(learned, true_rates, atol=5e-4)
    metrics = hsmc.gate_c1_metrics(design, observations, learned)
    assert metrics["passed"]

    corrupted = observations.copy()
    _, heldout = hsmc.split_characterization(design)
    corrupted[heldout] += 2.0
    failed_metrics = hsmc.gate_c1_metrics(design, corrupted)
    assert not failed_metrics["passed"]
    unstable = observations.copy()
    unstable[np.arange(unstable.size) % 2 == 0] = 0.0
    unstable_rates = hsmc.learn_sparse_pl_rates(design, unstable)
    unstable_metrics = hsmc.gate_c1_metrics(design, unstable, unstable_rates)
    assert unstable_metrics["support_f1_stability"] < 0.90
    assert not unstable_metrics["passed"]
    config = hsmc.RunConfig(output_dir=tmp_path, epochs=1, reps_per_epoch=2, bootstrap_repetitions=5)
    result = hsmc.run_pipeline(
        config=config,
        sampler=hsmc.DeterministicProbabilitySampler(),
        true_rates=true_rates,
        force_gate_c1_fail=True,
    )
    assert result["status"] == "stopped_gate_c1"


def test_sparse_pl_intercepts_remove_readout_offset_bias() -> None:
    true_rates = np.array([0.004, 0.003, 0.002, 0.005, 0.001, 0.0015, 0.0025])
    offsets = np.array([0.03, 0.02, 0.01, 0.025, 0.04, 0.035, 0.03])
    tasks, counts = hsmc.synthetic_characterization_counts_test_only(true_rates, intercepts=offsets)
    design = hsmc.characterization_design(tasks)
    rate_design = hsmc.characterization_rate_design(tasks)
    observations = hsmc.characterization_observations_from_counts(tasks, counts)
    model = hsmc.learn_sparse_pl_model(design, observations)
    biased = hsmc.learn_sparse_pl_rates_no_intercept_test_only(rate_design, observations)
    np.testing.assert_allclose(model["rates"], true_rates, atol=8e-4)
    assert np.linalg.norm(biased - true_rates) > 3.0 * np.linalg.norm(model["rates"] - true_rates)


def test_sigma_pred_matches_direct_pullback() -> None:
    cdev = np.diag(np.linspace(0.01, 0.12, 12))
    maps = hsmc.method_maps((1.0, 2.0, 3.0))
    L = contrast_matrix(4, ref=0)
    for method, method_map in maps.items():
        expected = L @ method_map @ cdev @ method_map.T @ L.T
        actual = hsmc.sigma_pred(cdev, method_map, L)
        np.testing.assert_allclose(actual, expected, atol=1e-10)


def test_shots_matched_total_and_sigma_normalization_known_channel() -> None:
    tasks = hsmc.build_epoch_tasks(0, reps_per_epoch=1)
    assert len(tasks) == 28
    assert {task.shots for task in tasks if task.method == "Raw"} == {4096}
    assert {task.shots for task in tasks if task.method != "Raw"} == {1365}

    primitive_var = np.linspace(0.02, 0.13, 12)
    effective = (1.0, 2.0, 3.0)
    da = hsmc.decision_zne_coefficients_from_prediction(
        primitive_var,
        np.array([-2.0, -1.8, -1.6, -1.4]),
        effective,
    )
    maps = hsmc.method_maps(effective, da_coeffs=da)
    L = contrast_matrix(4, ref=0)
    raw_sigma = hsmc.sigma_pred_from_primitive_variances(primitive_var, "Raw", maps["Raw"], L)
    manual = L @ maps["Raw"] @ np.diag(primitive_var / hsmc.primitive_shot_vector("Raw")) @ maps["Raw"].T @ L.T
    np.testing.assert_allclose(raw_sigma, manual, atol=1e-12)

    # High-R synthetic Monte Carlo: sample independent primitive estimates from
    # the same diagonal covariance and check the pipeline covariance scale.
    rng = np.random.default_rng(260616)
    draws = rng.normal(scale=np.sqrt(primitive_var / hsmc.primitive_shot_vector("Accuracy-ZNE")), size=(20_000, 12))
    gaps = (L @ maps["Accuracy-ZNE"] @ draws.T).T
    sigma_hat = np.cov(gaps, rowvar=False, ddof=1)
    sigma_pred = hsmc.sigma_pred_from_primitive_variances(primitive_var, "Accuracy-ZNE", maps["Accuracy-ZNE"], L)
    rel = np.linalg.norm(sigma_hat - sigma_pred, ord="fro") / np.linalg.norm(sigma_pred, ord="fro")
    assert rel < 0.08


def test_isa_prediction_units_known_channel_scale() -> None:
    rates = np.array([0.004, 0.003, 0.002, 0.005, 0.001, 0.0015, 0.0025])
    primitive_var = hsmc.primitive_variance_unit_from_rates(rates)
    assert primitive_var.shape == (12,)
    assert np.all(primitive_var >= 0.0)
    effective = hsmc.effective_scale_tuple()
    maps = hsmc.method_maps(effective)
    L = contrast_matrix(4, ref=0)
    sigma = hsmc.sigma_pred_from_primitive_variances(primitive_var, "Accuracy-ZNE", maps["Accuracy-ZNE"], L)
    assert sigma.shape == (3, 3)
    assert np.all(np.isfinite(sigma))


def test_projected_endpoint_pass_fail_and_bootstrap_sanity() -> None:
    mu = np.array([0.5, 0.7, 1.0])
    pred = {
        "Raw": np.eye(3),
        "Accuracy-ZNE": 2.0 * np.eye(3),
        "DA-ZNE": 3.0 * np.eye(3),
    }
    endpoint_pass = hsmc.endpoint_projected_ranking(mu=mu, sigma_pred_by_method=pred, sigma_hat_by_method=pred)
    assert endpoint_pass["primary_pass"]
    bad_hat = {method: 10.0 * sigma for method, sigma in pred.items()}
    endpoint_fail = hsmc.endpoint_projected_ranking(mu=mu, sigma_pred_by_method=pred, sigma_hat_by_method=bad_hat)
    assert not endpoint_fail["primary_pass"]

    rng = np.random.default_rng(123)
    epoch_vectors = []
    for _ in range(4):
        epoch_vectors.append({method: [rng.normal(size=3) for _ in range(3)] for method in hsmc.METHODS})
    boot = hsmc.bootstrap_sigma_by_epoch(epoch_vectors, repetitions=20)
    assert len(boot) == 20
    assert all(np.all(np.isfinite(row["Raw"])) for row in boot)


def test_gri_endpoint_two_sides_and_directionally_sensitive_case() -> None:
    mu = np.array([0.6, 0.9, 1.2])
    pred = {
        "Raw": np.diag([0.03, 0.04, 0.05]),
        "Accuracy-ZNE": np.diag([0.05, 0.06, 0.07]),
        "DA-ZNE": np.diag([0.07, 0.08, 0.09]),
    }
    small = {k: v + 1e-5 * np.eye(3) for k, v in pred.items()}
    assert hsmc.endpoint_projected_ranking(mu=mu, sigma_pred_by_method=pred, sigma_hat_by_method=small)["primary_pass"]
    large = {k: 3.0 * v for k, v in pred.items()}
    assert not hsmc.endpoint_projected_ranking(mu=mu, sigma_pred_by_method=pred, sigma_hat_by_method=large)["primary_pass"]

    gradients = {k: hsmc.gri_sigma_gradient(mu, v) for k, v in pred.items()}
    rows = []
    for a, b in [("Raw", "Accuracy-ZNE"), ("Raw", "DA-ZNE")]:
        diff = gradients[a] - gradients[b]
        rows.append(np.array([diff[0, 0], diff[1, 1], diff[2, 2]], dtype=float))
    _, _, vh = np.linalg.svd(np.vstack(rows))
    null_diag = vh[-1]
    err = np.diag(null_diag / np.linalg.norm(null_diag) * 0.2)
    innocuous = {k: v + err for k, v in pred.items()}
    projected = hsmc.endpoint_projected_ranking(mu=mu, sigma_pred_by_method=pred, sigma_hat_by_method=innocuous)
    frob = hsmc.frobenius_secondary(pred, innocuous)
    assert projected["primary_pass"]
    assert not frob["secondary_pass"]


def test_ordering_gate_end_to_end_hsmc001() -> None:
    result = hsmc.ordering_gate_end_to_end()
    assert result["passed"]
    assert result["abs_error"] <= result["tolerance"]


def test_dry_run_pipeline_complete_writes_result(tmp_path) -> None:
    config = hsmc.RunConfig(output_dir=tmp_path, epochs=2, reps_per_epoch=2, bootstrap_repetitions=20)
    sampler = hsmc.DeterministicProbabilitySampler()
    result = hsmc.run_pipeline(config=config, sampler=sampler, true_rates=np.array([0.004, 0.003, 0.002, 0.005, 0.001, 0.0015, 0.0025]))
    assert result["status"] == "complete"
    assert result["gate_c1"]["passed"]
    assert result["ordering_gate"]["passed"]
    assert (tmp_path / "hsmc_result.json").exists()
    payload = json.loads((tmp_path / "hsmc_result.json").read_text(encoding="utf-8"))
    assert payload["config"]["B_nominal"] == 4096
    assert set(payload["sigma_hat"]) == set(hsmc.METHODS)


def test_checkpoint_resume_does_not_resubmit_completed_epoch(tmp_path) -> None:
    config = hsmc.RunConfig(output_dir=tmp_path, epochs=3, reps_per_epoch=1, bootstrap_repetitions=10)
    first_sampler = hsmc.DeterministicProbabilitySampler()
    true_rates = np.array([0.004, 0.003, 0.002, 0.005, 0.001, 0.0015, 0.0025])
    first = hsmc.run_pipeline(config=config, sampler=first_sampler, stop_after_epoch=0, true_rates=true_rates)
    assert first["status"] == "incomplete_checkpointed"
    assert first_sampler.submitted_batches == 1

    second_sampler = hsmc.DeterministicProbabilitySampler()
    second = hsmc.run_pipeline(config=config, sampler=second_sampler, resume=True, true_rates=true_rates)
    assert second["status"] == "complete"
    assert second_sampler.submitted_batches == 2


def test_output_dir_with_checkpoint_requires_resume(tmp_path) -> None:
    (tmp_path / "checkpoints").mkdir()
    (tmp_path / "checkpoints" / "epoch_00.json").write_text("{}", encoding="utf-8")
    config = hsmc.RunConfig(output_dir=tmp_path, epochs=1, reps_per_epoch=2, bootstrap_repetitions=5)
    try:
        hsmc.run_pipeline(
            config=config,
            sampler=hsmc.DeterministicProbabilitySampler(),
            true_rates=np.array([0.004, 0.003, 0.002, 0.005, 0.001, 0.0015, 0.0025]),
        )
    except RuntimeError as exc:
        assert "already contains data" in str(exc)
    else:
        raise AssertionError("expected output-dir safety error")


def test_budget_guard_stops_before_crossing_cap(tmp_path) -> None:
    config = hsmc.RunConfig(output_dir=tmp_path, epochs=3, reps_per_epoch=1, bootstrap_repetitions=5)
    guard = hsmc.BudgetGuard(consumed_minutes=49.8, per_epoch_minutes=0.3, cap_minutes=50.0)
    sampler = hsmc.DeterministicProbabilitySampler()
    result = hsmc.run_pipeline(
        config=config,
        sampler=sampler,
        budget_guard=guard,
        true_rates=np.array([0.004, 0.003, 0.002, 0.005, 0.001, 0.0015, 0.0025]),
    )
    assert result["status"] == "stopped_budget_guard"
    assert result["completed_epochs"] == []
    assert sampler.submitted_batches == 0


def test_dry_run_json_does_not_contain_token_markers(tmp_path) -> None:
    config = hsmc.RunConfig(output_dir=tmp_path, epochs=1, reps_per_epoch=2, bootstrap_repetitions=5)
    hsmc.run_pipeline(
        config=config,
        sampler=hsmc.DeterministicProbabilitySampler(),
        true_rates=np.array([0.004, 0.003, 0.002, 0.005, 0.001, 0.0015, 0.0025]),
    )
    combined = (tmp_path / "hsmc_result.json").read_text(encoding="utf-8")
    assert "apikey" not in combined.lower()
    assert "qiskit_ibm_token" not in combined.lower()
