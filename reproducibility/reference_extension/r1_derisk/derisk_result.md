# R1 Structured-Noise De-risk Result

This computes the locked R1 de-risk cell from `r1_structured_noise_derisk.yaml`.
No confirmatory ids are used and no rate sweep is performed.

## Graph Gate

- structured_noise_graph_equals_a3_graph: True
- num_qubits: 10
- num_edges: 15

## Channel

- family: amplitude_damping_plus_phase_damping
- gamma_amplitude_damping: 0.006
- gamma_phase_damping: 0.004
- scale_policy: multiply_each_gamma_by_zne_scale

## Ranking Diagnostic

- ideal_argmin: 0
- raw_lambda1_argmin: 0
- ranking_flip: False

## Budget Table

| budget | GRI_Raw | GRI_Accuracy-ZNE | GRI_Decision-ZNE | DA_selected | MSE_selected | DA<Raw | best_mitigated | best_mitigated<Raw | rho_gap_noise |
|---:|---:|---:|---:|:---|:---|:---:|:---|:---:|---:|
| 256 | 0.796436474902 | 0.802187329094 | 0.802130738729 | Raw | Accuracy-ZNE | False | Decision-ZNE | False | 0 |
| 512 | 0.746994916414 | 0.742780169003 | 0.742569603574 | Decision-ZNE | Decision-ZNE | True | Decision-ZNE | True | 0.0296207694497 |
| 1024 | 0.688610386827 | 0.662084999031 | 0.661645456989 | Decision-ZNE | Decision-ZNE | True | Decision-ZNE | True | 0.195792354824 |
| 2048 | 0.624214508815 | 0.558638725675 | 0.557904139271 | Decision-ZNE | Decision-ZNE | True | Decision-ZNE | True | 0.531150498809 |
| 4096 | 0.557318984258 | 0.436625030371 | 0.43558826301 | Decision-ZNE | Decision-ZNE | True | Decision-ZNE | True | 1.09210994679 |
| 8192 | 0.488864038424 | 0.306008219613 | 0.304759384292 | Decision-ZNE | Decision-ZNE | True | Decision-ZNE | True | 1.88298422119 |

## Secondary Frontier Summary

- rho_c: 1
- rho_gap_noise is reported per budget as relative_GRI_savings_DA_vs_Raw / 0.20.
