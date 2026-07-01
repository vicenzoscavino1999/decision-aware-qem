# Pre-registro Hardware-Sigma micro-cell v1

> **Documento de PRE-REGISTRO para revisión y sello.** Este arm de hardware es aditivo y
> constituye un stress test local del pullback de covarianza. No es un gate de E1/E2/E3 y no
> modifica el freeze publicado (`sha256:2AF91BE1...`, 52 archivos), `src/daqem/*`, ni los
> pre-registros FakeBackend sellados (`sha256:6210C6F1...` y `sha256:AA029CA5...`).
>
> **Fecha:** 2026-07-01. **Estado:** diseño no ejecutado, pendiente de confirmar el backend y
> sellar los campos derivados exclusivamente del mini-job de feasibility. **Ejecución de la
> micro-cell:** prohibida hasta completar esos campos y registrar hash + commit.

---

## 0. Ancla en el PAP y alcance

Este diseño implementa la **Hardware-Sigma micro-cell** del
`EXPERIMENTAL_PLAN_v13_PRXQ.md`:

- **PAP §15.1.1:** celda de 3--5 qubits con 2--3 gaps activos; aprendizaje de
  \(C_{\mathrm{dev}}\) antes de estimar \(\widehat\Sigma\); estimación directa mediante
  repeticiones independientes; ejecución interleaved por método/budget; cluster bootstrap por
  epoch; endpoint
  \[
  \Sigma_m^{\mathrm{pred}}
  = L M_m C_{\mathrm{dev}} M_m^\top L^\top
  \quad\text{vs}\quad
  \widehat\Sigma_m^{\mathrm{hardware}}.
  \]
- **PAP §4.4.1 y Gate C1:** la caracterización sparse Pauli--Lindblad se carga al ledger y
  debe alcanzar error de generalización relativo `<= 0.20` y `support F1 >= 0.90` antes de
  habilitar la comparación de covarianza.
- **PAP §15.3:** el lenguaje `device-level` queda condicionado al pase cuantitativo de esta
  micro-cell. Un fallo o resultado inconcluso prohíbe
  `device_level_prediction_of_covariance` y `device_level_prediction_of_shot_cost`, y exige
  democión del título.
- **PAP §15.1 y línea 1145:** hardware es un stress test. Los claims simulados E1/E2/E3 no
  dependen de este resultado y no se reinterpretan a partir de él.

El objetivo es exclusivamente validar, en una micro-cell local y directamente estimable, si el
canal aprendido predice la covarianza de los gaps. No se prueba ventaja de decisión, ordering
across budgets, universalidad, ni acuerdo de constantes fuera de esta celda.

---

## 1. Estado de bloqueo y secuencia de sello

```yaml
preregistration:
  document: HARDWARE_SIGMA_MICROCELL_v1.md
  status: draft_for_review_not_executable
  design_date: 2026-07-01
  must_be_hashed_and_committed_before_hardware_main_run: true
  current_blockers:
    - backend_frozen
    - backend_calibration_snapshot_id
    - physical_qubit_path
    - feasibility_quantum_time_measurement
    - R_final_from_preregistered_time_rule
  forbidden_before_final_seal:
    - hardware_Sigma_main_run
    - estimating_Sigma_hat
    - comparing_Sigma_pred_to_Sigma_hat
    - changing_cell_metric_or_tolerance_after_hardware_data
```

El mini-job de feasibility no estima \(\widehat\Sigma\), no evalúa la métrica primaria y no
autoriza inspección de resultados de decisión. Tras ese mini-job se completan únicamente los
campos de backend, mapping, quantum time y `R_final` definidos por la regla de la §8; se genera
un hash + commit nuevo **antes** de la corrida principal.

---

## 2. Backend real y selección ciega

```yaml
hardware_backend:
  provider: IBM_Quantum
  backend_frozen: ibm_marrakesh
  backend_calibration_snapshot_id: "2026-06-30 11:49:31-05:00"
  required_type: real_hardware_not_fake_backend
  minimum_operational_qubits: 4
  num_qubits: 156
  basis_gates: [cz, delay, id, if_else, measure, reset, rz, sx, x]
  coupling_map_edge_count: 176
  target_and_full_coupling_record: experiments/hardware_sigma/feasibility_result.json
  calibration_record: experiments/hardware_sigma/feasibility_result.json
  selection_inputs_allowed:
    - backend_availability
    - queue_status
    - calibration_snapshot
    - readout_error
    - two_qubit_gate_error
    - connectivity
  forbidden_selection_inputs:
    - decision_failure
    - selector_choice
    - GRI
    - MSE
    - Sigma_hat
    - agreement_with_Sigma_pred
  quantum_time_budget_minutes: [40, 50]
  user_quantum_time_available_minutes: 140
```

