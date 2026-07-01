# Hardware-Sigma micro-cell v1.1 amendment

> Preparacion para revision y sello. Esta enmienda no ejecuta hardware y no modifica el
> pre-registro v1 sellado (`sha256:734FC61A916D8AF40BE163E7294717205618884419083547E200F47D690AA7FC`),
> el freeze publicado, `src/daqem/*`, ni los intentos ya archivados. La corrida del intento 2
> queda prohibida hasta registrar hash + commit de esta enmienda.

## 1. Motivo de la enmienda

El intento 1 siguio el documento v1 y se detuvo correctamente antes del endpoint:

```yaml
attempt_1:
  preregistration_anchor: HARDWARE_SIGMA_MICROCELL_v1.md
  preregistration_sha256: 734FC61A916D8AF40BE163E7294717205618884419083547E200F47D690AA7FC
  output_dir: results/hardware_sigma/
  characterization_job_id: d92pbgfd07jc73dvkveg
  status: stopped_gate_c1
  gate_c1:
    heldout_relative_generalization_error: 0.7441568357299029
    support_f1_stability: 1.0
    passed: false
    thresholds: {gen_error_max: 0.20, support_f1_min: 0.90}
  learned_rates:
    q14: 0.0006788184321887547
    q15: 0.0028319503914518433
    q19: 0.0022753734920692575
    q35: 0.0005376657366110392
    edge_14_15: 0.01546277856288189
    edge_15_19: 0.0054970732951079015
    edge_19_35: 0.4892552555259717
  learned_intercepts:
    q14: 0.010755738543528522
    q15: 0.0705934961452033
    q19: 0.007120509102307604
    q35: 0.03949671105524577
    edge_14_15: 0.08264978131859158
    edge_15_19: 0.12129636693194334
    edge_19_35: 1.317202103276285
  diagnosis: >
    The physical edge (19,35) is effectively broken at runtime relative to the
    2026-06-30 snapshot used by v1. The sparse-PL characterization found a very
    large rate and intercept on that edge, causing Gate C1 to fail.
  stop_correctness:
    endpoint_computed: false
    Sigma_hat_estimated: false
    forbidden_outputs: []
  quantum_time_consumed_minutes: 3.6666666666666643
```

This is a characterization failure, not a covariance endpoint result. It used no
decision, GRI, selector, or `Sigma_hat` information for reselection.

## 2. Blind reselection rule for attempt 2

The attempt-2 mapping is selected by re-running the same calibration-only rule from v1
on a fresh `ibm_marrakesh` snapshot:

```yaml
reselection_rule:
  backend: ibm_marrakesh
  inputs_allowed:
    - fresh_calibration_snapshot
    - readout_error
    - two_qubit_gate_error
    - connectivity
  excluded_inputs:
    - decision_failure
    - selector_choice
    - GRI
    - MSE
    - Sigma_hat
    - agreement_with_Sigma_pred
  path_score: mean_readout_error_plus_mean_two_qubit_error_over_connected_4q_paths
  exclusion:
    edge: [19, 35]
    rule: exclude_any_path_containing_this_edge_in_either_direction
    reason: Gate_C1_characterization_failure_on_attempt_1_edge_not_endpoint_or_decision_data
  tie_break: lexicographic_physical_qubit_tuple
```

The full ranking audit is archived as:

```yaml
mapping_audit:
  file: experiments/hardware_sigma/hardware_sigma_v1_1_mapping_audit.json
  sha256: 46841854FA1FD42C8D33157EB8654B7FA5FAA7E8BB61AA9DE0108AA015A8F099
  ranked_paths_after_exclusion: 606
```

Fresh snapshot and selected mapping:

