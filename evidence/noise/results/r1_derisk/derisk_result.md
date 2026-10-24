# R1 Structured-Noise De-risk Result

This computes the locked R1 de-risk cell from `r1_structured_noise_derisk.yaml`.
No confirmatory ids are used and no rate sweep is performed.
Oracle analytic control; B shots per candidate per scale. Raw uses B, ZNE uses 3B; this is not an equal-total-cost comparison.

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
| 256 | 0.796438776047 | 0.802192271363 | 0.802135665012 | Raw | Accuracy-ZNE | False | Decision-ZNE | False | 0 |
| 512 | 0.746995868002 | 0.742782626612 | 0.742572060717 | Decision-ZNE | Decision-ZNE | True | Decision-ZNE | True | 0.0296106543184 |
| 1024 | 0.688610769242 | 0.662085622364 | 0.66164608899 | Decision-ZNE | Decision-ZNE | True | Decision-ZNE | True | 0.19579043385 |
| 2048 | 0.624214788625 | 0.558638814125 | 0.557904244396 | Decision-ZNE | Decision-ZNE | True | Decision-ZNE | True | 0.531151659955 |
| 4096 | 0.557319072149 | 0.436625199394 | 0.435588457907 | Decision-ZNE | Decision-ZNE | True | Decision-ZNE | True | 1.09210881454 |
| 8192 | 0.488864084168 | 0.306008258956 | 0.304759458958 | Decision-ZNE | Decision-ZNE | True | Decision-ZNE | True | 1.88298374918 |

## Secondary Frontier Summary

- rho_c: 1
- rho_gap_noise is reported per budget as relative_GRI_savings_DA_vs_Raw / 0.20.