El usuario confirma un backend disponible con al menos cuatro qubits operativos. La elección se
hace por disponibilidad y menor error de calibración, ciega a cualquier resultado de decisión o
covarianza. Se archivan el nombre del backend, timestamp/ID del snapshot de calibración, target,
basis gates, coupling map y propiedades usadas en la selección.

### 2.1 Mapping físico ciego

Sobre el backend confirmado se enumeran los caminos conectados de cuatro qubits. Para cada camino
se calcula, solo desde el snapshot de calibración,

\[
s(q_0,q_1,q_2,q_3)
=
\operatorname{mean}_i(e^{\mathrm{readout}}_{q_i})
+
\operatorname{mean}_{(i,j)\in P_4}(e^{2q}_{q_iq_j}).
\]

Se elige el camino con menor `s`; los empates se rompen por la tupla lexicográficamente menor de
qubits físicos. Esta elección no usa ejecuciones de la micro-cell. El mapping, score, errores
componentes, profundidad transpilada y SWAP count se completan y sellan antes de la corrida
principal.

```yaml
physical_mapping:
  rule: minimum_calibration_score_connected_four_qubit_path
  tie_break: lexicographic_physical_qubit_tuple
  physical_qubits: [14, 15, 19, 35]
  calibration_score: 0.005940674965659587
  mean_readout_error: 0.004547119140625
  mean_two_qubit_error: 0.001393555825034587
  readout_errors: [0.0048828125, 0.005126953125, 0.0037841796875, 0.00439453125]
  edge_errors: [0.0013853337077031347, 0.0013179805293715985, 0.0014773532380290277]
  transpilation:
    optimization_level: 1
    seed_transpiler: 260616
    target: confirmed_backend_target
  transpiled_depth: 36
  swap_count: 0
```

---

## 3. Micro-cell ciega

La micro-cell se fija por una regla estructural y no por su comportamiento en hardware:

```yaml
microcell:
  instance_id: HSMC001
  problem: MaxCut
  graph:
    family: path_graph
    n_qubits: 4
    logical_edges: [[0, 1], [1, 2], [2, 3]]
  qaoa_depth: 1
  candidate_construction:
    source: frozen_candidate_landscape_core_read_only
    candidate_count: 4
    local_radius: 0.16
    search_radius: 0.55
    search_count: 64
    seed_derivation: sha256(instance_id)
  active_gaps: 3
  contrast_reference: ideal_noise_free_best_candidate
  contrast_matrix: "L has rows e_i - e_ref for the three competitors"
  hardware_outcome_blind: true
```

Los cuatro candidatos generan exactamente tres coordenadas de gap respecto del mejor candidato
ideal. El candidato de referencia se determina por simulación noise-free antes del hardware y se
sella. Si el paisaje ideal presenta un empate exacto que hace degenerado algún gap, la micro-cell
se declara **inviable** y no se sustituye por otra después de mirar hardware; cualquier rediseño
requiere una versión nueva, justificación y sello previo.

---

## 4. Menú mínimo y presupuesto

```yaml
method_menu:
  - Raw
  - Accuracy-ZNE
  - DA-ZNE
excluded_methods:
  - CDR
  - Raw+REM
  - PEC
  - CDR+REM
scope_reason: minimum_selector_core_for_local_Sigma_validation

evaluation_budget:
  B_nominal: 4096
  Raw:
    scales: [1.0]
  Accuracy_ZNE:
    scales: [1.0, 2.0, 3.0]
    zne_order: 1
  DA_ZNE:
    scales: [1.0, 2.0, 3.0]
    zne_order: 1
  matched_total_shots: true
```

El menú no se amplía tras ver resultados. ZNE reparte el budget nominal entre sus tres escalas;
Raw usa una escala. Los shots de caracterización de \(C_{\mathrm{dev}}\) y de estimación directa
de \(\widehat\Sigma\) se reportan por separado y en el total, conforme a PAP §4.4.1.

---

