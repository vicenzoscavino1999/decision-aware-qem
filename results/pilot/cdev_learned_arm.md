# C_dev Learned Arm (Full)

Diagnostic only: not canonical, not part of verify/reference.

## Alcance (honesto)

- El canal de ruido en simulación es depolarizing UNIFORME: el mismo p1 en todos los qubits y el mismo p2 en todas las aristas.
- Los circuitos de caracterización NO son qubit-específicos; por eso los 25 generadores colapsan a 2 mediciones distintas. Esto es ESTIMACIÓN DE 2 PARÁMETROS GLOBALES (p1, p2) por caracterización finito-shot, NO sparse Pauli-Lindblad espacialmente resuelto.
- support_F1 es trivial por construcción, porque todos los generadores verdaderos son activos.
- El valor real del sparse PL para ruido heterogéneo/dispositivo queda diferido: ver DECISION_DIFERIDA_F1cB_canal_heterogeneo.md.

## Method

- Sparse PL basis: 1q generators plus weight-2 generators on graph edges.
- C1 weights are computed from frozen A3 gradients and active pairs before learning results.
- Learned p1/p2 are injected into the same A3 primitive moment function, then propagated through frozen gap_maps.

## Cost

| characterization_circuits | shots_per_circuit | total_shots | learning_seconds | total_seconds |
|---:|---:|---:|---:|---:|
| 1000 | 4096 | 4096000 | 8.36085 | 68.1716 |

## C1 Channel Recovery

- weights_sha256: sha256:807BBE1EE8D627DEC21D326C604F18572621901E7AE473F0C99EB5137054FE28
- generators: 25
- learned_p1: 0.0100086055
- learned_p2: 0.029907517
- cdev_learned_diag_sha256: sha256:471FB9E5C0FB929E3C54137B9F4E43FDAABEE89303156E4E78D765CEDEA1B6E4

| e_C | threshold | precision | recall | support_F1 | support_F1_min | c1_status |
|---:|---:|---:|---:|---:|---:|---|
| 0.0095756 | 0.2 | 1 | 1 | 1 | 0.9 | pass |

## C2 Propagation

