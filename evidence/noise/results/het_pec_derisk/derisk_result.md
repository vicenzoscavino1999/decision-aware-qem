# Heterogeneous PEC De-risk Result

This computes the locked 2b de-risk metric from `het_pec_derisk.yaml`.
No confirmatory effect sizes are used.
Gaussian scalar-overhead proxy: ideal gaps and gamma_squared times the Raw heterogeneous covariance; not signed PEC circuit sampling

## Graph Gate

- channel_graph_equals_a3_graph: True
- num_qubits: 10
- num_edges: 15

## PEC Overhead

- gamma_het: 9.43100562735
- gamma_squared_het: 88.9438671431
- p1_range: [0.00465583070075, 0.0151035605708]
- p2_range: [0.017030651994, 0.0546699889561]

## Ranking Diagnostic

- ideal_argmin: 0
- raw_het_argmin: 0
- ranking_flip: False
- min_mu_raw: 0.244281434509
- min_mu_ideal: 0.375986484389

## Budget Table

| budget | GRI_raw | GRI_pec | raw_minus_pec | relative_savings | PEC_wins | rho_gap_noise |
|---:|---:|---:|---:|---:|:---:|---:|
| 256 | 0.129392341437 | 0.880121112494 | -0.750728771057 | -5.80195676748 | False | -29.0097838374 |
| 512 | 0.02529916553 | 0.826088297416 | -0.800789131886 | -31.6527883473 | False | -158.263941737 |
| 1024 | 0.00140452348248 | 0.737094863879 | -0.735690340396 | -523.800669461 | False | -2619.0033473 |
| 2048 | 7.36728358808e-06 | 0.597867799312 | -0.597860432029 | -81150.728743 | False | -405753.643715 |
| 4096 | 3.6825909869e-10 | 0.40405822935 | -0.404058228982 | -1097211801.2 | False | -5486059005.99 |
| 8192 | 1.49627022658e-18 | 0.193397339366 | -0.193397339366 | -1.29252949053e+17 | False | -6.46264745266e+17 |

## Scale Treatment

A3 primitive moments keep the frozen three-scale layout. The same locked heterogeneous channel is supplied for all scale slots; the Raw gap map uses only lambda=1 coefficients [1,0,0].

## Secondary Frontier Summary

- rho_c: 1
- rho_gap_noise is reported per budget as relative_savings / 0.20.