## 5. Aprendizaje de \(C_{\mathrm{dev}}\) antes de \(\widehat\Sigma\)

La caracterización usa un modelo sparse Pauli--Lindblad local sobre los cuatro qubits y las tres
aristas físicas seleccionadas. Se ejecuta y congela antes de comenzar cualquier repetición usada
para \(\widehat\Sigma\).

```yaml
Cdev_learning:
  model: sparse_Pauli_Lindblad
  locality: selected_four_qubits_and_three_path_edges
  ordering: strictly_before_Sigma_hat_data
  characterization_circuits_target: 200
  shots_per_characterization_circuit: 4096
  split: fixed_train_validation_split_before_execution
  gate_C1:
    heldout_relative_generalization_error_max: 0.20
    support_F1_min: 0.90
  if_gate_C1_fails:
    Sigma_prediction_endpoint_status: not_testable
    required_report: noise_characterization_failed
    device_level_language_allowed: false
  ledger:
    C_noiselearn_charged: true
    amortization_flag: non_amortized
```

En hardware no existe \(C_{\mathrm{dev}}^{true}\) observable. Por ello, los targets de Gate C1
se operacionalizan como error relativo de generalización sobre circuitos held-out y estabilidad
del soporte frente a particiones/epochs predefinidos; no se presentan como distancia a un canal
verdadero conocido. Si cualquiera de los dos targets falla, no se computa un veredicto sobre el
pullback: el resultado es una falla de caracterización, no una refutación de la teoría.

---

## 6. Estimación directa de \(\widehat\Sigma^{\mathrm{hardware}}\)

```yaml
Sigma_hat_sampling:
  gap_vector_dimension: 3
  methods: [Raw, Accuracy-ZNE, DA-ZNE]
  B_nominal: 4096
  shots_per_circuit: 4096
  R_target: 200
  epochs_target: 10
  repetitions_per_epoch_target: 20
  independent_repetitions: true
  schedule:
    interleaved_by_method_and_budget: true
    order_within_epoch: deterministic_balanced_rotation
    epoch_definition: contiguous_hardware_time_block
  covariance_estimator: sample_covariance_of_independent_gap_vectors
  uncertainty: cluster_bootstrap_by_epoch
  bootstrap_repetitions: 10000
  bootstrap_seed_stream: hardware_sigma_epoch_bootstrap
  ledger:
    C_Sigmahat_charged: true
    report_separately_and_in_total: true
    overlap_accounting_required: true
```

Cada repetición produce el vector completo de tres gaps para un método. Las unidades de
resampling son epochs completos, no shots individuales, para conservar la dependencia inducida
por drift. El orden de métodos rota de forma balanceada entre epochs y queda generado antes de la
primera ejecución.

---

## 7. Endpoint, tolerancia y regla de lenguaje

La métrica primaria es el error de ranking proyectado de PAP §3.3.1 y Gate C2, adaptado a
hardware con \(\widehat\Sigma^{\mathrm{hardware}}\) en el rol de la referencia. Para cada par
activo de métodos \((m,n)\),

\[
\delta^{\mathrm{rank,hw}}_{mn}(B)
=
\left|
\left\langle G_{mn}^{(m)}(B),
\Sigma_m^{\mathrm{pred,learned}}(B)-\widehat\Sigma_m^{\mathrm{hardware}}(B)
\right\rangle_F
+
\left\langle G_{mn}^{(n)}(B),
\Sigma_n^{\mathrm{pred,learned}}(B)-\widehat\Sigma_n^{\mathrm{hardware}}(B)
\right\rangle_F
\right|,
\]

donde \(G_{mn}^{(m)}\) y \(G_{mn}^{(n)}\) son los gradientes de la dirección que puede voltear
el ranking de riesgo, definidos en PAP §3.3.1. El gate primario es

\[
\operatorname{UCB}_{0.95}
\!\left[\delta^{\mathrm{rank,hw}}_{mn}(B)\right]
<
\rho_C\,|\Delta_{mn}^{\mathrm{pred}}(B)|,
\qquad \rho_C=0.25,
\]

para todos los pares activos. La UCB se obtiene mediante cluster bootstrap por epoch.