| cell | pair_id | B | active_pair | delta_rank_C | tau_C | ratio | rel_frob | c2_status | frob_secondary |
|---|---|---:|---|---:|---:|---:|---:|---|---|
| P001 | Raw_vs_Accuracy-ZNE | 256 | True | 9.81655e-06 | 0.0349256 | 0.00028107 | 0.000195349 | pass | pass |
| P001 | Raw_vs_Accuracy-ZNE | 512 | True | 1.22923e-05 | 0.0393848 | 0.000312109 | 0.000195349 | pass | pass |
| P001 | Raw_vs_Accuracy-ZNE | 1024 | True | 5.40262e-06 | 0.0392153 | 0.000137768 | 0.000195349 | pass | pass |
| P001 | Raw_vs_Accuracy-ZNE | 2048 | True | 4.60594e-06 | 0.0341696 | 0.000134797 | 0.000195349 | pass | pass |
| P001 | Raw_vs_Accuracy-ZNE | 4096 | True | 1.24567e-05 | 0.0240397 | 0.000518174 | 0.000195349 | pass | pass |
| P001 | Raw_vs_Accuracy-ZNE | 8192 | True | 1.35467e-05 | 0.0112663 | 0.00120242 | 0.000195349 | pass | pass |
| P001 | Raw_vs_Decision-ZNE | 256 | True | 9.41184e-06 | 0.0348986 | 0.000269691 | 0.000197084 | pass | pass |
| P001 | Raw_vs_Decision-ZNE | 512 | True | 1.18727e-05 | 0.0393525 | 0.000301702 | 0.000197084 | pass | pass |
| P001 | Raw_vs_Decision-ZNE | 1024 | True | 4.94603e-06 | 0.0391819 | 0.000126232 | 0.000197084 | pass | pass |
| P001 | Raw_vs_Decision-ZNE | 2048 | True | 5.04559e-06 | 0.0341405 | 0.000147789 | 0.000197084 | pass | pass |
| P001 | Raw_vs_Decision-ZNE | 4096 | True | 1.28041e-05 | 0.024018 | 0.000533104 | 0.000197084 | pass | pass |
| P001 | Raw_vs_Decision-ZNE | 8192 | True | 1.37503e-05 | 0.0112537 | 0.00122184 | 0.000197084 | pass | pass |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 256 | False | 4.04713e-07 | 2.70883e-05 | 0.0149405 | 0.000182997 | pass | pass |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 512 | False | 4.19624e-07 | 3.22979e-05 | 0.0129923 | 0.000182997 | pass | pass |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 1024 | False | 4.56598e-07 | 3.33635e-05 | 0.0136856 | 0.000182997 | pass | pass |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 2048 | False | 4.39648e-07 | 2.91047e-05 | 0.0151057 | 0.000182997 | pass | pass |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 4096 | False | 3.47362e-07 | 2.16618e-05 | 0.0160357 | 0.000182997 | pass | pass |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 8192 | False | 2.03512e-07 | 1.25289e-05 | 0.0162434 | 0.000182997 | pass | pass |
| P002 | Raw_vs_Accuracy-ZNE | 256 | True | 2.82959e-05 | 0.065161 | 0.000434246 | 0.00039399 | pass | pass |
| P002 | Raw_vs_Accuracy-ZNE | 512 | True | 1.91742e-05 | 0.0475878 | 0.000402924 | 0.00039399 | pass | pass |
| P002 | Raw_vs_Accuracy-ZNE | 1024 | True | 3.28445e-05 | 0.01664 | 0.00197382 | 0.00039399 | pass | pass |
| P002 | Raw_vs_Accuracy-ZNE | 2048 | True | 8.61478e-06 | 0.00185302 | 0.00464904 | 0.00039399 | pass | pass |
| P002 | Raw_vs_Accuracy-ZNE | 4096 | False | 2.98227e-07 | 3.43595e-05 | 0.00867961 | 0.00039399 | pass | pass |
| P002 | Raw_vs_Accuracy-ZNE | 8192 | False | 4.3127e-10 | 2.54614e-08 | 0.0169382 | 0.00039399 | pass | pass |
| P002 | Raw_vs_Decision-ZNE | 256 | True | 2.66107e-05 | 0.0651544 | 0.000408425 | 0.000399381 | pass | pass |
| P002 | Raw_vs_Decision-ZNE | 512 | True | 2.09615e-05 | 0.0475557 | 0.000440778 | 0.000399381 | pass | pass |
| P002 | Raw_vs_Decision-ZNE | 1024 | True | 3.38654e-05 | 0.016613 | 0.00203849 | 0.000399381 | pass | pass |
| P002 | Raw_vs_Decision-ZNE | 2048 | True | 8.81344e-06 | 0.00184639 | 0.00477334 | 0.000399381 | pass | pass |
| P002 | Raw_vs_Decision-ZNE | 4096 | False | 3.03539e-07 | 3.41069e-05 | 0.00889965 | 0.000399381 | pass | pass |
| P002 | Raw_vs_Decision-ZNE | 8192 | False | 4.35771e-10 | 2.50966e-08 | 0.0173638 | 0.000399381 | pass | pass |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 256 | False | 1.68523e-06 | 6.63854e-06 | 0.253855 | 0.000367222 | pass | pass |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 512 | False | 1.7873e-06 | 3.20187e-05 | 0.0558204 | 0.000367222 | pass | pass |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 1024 | False | 1.02091e-06 | 2.7068e-05 | 0.0377166 | 0.000367222 | pass | pass |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 2048 | False | 1.98664e-07 | 6.6368e-06 | 0.0299337 | 0.000367222 | pass | pass |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 4096 | False | 5.31185e-09 | 2.52629e-07 | 0.0210263 | 0.000367222 | pass | pass |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 8192 | False | 4.50169e-12 | 3.64785e-10 | 0.0123407 | 0.000367222 | pass | pass |
| P003 | Raw_vs_Accuracy-ZNE | 256 | True | 4.22452e-06 | 0.00211448 | 0.0019979 | 0.000203245 | pass | pass |
| P003 | Raw_vs_Accuracy-ZNE | 512 | False | 2.90686e-07 | 7.0759e-05 | 0.00410811 | 0.000203245 | pass | pass |
| P003 | Raw_vs_Accuracy-ZNE | 1024 | False | 1.01709e-09 | 1.26985e-07 | 0.0080095 | 0.000203245 | pass | pass |
| P003 | Raw_vs_Accuracy-ZNE | 2048 | False | 9.22419e-15 | 5.89334e-13 | 0.00922419 | 0.000203245 | pass | pass |
| P003 | Raw_vs_Accuracy-ZNE | 4096 | False | 0 | 0 | 0 | 0.000203245 | pass | pass |
| P003 | Raw_vs_Accuracy-ZNE | 8192 | False | 0 | 0 | 0 | 0.000203245 | pass | pass |
| P003 | Raw_vs_Decision-ZNE | 256 | True | 4.30318e-06 | 0.00211383 | 0.00203572 | 0.000205461 | pass | pass |
| P003 | Raw_vs_Decision-ZNE | 512 | False | 2.95374e-07 | 7.06988e-05 | 0.00417793 | 0.000205461 | pass | pass |
| P003 | Raw_vs_Decision-ZNE | 1024 | False | 1.03224e-09 | 1.26761e-07 | 0.0081432 | 0.000205461 | pass | pass |
| P003 | Raw_vs_Decision-ZNE | 2048 | False | 9.45801e-15 | 5.87363e-13 | 0.00945801 | 0.000205461 | pass | pass |
| P003 | Raw_vs_Decision-ZNE | 4096 | False | 0 | 0 | 0 | 0.000205461 | pass | pass |
| P003 | Raw_vs_Decision-ZNE | 8192 | False | 0 | 0 | 0 | 0.000205461 | pass | pass |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 256 | False | 7.8658e-08 | 6.45915e-07 | 0.121778 | 0.000172564 | pass | pass |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 512 | False | 4.68865e-09 | 6.02564e-08 | 0.0778117 | 0.000172564 | pass | pass |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 1024 | False | 1.51515e-11 | 2.24251e-10 | 0.0675648 | 0.000172564 | pass | pass |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 2048 | False | 2.33821e-16 | 1.97065e-15 | 0.000233821 | 0.000172564 | pass | pass |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 4096 | False | 0 | 0 | 0 | 0.000172564 | pass | pass |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 8192 | False | 0 | 0 | 0 | 0.000172564 | pass | pass |
| P004 | Raw_vs_Accuracy-ZNE | 256 | True | 8.50612e-06 | 0.0191952 | 0.000443138 | 0.000259729 | pass | pass |
| P004 | Raw_vs_Accuracy-ZNE | 512 | True | 1.12358e-05 | 0.0198108 | 0.000567156 | 0.000259729 | pass | pass |
| P004 | Raw_vs_Accuracy-ZNE | 1024 | True | 1.46358e-05 | 0.0229667 | 0.00063726 | 0.000259729 | pass | pass |
| P004 | Raw_vs_Accuracy-ZNE | 2048 | True | 1.12562e-05 | 0.025522 | 0.00044104 | 0.000259729 | pass | pass |
| P004 | Raw_vs_Accuracy-ZNE | 4096 | True | 1.50907e-07 | 0.0228465 | 6.60525e-06 | 0.000259729 | pass | pass |
| P004 | Raw_vs_Accuracy-ZNE | 8192 | True | 1.03059e-05 | 0.0134273 | 0.000767534 | 0.000259729 | pass | pass |
| P004 | Raw_vs_Decision-ZNE | 256 | True | 8.22044e-06 | 0.0191891 | 0.000428392 | 0.00026223 | pass | pass |
| P004 | Raw_vs_Decision-ZNE | 512 | True | 1.09366e-05 | 0.0198042 | 0.000552238 | 0.00026223 | pass | pass |
| P004 | Raw_vs_Decision-ZNE | 1024 | True | 1.42929e-05 | 0.0229602 | 0.000622506 | 0.00026223 | pass | pass |
| P004 | Raw_vs_Decision-ZNE | 2048 | True | 1.0847e-05 | 0.0255145 | 0.000425131 | 0.00026223 | pass | pass |
| P004 | Raw_vs_Decision-ZNE | 4096 | True | 2.79117e-07 | 0.0228386 | 1.22213e-05 | 0.00026223 | pass | pass |
| P004 | Raw_vs_Decision-ZNE | 8192 | True | 1.0642e-05 | 0.0134211 | 0.000792931 | 0.00026223 | pass | pass |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 256 | False | 2.85681e-07 | 6.10594e-06 | 0.0467873 | 0.000234709 | pass | pass |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 512 | False | 2.99168e-07 | 6.57131e-06 | 0.0455264 | 0.000234709 | pass | pass |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 1024 | False | 3.4291e-07 | 6.504e-06 | 0.0527229 | 0.000234709 | pass | pass |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 2048 | False | 4.09195e-07 | 7.47181e-06 | 0.0547651 | 0.000234709 | pass | pass |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 4096 | False | 4.30024e-07 | 7.87731e-06 | 0.0545902 | 0.000234709 | pass | pass |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 8192 | False | 3.36086e-07 | 6.21006e-06 | 0.0541196 | 0.000234709 | pass | pass |

