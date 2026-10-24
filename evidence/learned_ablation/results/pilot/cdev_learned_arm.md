# C_dev Learned Arm (Full)

Diagnostic only: not canonical, not part of verify/reference.

## Alcance

- El canal de ruido en simulación es depolarizing UNIFORME: el mismo p1 en todos los qubits y el mismo p2 en todas las aristas.
- Los circuitos de caracterización NO son qubit-específicos; por eso los 25 generadores colapsan a 2 mediciones distintas. Esto es ESTIMACIÓN DE 2 PARÁMETROS GLOBALES (p1, p2) por caracterización finito-shot, NO sparse Pauli-Lindblad espacialmente resuelto.
- support_F1 es trivial por construcción, porque todos los generadores verdaderos son activos.
- Las repeticiones usan circuitos idénticos; el nombre histórico pauli_twirls no implica aleatorización Pauli.

## Method

- Probe labels index repeated estimates of the same two global rates.
- C1 uses the historical proportional-variance weighting heuristic with corrected full gradients, fixed before channel samples; these weights are not exact derivatives with respect to physical rates.
- e_C is the weighted error of replicate estimates. e_C_aggregated is the error of the two rates actually used for propagation.
- Learned p1/p2 are simulated on the matching graph and candidate landscape with dense probabilities, then propagated through frozen gap_maps.
- C2 holds the archived ideal gap mean fixed and assesses covariance propagation only; it does not certify the full biased decision model.
- C3 retains archived sampling diagnostics as context. Their old derivative cannot certify the recalculated full-gradient comparison.

## Cost

| characterization_circuits | shots_per_circuit | total_shots | learning_seconds | total_seconds |
|---:|---:|---:|---:|---:|
| 1000 | 4096 | 4096000 | 3.75975 | 103.083 |

## C1 Channel Recovery

- weights_sha256: sha256:235F628A64087A19DABF4521677E42B5278E3B251B393D5E6BEE1B0DE4FA9ED5
- generators: 25
- learned_p1: 0.0100086055
- learned_p2: 0.029907517
- last_cell_cdev_learned_diag_sha256: sha256:CD5E3688204B47C885D8B82B1C6DB76CDE5EF9534C64211342D5880977E6CBBF
- All cell-specific primitives, covariances and gradients are saved in cdev_primitives/ and cdev_evidence/.

| e_C | threshold | precision | recall | support_F1 | support_F1_min | c1_status |
|---:|---:|---:|---:|---:|---:|---|
| 0.0095756 | 0.2 | 1 | 1 | 1 | 0.9 | pass |

- e_C_aggregated: 0.00252721076936

## C2 Propagation