```yaml
primary_endpoint:
  comparison: "Sigma_pred = L M C_dev M^T L^T vs Sigma_hat_hardware"
  metric: projected_ranking_error
  gradients: "G_mn^(m), G_mn^(n) from PAP section 3.3.1"
  active_pair_rule: pairs_whose_predicted_risk_margin_can_affect_the_selector
  rho_C: 0.25
  uncertainty: 95_percent_cluster_bootstrap_CI_by_epoch
  pass_rule: upper_95CI_delta_rank_mn_lt_rho_C_times_abs_predicted_risk_margin
  multiple_pairs_rule: intersection_all_active_pairs_no_best_pair_or_method_selection

secondary_frobenius:
  metric: relative_Frobenius_error
  definition: "||Sigma_pred,learned - Sigma_hat_hardware||_F / (||Sigma_hat_hardware||_F + epsilon0)"
  epsilon0: 1.0e-12
  conservative_tolerance: 0.20
  pass_rule: relative_Frobenius_error_le_0.20_for_all_three_methods
  role: reported_conservative_secondary_not_primary_gate

secondary_diagnostics:
  - relative_operator_norm_error
  - elementwise_bootstrap_z_scores
  - eigenvalue_and_PSD_check
  - epoch_drift_trace
  status: descriptive_only
```

Gate C2 usa el error proyectado con `rho_C=0.25` como primario; el error Frobenius relativo
`<=0.20` es un criterio conservador secundario. Ambas tolerancias se fijan antes de hardware y
no se calibran a los datos. No se selecciona el par ni el método con mejor acuerdo: el gate
primario pasa solo si **todos** los pares activos cumplen su desigualdad proyectada.

```yaml
claim_language:
  if_projected_pass_and_frobenius_pass:
    result_label: Frobenius-conservative_pass
    allowed_language: device_level_noise_predicts_decision_covariance_in_this_local_microcell
    scope: local_microcell_only
  if_projected_pass_and_frobenius_fail:
    result_label: directionally-sensitive_pass
    required_explanation: matrix_error_lies_in_decisionally_innocuous_directions
    allowed_language: device_level_noise_predicts_decision_covariance_in_this_local_microcell
    scope: local_microcell_only
  if_projected_fail_or_inconclusive:
    required_language: honest_hardware_stress_test_failed_or_inconclusive
    forbidden_language:
      - device_level_prediction_of_covariance
      - device_level_prediction_of_shot_cost
    required_title_demotion: true
  never_allowed:
    - broad_hardware_validation_of_full_theory
    - universal_covariance_prediction
    - hardware_validation_of_E1_E2_E3
```

El lenguaje `device-level` está gateado exclusivamente al pase del endpoint primario proyectado.
Si el error proyectado pasa pero Frobenius falla, se explicita que el desacuerdo matricial cae en
direcciones decisionalmente inofensivas; Frobenius no puede rescatar un fallo del gate proyectado.

---

## 8. Feasibility mini-job y dimensionamiento ciego

Antes de comprometer el presupuesto principal se ejecuta un mini-job que mide quantum time y
comprueba que la lectura del observable no sea degenerada. No se estima \(\widehat\Sigma\), no se
calcula GRI, no se comparan selectores y no se inspecciona ningún endpoint de decisión.

```yaml
feasibility:
  status: required_before_final_seal
  circuit_count: 8
  allowed_range_from_design: [5, 10]
  shots_per_circuit: 4096
  allowed_outputs:
    - actual_quantum_time_consumed
    - queue_and_runtime_metadata
    - successful_counts_return
    - observable_not_degenerate_or_saturated
  forbidden_outputs:
    - decision_failure
    - GRI
    - MSE_selector_comparison
    - Sigma_hat
    - Sigma_pred_vs_Sigma_hat
  saturation_check: "counts not concentrated with probability 1 on one bitstring and finite nonzero empirical observable variance"
  executed_mini_job:
    job_ids: [d92mef8oamcc73db82v0]
    feasibility_quantum_time_minutes: 0.18333333333333332
    wall_clock_minutes: 68.18350672333423
    observable_not_saturated_all_circuits: true
    result_record: experiments/hardware_sigma/feasibility_result.json
```

El objetivo inicial, ya usado en la tabla de ejecutabilidad del paquete, es `R_target=200` con
`4096` shots. El mini-job solo dimensiona `R` por costo real mediante esta regla pre-especificada:

