# Heterogeneous PEC De-risk Result

This computes the locked 2b de-risk metric from `het_pec_derisk.yaml`.
No confirmatory effect sizes are used.

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
| 256 | 0.129387329593 | 0.880119108723 | -0.750731779131 | -5.80220475601 | False | -29.01102378 |
| 512 | 0.025300511046 | 0.826083333017 | -0.800782821971 | -31.6508556098 | False | -158.254278049 |
| 1024 | 0.0014047836447 | 0.737091456741 | -0.735686673096 | -523.70105238 | False | -2618.5052619 |
| 2048 | 7.37528913219e-06 | 0.597871198295 | -0.597863823006 | -81063.1030581 | False | -405315.51529 |
| 4096 | 3.676896565e-10 | 0.404062899399 | -0.404062899032 | -1098923757.82 | False | -5494618789.09 |
| 8192 | 0 | 0.193397003307 | -0.193397003307 | NA | False | NA |

## Scale Treatment

A3 primitive moments keep the frozen three-scale layout. The same locked heterogeneous channel is supplied for all scale slots; the Raw gap map uses only lambda=1 coefficients [1,0,0].

## Secondary Frontier Summary

- rho_c: 1
- rho_gap_noise is reported per budget as relative_savings / 0.20.