```yaml
attempt_2_mapping:
  backend_frozen: ibm_marrakesh
  calibration_snapshot_id: "2026-07-01 17:10:59-05:00"
  num_qubits: 156
  coupling_edge_count: 176
  physical_qubits: [13, 14, 15, 19]
  calibration_score: 0.006276329977783074
  mean_readout_error: 0.0048828125
  mean_two_qubit_error: 0.0013935174777830739
  readout_errors: [0.0057373046875, 0.0048828125, 0.005126953125, 0.0037841796875]
  edge_errors:
    edge_13_14: 0.0015987345562298028
    edge_14_15: 0.001381312678499197
    edge_15_19: 0.001200505198620222
  excluded_edge_present: false
  reference_transpilation:
    optimization_level: 1
    seed_transpiler: 260616
    depth: 12
    size: 39
    swap_count: 0
    operation_counts: {rz: 20, sx: 12, cz: 3, measure: 4, barrier: 1}
  execution_transpilation_note: >
    The reference depth/swap count above uses the v1 blind mapping rule
    (optimization_level=1). Actual folded and characterization circuits remain executed
    with optimization_level=0 anti-cancellation ISA transpilation, as implemented in A.3.
```

The previous feasibility record already contains the backend basis/coupling edges needed for
the new path: `(13,14)`, `(14,15)`, and `(15,19)` are present. No target/basis update is needed.

## 3. Runtime budget and R rule

The arm-level cap remains 50 minutes. Attempt 1 consumed 3.6666666666666643 minutes before
the Gate C1 stop. Attempt 2 reserves the same projected characterization cost before allocating
epochs:

```yaml
runtime_budget_attempt_2:
  total_arm_cap_minutes: 50
  consumed_minutes_initial: 3.6666666666666643
  projected_attempt2_characterization_minutes: 3.6666666666666643
  projected_time_per_interleaved_repetition_minutes: 0.64
  R_rule: "min(200, floor((50 - 3.6666666666666643 - 3.6666666666666643) / 0.64)), rounded down to a multiple of 10"
  R_final: 60
  epochs: 10
  repetitions_per_epoch: 6
  output_dir: results/hardware_sigma_attempt2/
```

The runner initializes the budget guard with `consumed_minutes=3.6666666666666643` for the
attempt-2 run. If Runtime usage is unavailable between jobs, the fallback remains 0.64 minutes
per interleaved repetition.

## 4. Two-strikes rule

```yaml
two_strikes_commitment:
  if_attempt2_gate_C1_fails: stop_definitive_no_third_attempt
  report_required: both_attempts_honestly_with_job_ids_and_gate_C1_metrics
  exceptions_allowed: false
```

No third mapping, backend, metric, tolerance, or cell is permitted after an attempt-2 Gate C1
failure.

## 5. Unchanged design elements

Everything not explicitly amended above remains identical to v1:

```yaml
unchanged_from_v1:
  microcell: HSMC001
  problem: 4q_path_MaxCut_QAOA_depth1
  method_menu: [Raw, Accuracy-ZNE, DA-ZNE]
  B_nominal: 4096
  zne_scales_nominal: [1.0, 2.0, 3.0]
  endpoint_primary: projected_ranking_error
  rho_C: 0.25
  endpoint_secondary: relative_Frobenius_error_le_0.20
  bootstrap: cluster_bootstrap_by_epoch
  language_rule: PAP_section_15_3
  hardware_status: stress_test_not_gate_for_E1_E2_E3
  stop_if_gate_C1_fails: true
```

## 6. Pre-run lock checklist

```yaml
pre_run_lock_checklist_v1_1:
  v1_sha256: 734FC61A916D8AF40BE163E7294717205618884419083547E200F47D690AA7FC
  attempt1_output_archived: results/hardware_sigma/
  attempt1_job_id: d92pbgfd07jc73dvkveg
  attempt2_backend: ibm_marrakesh
  attempt2_snapshot: "2026-07-01 17:10:59-05:00"
  attempt2_physical_qubits: [13, 14, 15, 19]
  attempt2_R_final: 60
  attempt2_epochs_reps: "10 x 6"
  attempt2_output_dir: results/hardware_sigma_attempt2/
  execution_allowed_only_after_hash_and_commit: true
```