```yaml
runtime_sizing_rule:
  total_quantum_time_cap_minutes: 50
  preferred_window_minutes: [40, 50]
  shots_per_circuit_final: 4096
  R_cap: 200
  projected_C_noiselearn_time_minutes: 4.583333333333333
  projected_time_for_one_interleaved_all_methods_repetition_minutes: 0.6416666666666666
  R_final: 70
  R_final_rule_applied: >
    min(200, floor((50 min - 4.583333333333333 min) /
    0.6416666666666666 min)), rounded down to a multiple of 10 for complete epochs
  may_increase_above_200_if_fast: false
  outcome_inputs_forbidden: true
  if_projected_C_noiselearn_time_ge_50_minutes: stop_infeasible
```

`R_final`, la proyección de costo y el snapshot de calibración se escriben en este documento (o
en una enmienda versionada) y se sellan por hash + commit antes de la caracterización completa y
antes de cualquier dato de \(\widehat\Sigma\). Si el dimensionamiento produce un intervalo
demasiado ancho para resolver la tolerancia, el resultado se reporta como inconcluso; no se cambia
la tolerancia ni la celda.

---

## 9. Reproducibilidad y drift

```yaml
reproducibility:
  hardware_bit_reproducibility_claimed: false
  classical_postprocessing_deterministic: true
  archive:
    - backend_name
    - calibration_snapshot
    - transpilation_seed_and_layout
    - compiled_circuits
    - raw_counts
    - job_ids
    - timestamps
    - epoch_assignments
    - quantum_time_usage
    - ledger
    - bootstrap_seed
  drift_controls:
    - interleaved_methods
    - contiguous_epochs
    - cluster_bootstrap_by_epoch
    - report_epochwise_diagnostics
```

El hardware deriva en el tiempo; por tanto, no se reclama identidad bit-a-bit entre ejecuciones.
La reproducibilidad se apoya en datos crudos archivados, metadata completa, interleaving y
post-proceso determinista. Se reportan todos los epochs y cualquier drift observado, también si
debilita el resultado.

---

## 10. Disciplina y reglas de parada

1. Backend, mapping, celda, métrica, tolerancia, menú, `R_final`, shots y schedule se sellan por
   hash + commit antes de la corrida principal.
2. La celda no se cambia por acuerdo/desacuerdo con \(\Sigma^{\mathrm{pred}}\), por saturación
   observada después del feasibility, ni por resultados del FakeBackend.
3. El agente conoce los resultados FakeBackend, pero este experimento es distinto: valida el
   pullback de covarianza en una celda nueva y pequeña, no ventaja de decisión.
4. Si Gate C1 falla, se detiene antes del endpoint y se reporta falla de caracterización.
5. Si faltan jobs/epochs o el bootstrap no resuelve la tolerancia, se reporta inconcluso; no se
   agregan shots post hoc salvo una enmienda pre-data explícita y un nuevo sello.
6. PASS, FAIL e inconcluso se reportan tal como salgan. Hardware ejecutado nunca se oculta.
7. Este arm no modifica, valida ni invalida E1/E2/E3; conserva el framing `hardware stress test`.

---

## 11. Campos que deben quedar completos antes de ejecutar

```yaml
pre_run_lock_checklist:
  backend_frozen: ibm_marrakesh
  backend_calibration_snapshot_id: "2026-06-30 11:49:31-05:00"
  physical_qubits: [14, 15, 19, 35]
  calibration_score: 0.005940674965659587
  transpiled_depth: 36
  swap_count: 0
  noise_free_reference_candidate: 0   # argmin energia ideal HSMC001; gaps ideales [0.127093, 0.245308, 0.404948], sin degeneracion; computado clasico noiseless via build_candidate_landscape_for_graph, ciego a hardware (2026-07-01)
  feasibility_job_ids: [d92mef8oamcc73db82v0]
  feasibility_quantum_time_minutes: 0.18333333333333332
  projected_C_noiselearn_time_minutes: 4.583333333333333
  projected_time_per_interleaved_repetition: 0.6416666666666666
  R_final: 70
  final_document_sha256: recorded_in_sealing_commit_message   # el hash no puede auto-contenerse; el commit de sello lo registra
  git_commit: the_sealing_commit_of_this_file                 # commit en rama derisk-fakebackend-prereg
  execution_allowed_only_when_no_TBD_remains: true
```

Mientras cualquiera de estos campos permanezca `TBD`, la caracterización completa y la
estimación de \(\widehat\Sigma^{\mathrm{hardware}}\) están prohibidas.