## C3 Interpretation

| cell | pair_id | B | active_pair | true_vs_sigmahat | learned_vs_sigmahat_ratio | gaussianity_valid_pair | sigmahat_audit | c3_interpretation |
|---|---|---:|---|---|---:|---|---|---|
| P001 | Raw_vs_Accuracy-ZNE | 256 | True | pass | 0.302555 | False | robust_pass | empirical_fallback_only |
| P001 | Raw_vs_Accuracy-ZNE | 512 | True | pass | 0.0573327 | True | robust_pass | no_failure_detected |
| P001 | Raw_vs_Accuracy-ZNE | 1024 | True | pass | 0.00834194 | True | robust_pass | no_failure_detected |
| P001 | Raw_vs_Accuracy-ZNE | 2048 | True | pass | 0.0545949 | True | robust_pass | no_failure_detected |
| P001 | Raw_vs_Accuracy-ZNE | 4096 | True | pass | 0.0672539 | True | robust_pass | no_failure_detected |
| P001 | Raw_vs_Accuracy-ZNE | 8192 | True | pass | 0.702621 | True | robust_pass | no_failure_detected |
| P001 | Raw_vs_Decision-ZNE | 256 | True | pass | 0.302728 | False | robust_pass | empirical_fallback_only |
| P001 | Raw_vs_Decision-ZNE | 512 | True | pass | 0.0571848 | True | robust_pass | no_failure_detected |
| P001 | Raw_vs_Decision-ZNE | 1024 | True | pass | 0.00520745 | True | robust_pass | no_failure_detected |
| P001 | Raw_vs_Decision-ZNE | 2048 | True | pass | 0.0450569 | True | robust_pass | no_failure_detected |
| P001 | Raw_vs_Decision-ZNE | 4096 | True | pass | 0.066109 | True | robust_pass | no_failure_detected |
| P001 | Raw_vs_Decision-ZNE | 8192 | True | pass | 0.686925 | True | robust_pass | no_failure_detected |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 256 | False | ambiguous | 0.078792 | False | ci_includes_1_sampling_sensitive | empirical_fallback_only |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 512 | False | ambiguous | 0.237453 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 1024 | False | ambiguous | 3.68948 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 2048 | False | ambiguous | 11.2428 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 4096 | False | ambiguous | 1.3367 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P001 | Accuracy-ZNE_vs_Decision-ZNE | 8192 | False | ambiguous | 14.8004 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P002 | Raw_vs_Accuracy-ZNE | 256 | True | pass | 0.0948659 | True | robust_pass | no_failure_detected |
| P002 | Raw_vs_Accuracy-ZNE | 512 | True | pass | 0.0177154 | True | robust_pass | no_failure_detected |
| P002 | Raw_vs_Accuracy-ZNE | 1024 | True | pass | 0.778356 | True | robust_pass | no_failure_detected |
| P002 | Raw_vs_Accuracy-ZNE | 2048 | True | pass | 1.80955 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P002 | Raw_vs_Accuracy-ZNE | 4096 | False | ambiguous | 0.56607 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P002 | Raw_vs_Accuracy-ZNE | 8192 | False | ambiguous | 8.21815 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P002 | Raw_vs_Decision-ZNE | 256 | True | pass | 0.0928019 | True | robust_pass | no_failure_detected |
| P002 | Raw_vs_Decision-ZNE | 512 | True | pass | 0.0224026 | True | robust_pass | no_failure_detected |
| P002 | Raw_vs_Decision-ZNE | 1024 | True | pass | 0.766108 | True | robust_pass | no_failure_detected |
| P002 | Raw_vs_Decision-ZNE | 2048 | True | pass | 1.71436 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P002 | Raw_vs_Decision-ZNE | 4096 | False | ambiguous | 0.526264 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P002 | Raw_vs_Decision-ZNE | 8192 | False | ambiguous | 8.42151 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 256 | False | ambiguous | 20.3531 | True | robust_fail | theory_or_model_limited |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 512 | False | ambiguous | 6.94386 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 1024 | False | ambiguous | 8.29566 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 2048 | False | ambiguous | 28.2928 | True | robust_fail | theory_or_model_limited |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 4096 | False | ambiguous | 5.94016 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P002 | Accuracy-ZNE_vs_Decision-ZNE | 8192 | False | ambiguous | 5.77254 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P003 | Raw_vs_Accuracy-ZNE | 256 | True | fail | 2.10947 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P003 | Raw_vs_Accuracy-ZNE | 512 | False | ambiguous | 1.8211 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P003 | Raw_vs_Accuracy-ZNE | 1024 | False | ambiguous | 0.64862 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P003 | Raw_vs_Accuracy-ZNE | 2048 | False | ambiguous | 0.895778 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P003 | Raw_vs_Accuracy-ZNE | 4096 | False | ambiguous | 0 | True | robust_pass | theory_or_model_limited |
| P003 | Raw_vs_Accuracy-ZNE | 8192 | False | ambiguous | 0 | True | robust_pass | theory_or_model_limited |
| P003 | Raw_vs_Decision-ZNE | 256 | True | fail | 2.10677 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P003 | Raw_vs_Decision-ZNE | 512 | False | ambiguous | 1.82754 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P003 | Raw_vs_Decision-ZNE | 1024 | False | ambiguous | 0.72681 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P003 | Raw_vs_Decision-ZNE | 2048 | False | ambiguous | 0.755557 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P003 | Raw_vs_Decision-ZNE | 4096 | False | ambiguous | 0 | True | robust_pass | theory_or_model_limited |
| P003 | Raw_vs_Decision-ZNE | 8192 | False | ambiguous | 0 | True | robust_pass | theory_or_model_limited |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 256 | False | ambiguous | 10.9446 | True | robust_fail | theory_or_model_limited |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 512 | False | ambiguous | 5.73217 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 1024 | False | ambiguous | 43.5493 | True | robust_fail | theory_or_model_limited |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 2048 | False | ambiguous | 0.140221 | True | robust_pass | theory_or_model_limited |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 4096 | False | ambiguous | 0 | True | robust_pass | theory_or_model_limited |
| P003 | Accuracy-ZNE_vs_Decision-ZNE | 8192 | False | ambiguous | 0 | True | robust_pass | theory_or_model_limited |
| P004 | Raw_vs_Accuracy-ZNE | 256 | True | pass | 0.147203 | True | robust_pass | no_failure_detected |
| P004 | Raw_vs_Accuracy-ZNE | 512 | True | pass | 0.324009 | True | robust_pass | no_failure_detected |
| P004 | Raw_vs_Accuracy-ZNE | 1024 | True | pass | 0.357614 | True | robust_pass | no_failure_detected |
| P004 | Raw_vs_Accuracy-ZNE | 2048 | True | pass | 0.0308016 | True | robust_pass | no_failure_detected |
| P004 | Raw_vs_Accuracy-ZNE | 4096 | True | pass | 0.0123661 | True | robust_pass | no_failure_detected |
| P004 | Raw_vs_Accuracy-ZNE | 8192 | True | pass | 0.0910449 | True | robust_pass | no_failure_detected |
| P004 | Raw_vs_Decision-ZNE | 256 | True | pass | 0.140817 | True | robust_pass | no_failure_detected |
| P004 | Raw_vs_Decision-ZNE | 512 | True | pass | 0.321536 | True | robust_pass | no_failure_detected |
| P004 | Raw_vs_Decision-ZNE | 1024 | True | pass | 0.349681 | True | robust_pass | no_failure_detected |
| P004 | Raw_vs_Decision-ZNE | 2048 | True | pass | 0.0250194 | True | robust_pass | no_failure_detected |
| P004 | Raw_vs_Decision-ZNE | 4096 | True | pass | 0.0160542 | True | robust_pass | no_failure_detected |
| P004 | Raw_vs_Decision-ZNE | 8192 | True | pass | 0.0850771 | True | robust_pass | no_failure_detected |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 256 | False | ambiguous | 20.2144 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 512 | False | ambiguous | 7.77594 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 1024 | False | ambiguous | 28.3611 | True | robust_fail | theory_or_model_limited |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 2048 | False | ambiguous | 19.7755 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 4096 | False | ambiguous | 10.6806 | True | ci_includes_1_sampling_sensitive | inconclusive |
| P004 | Accuracy-ZNE_vs_Decision-ZNE | 8192 | False | ambiguous | 12.9886 | True | ci_includes_1_sampling_sensitive | inconclusive |
