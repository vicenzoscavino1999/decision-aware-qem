# Phase 0 Executability Audit

This is a feasibility order-of-magnitude gate, not confirmatory accounting.

## Benchmark Cell

- Qubits: 10; QAOA-MaxCut depth: 2; budget grid: [256, 512, 1024, 2048, 4096, 8192]
- Max wall hours per sim block: 48

## Execution Model Assumptions

- Nested budget subsampling: each candidate evaluation runs once at B_max=8192; lower budgets reuse prefixes/common random numbers. Shot cost is proportional to B_max, not sum(grid).
- Circuit batching: K_batch=50 candidate circuits are submitted in one AerSimulator.run([...]) call.
- Refined simulation wall time uses the measured batched amortized time per circuit; timings are machine-dependent and warning-only.
- Sparse-PL characterization is also batched and uses the conservative per-circuit time measured at B_max, although its characterization budget is smaller.

## Measured Single-Circuit Timing

| shots | median_seconds | seconds_per_shot |
|---:|---:|---:|
| 256 | 0.137857 | 0.000538503 |
| 512 | 0.201357 | 0.000393276 |
| 1024 | 0.325648 | 0.000318016 |
| 2048 | 0.218465 | 0.000106672 |
| 4096 | 0.228353 | 0.000055750 |
| 8192 | 0.256729 | 0.000031339 |

## Measured Batched Timing

| shots | K_batch | median_total_seconds | amortized_seconds_per_circuit |
|---:|---:|---:|---:|
| 8192 | 50 | 8.848611 | 0.176972220 |

## Refined vs Naive Upper Bound

The naive upper bound repeats every evaluation at every grid budget and uses one Aer call per circuit.

| block | refined_estimated_shots | refined_wall_hours | naive_estimated_shots | naive_wall_hours |
|---|---:|---:|---:|---:|
| E1_static | 921600000 | 5.530382 | 1814400000 | 42.762797 |
| E2_dynamic | 2949120000 | 17.697222 | 5806080000 | 136.840950 |

## Cost Multipliers

- E1_static: `1500 * 25 * 3 evaluations * B_max shots`
- E2_dynamic: `1200 * 20 * 5 * 3 evaluations * B_max shots`
- E3_pullback: `3 methods * 200 evaluations * B_max shots`
- Sparse_PL_Cdev: `200 * 4096 * 1`
- Hardware_Sigma_microcell: `3 gaps * 3 methods * 200 replicates * 4096 shots`
- Hardware_3budget_ordering: `3 budgets * 25 batches * 4096 shots`
- Scaling_4_6_8: `3 sizes * 3 budgets * 5 candidates * 3 methods * 1024 shots; batched wall time`

## Executability Budget Table

| block | primary_unit | N_minimum | estimated_shots | wall_hours | backend_or_resource | risk | decision |
|---|---|---:|---:|---:|---|---|---|
| E1_static | paired_decisions | 1500 | 921600000 | 5.530382 | sim/Aer | within sim ceiling | go |
| E2_dynamic | trajectories | 1200 | 2949120000 | 17.697222 | sim/Aer | within sim ceiling | go |
| E3_pullback | Sigma_hat_replicates | 200 | 4915200 | 0.029495 | sim/Aer | within sim ceiling | go |
| Sparse_PL_Cdev | characterization_circuits | 200 | 819200 | 0.009832 | sim/Aer | within sim ceiling | go |
| Hardware_Sigma_microcell | schedulability_only | 200 | 7372800 | 0.000000 | IBM_hardware | schedulability only; no hardware submitted | conditional |
| Hardware_3budget_ordering | schedulability_only | 25 | 307200 | 0.000000 | IBM_hardware | schedulability only; no hardware submitted | conditional |
| Scaling_4_6_8 | trend_only | 3 | 138240 | 0.006636 | sim/Aer | trend only small scaling probe | go |

## Gate Global

- global_gate: go
- recommended_track: PRXQ
- PRXQ gate rule: E1, E2, and E3 must be go, and Hardware-Sigma must be go or conditional-pending.