| cell | pair_id | B | active_pair | delta_rank_C | tau_C | ratio | rel_frob | c2_status | frob_secondary |
|---|---|---:|---|---:|---:|---:|---:|---|---|
| P001 | Raw_vs_Accuracy-ZNE | 256 | True | 1.72743e-05 | 0.0349257 | 0.000494602 | 0.000195349 | pass | pass |
| P001 | Raw_vs_Accuracy-ZNE | 512 | True | 1.07909e-05 | 0.0393847 | 0.000273986 | 0.000195349 | pass | pass |
| P001 | Raw_vs_Accuracy-ZNE | 1024 | True | 2.25386e-06 | 0.0392153 | 5.74741e-05 | 0.000195349 | pass | pass |
| P001 | Raw_vs_Accuracy-ZNE | 2048 | True | 5.58357e-06 | 0.0341696 | 0.000163407 | 0.000195349 | pass | pass |
| P001 | Raw_vs_Accuracy-ZNE | 4096 | True | 1.25019e-05 | 0.0240397 | 0.000520054 | 0.000195349 | pass | pass |
| P001 | Raw_vs_Accuracy-ZNE | 8192 | True | 1.35468e-05 | 0.0112663 | 0.00120242 | 0.000195349 | pass | pass |
| P001 | Raw_vs_Decision-ZNE | 256 | True | 1.68576e-05 | 0.0348987 | 0.000483046 | 0.000197084 | pass | pass |
| P001 | Raw_vs_Decision-ZNE | 512 | True | 1.03035e-05 | 0.0393524 | 0.000261828 | 0.000197084 | pass | pass |
| P001 | Raw_vs_Decision-ZNE | 1024 | True | 1.75587e-06 | 0.039182 | 4.48132e-05 | 0.000197084 | pass | pass |
| P001 | Raw_vs_Decision-ZNE | 2048 | True | 6.0317e-06 | 0.0341405 | 0.000176673 | 0.000197084 | pass | pass |
| P001 | Raw_vs_Decision-ZNE | 4096 | True | 1.28495e-05 | 0.024018 | 0.000534996 | 0.000197084 | pass | pass |
| P001 | Raw_vs_Decision-ZNE | 8192 | True | 1.37503e-05 | 0.0112537 | 0.00122185 | 0.000197084 | pass | pass |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 256 | False | 4.16694e-07 | 2.70885e-05 | 0.0153827 | 0.000182997 | inactive | pass |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 512 | False | 4.8731e-07 | 3.22982e-05 | 0.0150878 | 0.000182997 | inactive | pass |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 1024 | False | 4.97995e-07 | 3.33634e-05 | 0.0149264 | 0.000182997 | inactive | pass |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 2048 | False | 4.48131e-07 | 2.91047e-05 | 0.0153972 | 0.000182997 | inactive | pass |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 4096 | False | 3.47594e-07 | 2.16618e-05 | 0.0160464 | 0.000182997 | inactive | pass |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 8192 | False | 2.03512e-07 | 1.25289e-05 | 0.0162434 | 0.000182997 | inactive | pass |
| P002 | Raw_vs_Accuracy-ZNE | 256 | True | 3.4938e-05 | 0.0651601 | 0.000536187 | 0.00039399 | pass | pass |
| P002 | Raw_vs_Accuracy-ZNE | 512 | True | 2.35866e-05 | 0.0475871 | 0.000495652 | 0.00039399 | pass | pass |
| P002 | Raw_vs_Accuracy-ZNE | 1024 | True | 3.60024e-05 | 0.0166411 | 0.00216346 | 0.00039399 | pass | pass |
| P002 | Raw_vs_Accuracy-ZNE | 2048 | True | 8.75194e-06 | 0.0018526 | 0.00472413 | 0.00039399 | pass | pass |
| P002 | Raw_vs_Accuracy-ZNE | 4096 | False | 3.06505e-07 | 3.42825e-05 | 0.00894056 | 0.00039399 | inactive | pass |
| P002 | Raw_vs_Accuracy-ZNE | 8192 | False | 4.31468e-10 | 2.54324e-08 | 0.0169653 | 0.00039399 | inactive | pass |
| P002 | Raw_vs_Decision-ZNE | 256 | True | 3.30718e-05 | 0.0651534 | 0.000507599 | 0.000399381 | pass | pass |
| P002 | Raw_vs_Decision-ZNE | 512 | True | 2.55621e-05 | 0.0475551 | 0.000537527 | 0.000399381 | pass | pass |
| P002 | Raw_vs_Decision-ZNE | 1024 | True | 3.71079e-05 | 0.016614 | 0.00223353 | 0.000399381 | pass | pass |
| P002 | Raw_vs_Decision-ZNE | 2048 | True | 8.95371e-06 | 0.00184597 | 0.00485042 | 0.000399381 | pass | pass |
| P002 | Raw_vs_Decision-ZNE | 4096 | False | 3.11994e-07 | 3.40305e-05 | 0.00916806 | 0.000399381 | inactive | pass |
| P002 | Raw_vs_Decision-ZNE | 8192 | False | 4.35973e-10 | 2.5068e-08 | 0.0173916 | 0.000399381 | inactive | pass |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 256 | False | 1.86618e-06 | 6.63678e-06 | 0.281187 | 0.000367222 | inactive | pass |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 512 | False | 1.97547e-06 | 3.20171e-05 | 0.0617003 | 0.000367222 | inactive | pass |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 1024 | False | 1.10551e-06 | 2.70721e-05 | 0.0408357 | 0.000367222 | inactive | pass |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 2048 | False | 2.01774e-07 | 6.63541e-06 | 0.0304087 | 0.000367222 | inactive | pass |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 4096 | False | 5.48852e-09 | 2.52058e-07 | 0.0217748 | 0.000367222 | inactive | pass |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 8192 | False | 4.50405e-12 | 3.64375e-10 | 0.012361 | 0.000367222 | inactive | pass |
| P003 | Raw_vs_Accuracy-ZNE | 256 | True | 4.26491e-06 | 0.00211443 | 0.00201705 | 0.000203245 | pass | pass |
| P003 | Raw_vs_Accuracy-ZNE | 512 | False | 2.90774e-07 | 7.07504e-05 | 0.00410985 | 0.000203245 | inactive | pass |
| P003 | Raw_vs_Accuracy-ZNE | 1024 | False | 1.01714e-09 | 1.26991e-07 | 0.00800954 | 0.000203245 | inactive | pass |
| P003 | Raw_vs_Accuracy-ZNE | 2048 | False | 9.27281e-15 | 5.89405e-13 | 0.00927281 | 0.000203245 | inactive | pass |
| P003 | Raw_vs_Accuracy-ZNE | 4096 | False | 5.46591e-25 | 1.75411e-23 | 5.46591e-13 | 0.000203245 | inactive | pass |
| P003 | Raw_vs_Accuracy-ZNE | 8192 | False | 1.34293e-45 | 2.16573e-44 | 1.34293e-33 | 0.000203245 | inactive | pass |
| P003 | Raw_vs_Decision-ZNE | 256 | True | 4.34491e-06 | 0.00211379 | 0.00205551 | 0.000205461 | pass | pass |
| P003 | Raw_vs_Decision-ZNE | 512 | False | 2.95464e-07 | 7.06901e-05 | 0.00417971 | 0.000205461 | inactive | pass |
| P003 | Raw_vs_Decision-ZNE | 1024 | False | 1.03229e-09 | 1.26767e-07 | 0.00814324 | 0.000205461 | inactive | pass |
| P003 | Raw_vs_Decision-ZNE | 2048 | False | 9.39472e-15 | 5.87356e-13 | 0.00939472 | 0.000205461 | inactive | pass |
| P003 | Raw_vs_Decision-ZNE | 4096 | False | 5.5189e-25 | 1.74206e-23 | 5.5189e-13 | 0.000205461 | inactive | pass |
| P003 | Raw_vs_Decision-ZNE | 8192 | False | 1.34672e-45 | 2.13622e-44 | 1.34672e-33 | 0.000205461 | inactive | pass |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 256 | False | 8.00055e-08 | 6.46e-07 | 0.123848 | 0.000172564 | inactive | pass |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 512 | False | 4.69085e-09 | 6.02687e-08 | 0.0778322 | 0.000172564 | inactive | pass |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 1024 | False | 1.51532e-11 | 2.24247e-10 | 0.0675737 | 0.000172564 | inactive | pass |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 2048 | False | 1.21912e-16 | 2.04866e-15 | 0.000121912 | 0.000172564 | inactive | pass |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 4096 | False | 5.29919e-27 | 1.20555e-25 | 5.29919e-15 | 0.000172564 | inactive | pass |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 8192 | False | 3.7949e-48 | 2.95185e-46 | 3.7949e-36 | 0.000172564 | inactive | pass |
| P004 | Raw_vs_Accuracy-ZNE | 256 | True | 8.52238e-06 | 0.0191952 | 0.000443985 | 0.000259729 | pass | pass |
| P004 | Raw_vs_Accuracy-ZNE | 512 | True | 1.12358e-05 | 0.0198108 | 0.000567157 | 0.000259729 | pass | pass |
| P004 | Raw_vs_Accuracy-ZNE | 1024 | True | 1.46358e-05 | 0.0229667 | 0.00063726 | 0.000259729 | pass | pass |
| P004 | Raw_vs_Accuracy-ZNE | 2048 | True | 1.12562e-05 | 0.025522 | 0.00044104 | 0.000259729 | pass | pass |
| P004 | Raw_vs_Accuracy-ZNE | 4096 | True | 1.50907e-07 | 0.0228465 | 6.60525e-06 | 0.000259729 | pass | pass |
| P004 | Raw_vs_Accuracy-ZNE | 8192 | True | 1.03059e-05 | 0.0134273 | 0.000767534 | 0.000259729 | pass | pass |
| P004 | Raw_vs_Decision-ZNE | 256 | True | 8.23671e-06 | 0.0191891 | 0.000429239 | 0.00026223 | pass | pass |
| P004 | Raw_vs_Decision-ZNE | 512 | True | 1.09366e-05 | 0.0198042 | 0.000552239 | 0.00026223 | pass | pass |
| P004 | Raw_vs_Decision-ZNE | 1024 | True | 1.42929e-05 | 0.0229602 | 0.000622506 | 0.00026223 | pass | pass |
| P004 | Raw_vs_Decision-ZNE | 2048 | True | 1.0847e-05 | 0.0255145 | 0.000425131 | 0.00026223 | pass | pass |
| P004 | Raw_vs_Decision-ZNE | 4096 | True | 2.79117e-07 | 0.0228386 | 1.22213e-05 | 0.00026223 | pass | pass |
| P004 | Raw_vs_Decision-ZNE | 8192 | True | 1.0642e-05 | 0.0134211 | 0.000792931 | 0.00026223 | pass | pass |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 256 | False | 2.85673e-07 | 6.10593e-06 | 0.0467861 | 0.000234709 | inactive | pass |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 512 | False | 2.99168e-07 | 6.57131e-06 | 0.0455264 | 0.000234709 | inactive | pass |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 1024 | False | 3.4291e-07 | 6.504e-06 | 0.0527229 | 0.000234709 | inactive | pass |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 2048 | False | 4.09195e-07 | 7.47181e-06 | 0.0547651 | 0.000234709 | inactive | pass |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 4096 | False | 4.30024e-07 | 7.87731e-06 | 0.0545902 | 0.000234709 | inactive | pass |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 8192 | False | 3.36086e-07 | 6.21006e-06 | 0.0541196 | 0.000234709 | inactive | pass |

## C3 Interpretation

| cell | pair_id | B | active_pair | true_vs_sigmahat | learned_vs_sigmahat_ratio | gaussianity_valid_pair | sigmahat_audit | c3_interpretation |
|---|---|---:|---|---|---:|---|---|---|
| P001 | Raw_vs_Accuracy-ZNE | 256 | True | pass | 0.374391 | False | robust_pass | empirical_fallback_only |
| P001 | Raw_vs_Accuracy-ZNE | 512 | True | pass | 0.124945 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P001 | Raw_vs_Accuracy-ZNE | 1024 | True | pass | 0.0225162 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P001 | Raw_vs_Accuracy-ZNE | 2048 | True | pass | 0.0685165 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P001 | Raw_vs_Accuracy-ZNE | 4096 | True | pass | 0.0663243 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P001 | Raw_vs_Accuracy-ZNE | 8192 | True | pass | 0.70262 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P001 | Raw_vs_Decision-ZNE | 256 | True | pass | 0.374227 | False | robust_pass | empirical_fallback_only |
| P001 | Raw_vs_Decision-ZNE | 512 | True | pass | 0.127774 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P001 | Raw_vs_Decision-ZNE | 1024 | True | pass | 0.0255971 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P001 | Raw_vs_Decision-ZNE | 2048 | True | pass | 0.0589598 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P001 | Raw_vs_Decision-ZNE | 4096 | True | pass | 0.0652168 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P001 | Raw_vs_Decision-ZNE | 8192 | True | pass | 0.686925 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 256 | False | pass | 0.585799 | False | ci_includes_1_sampling_sensitive | inactive_pair |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 512 | False | fail | 3.32163 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 1024 | False | fail | 3.59566 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 2048 | False | fail | 11.2788 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 4096 | False | fail | 1.29429 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 8192 | False | fail | 14.8005 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P002 | Raw_vs_Accuracy-ZNE | 256 | True | pass | 0.0287832 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P002 | Raw_vs_Accuracy-ZNE | 512 | True | pass | 0.0402407 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P002 | Raw_vs_Accuracy-ZNE | 1024 | True | pass | 0.79653 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P002 | Raw_vs_Accuracy-ZNE | 2048 | True | fail | 1.80496 | True | ci_includes_1_sampling_sensitive | inconclusive_sampling |
| P002 | Raw_vs_Accuracy-ZNE | 4096 | False | pass | 0.502084 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P002 | Raw_vs_Accuracy-ZNE | 8192 | False | fail | 8.22778 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P002 | Raw_vs_Decision-ZNE | 256 | True | pass | 0.0268602 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P002 | Raw_vs_Decision-ZNE | 512 | True | pass | 0.0396108 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P002 | Raw_vs_Decision-ZNE | 1024 | True | pass | 0.781764 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P002 | Raw_vs_Decision-ZNE | 2048 | True | fail | 1.70865 | True | ci_includes_1_sampling_sensitive | inconclusive_sampling |
| P002 | Raw_vs_Decision-ZNE | 4096 | False | pass | 0.459673 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P002 | Raw_vs_Decision-ZNE | 8192 | False | fail | 8.43143 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 256 | False | fail | 18.907 | True | robust_fail | inactive_pair |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 512 | False | fail | 0.975747 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 1024 | False | fail | 9.85857 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 2048 | False | fail | 28.5989 | True | robust_fail | inactive_pair |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 4096 | False | fail | 6.22802 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 8192 | False | fail | 5.78238 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P003 | Raw_vs_Accuracy-ZNE | 256 | True | fail | 2.10969 | True | ci_includes_1_sampling_sensitive | inconclusive_sampling |
| P003 | Raw_vs_Accuracy-ZNE | 512 | False | fail | 1.82148 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P003 | Raw_vs_Accuracy-ZNE | 1024 | False | pass | 0.648482 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P003 | Raw_vs_Accuracy-ZNE | 2048 | False | pass | 0.900518 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P003 | Raw_vs_Accuracy-ZNE | 4096 | False | pass | 3.96607e-10 | True | robust_pass | inactive_pair |
| P003 | Raw_vs_Accuracy-ZNE | 8192 | False | pass | 2.00179e-31 | True | robust_pass | inactive_pair |
| P003 | Raw_vs_Decision-ZNE | 256 | True | fail | 2.10628 | True | ci_includes_1_sampling_sensitive | inconclusive_sampling |
| P003 | Raw_vs_Decision-ZNE | 512 | False | fail | 1.82794 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P003 | Raw_vs_Decision-ZNE | 1024 | False | pass | 0.726672 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P003 | Raw_vs_Decision-ZNE | 2048 | False | pass | 0.75052 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P003 | Raw_vs_Decision-ZNE | 4096 | False | pass | 3.85966e-10 | True | robust_pass | inactive_pair |
| P003 | Raw_vs_Decision-ZNE | 8192 | False | pass | 1.79376e-31 | True | robust_pass | inactive_pair |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 256 | False | fail | 13.2895 | True | robust_fail | inactive_pair |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 512 | False | fail | 5.7533 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 1024 | False | fail | 43.5528 | True | robust_fail | inactive_pair |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 2048 | False | pass | 0.149998 | True | robust_pass | inactive_pair |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 4096 | False | pass | 1.06408e-11 | True | robust_pass | inactive_pair |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 8192 | False | pass | 2.08029e-32 | True | robust_pass | inactive_pair |
| P004 | Raw_vs_Accuracy-ZNE | 256 | True | pass | 0.146583 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P004 | Raw_vs_Accuracy-ZNE | 512 | True | pass | 0.324009 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P004 | Raw_vs_Accuracy-ZNE | 1024 | True | pass | 0.357614 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P004 | Raw_vs_Accuracy-ZNE | 2048 | True | pass | 0.0308016 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P004 | Raw_vs_Accuracy-ZNE | 4096 | True | pass | 0.0123661 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P004 | Raw_vs_Accuracy-ZNE | 8192 | True | pass | 0.0910449 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P004 | Raw_vs_Decision-ZNE | 256 | True | pass | 0.140201 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P004 | Raw_vs_Decision-ZNE | 512 | True | pass | 0.321536 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P004 | Raw_vs_Decision-ZNE | 1024 | True | pass | 0.349681 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P004 | Raw_vs_Decision-ZNE | 2048 | True | pass | 0.0250194 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P004 | Raw_vs_Decision-ZNE | 4096 | True | pass | 0.0160542 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P004 | Raw_vs_Decision-ZNE | 8192 | True | pass | 0.0850771 | True | robust_pass | inconclusive_legacy_sampling_audit |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 256 | False | fail | 20.2038 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 512 | False | fail | 7.77594 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 1024 | False | fail | 28.3611 | True | robust_fail | inactive_pair |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 2048 | False | fail | 19.7755 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 4096 | False | fail | 10.6806 | True | ci_includes_1_sampling_sensitive | inactive_pair |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 8192 | False | fail | 12.9886 | True | ci_includes_1_sampling_sensitive | inactive_pair |
