# Pilot Static Power Report

Diagnostic pilot report; not canonical and not part of verify/reference until freeze.

## Definitions

- Baseline is the MSE-selected method at each `(cell, budget)`.
- `MSE_m` is the empirical mean over F1a replicates and candidates of `(hat F_m - F_ideal)^2`.
- DA is selected by full Gaussian risk (GRI) from the same gap samples.
- Failure is the empirical event that at least one residual gap is non-positive.
- Paired decisions are counted as one shared confirmatory instance/replicate decision for MSE and DA at the same `(cell, budget)`.

## Gate Parameters

- critical_band: [0.15, 0.7]
- static_primary_min_paired_decisions: 1500
- confirmatory_static_design: 48 instances x 40 replicates = 1920 paired decisions
- minimum_detectable_relative_failure_reduction: 0.15
- bootstrap_repetitions: 10000
- alpha: 0.05

## Primary Static Cell

- primary_cell: P004
- B_star_operational: 512
- baseline failure_rate_MSE: 0.405
- choice rule: maximum distance from the nearest edge of `[0.15, 0.70]`, tie-broken by lower failure, lower budget, then cell id.

## Observed Paired Effect at B*

| cell | in_band | both_fail | both_ok | b_DA_better | c_DA_worse | fail_MSE | fail_DA | observed_rel_reduction | reaches_MDE_0.15 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| P001 | True | 66 | 99 | 29 | 6 | 0.475 | 0.36 | 0.242105 | True |
| P002 | True | 27 | 138 | 29 | 6 | 0.28 | 0.165 | 0.410714 | True |
| P003 | False | 0 | 200 | 0 | 0 | 0 | 0 | 0 | False |
| P004 | True | 61 | 102 | 20 | 17 | 0.405 | 0.39 | 0.037037 | False |

| pooled_in_band_at_B* | pilot_instances | paired_n_pilot | both_fail | both_ok | b_DA_better | c_DA_worse | fail_MSE | fail_DA | observed_rel_reduction | reaches_MDE_0.15 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| B*=512 | 3 | 600 | 154 | 339 | 78 | 29 | 0.386667 | 0.305 | 0.211207 | True |

- uncertainty_note: pooled effect uses 3 in-band pilot instances at B*; projected power assumes the confirmatory effect distribution is similar.

## Static Power Check

- paired_decisions_ok: True
- power_estimated_from_observed_pairs: 1
- simulation_model: multinomial bootstrap from observed pooled paired outcomes `(both_fail, both_ok, b, c)` at B*.
- no_hypothetical_15pct_power_number: true

## Critical Band

| cell | budget | failure_rate_MSE | MSE_selected_method | DA_selected_method |
|---|---:|---:|---|---|
| P001 | 256 | 0.55 | Decision-ZNE | Raw |
| P001 | 512 | 0.475 | Decision-ZNE | Raw |
| P001 | 1024 | 0.36 | Decision-ZNE | Raw |
| P001 | 2048 | 0.245 | Accuracy-ZNE | Raw |
| P001 | 4096 | 0.15 | Decision-ZNE | Raw |
| P002 | 256 | 0.48 | Decision-ZNE | Raw |
| P002 | 512 | 0.28 | Decision-ZNE | Raw |
| P004 | 256 | 0.5 | Decision-ZNE | Raw |
| P004 | 512 | 0.405 | Decision-ZNE | Raw |
| P004 | 1024 | 0.355 | Decision-ZNE | Raw |
| P004 | 2048 | 0.28 | Decision-ZNE | Raw |
| P004 | 4096 | 0.235 | Decision-ZNE | Raw |
| P004 | 8192 | 0.175 | Decision-ZNE | Raw |

## Static Pilot Table

| cell | budget | MSE_selected_method | DA_selected_method | failure_rate_MSE | failure_rate_DA | failure_rate_Raw | observed_rel_reduction | b_DA_better | c_DA_worse | in_band |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---|
| P001 | 256 | Decision-ZNE | Raw | 0.55 | 0.44 | 0.44 | 0.2 | 31 | 9 | True |
| P001 | 512 | Decision-ZNE | Raw | 0.475 | 0.36 | 0.36 | 0.242105 | 29 | 6 | True |
| P001 | 1024 | Decision-ZNE | Raw | 0.36 | 0.24 | 0.24 | 0.333333 | 31 | 7 | True |
| P001 | 2048 | Accuracy-ZNE | Raw | 0.245 | 0.19 | 0.19 | 0.22449 | 17 | 6 | True |
| P001 | 4096 | Decision-ZNE | Raw | 0.15 | 0.065 | 0.065 | 0.566667 | 20 | 3 | True |
| P001 | 8192 | Accuracy-ZNE | Raw | 0.045 | 0.015 | 0.015 | 0.666667 | 7 | 1 | False |
| P002 | 256 | Decision-ZNE | Raw | 0.48 | 0.315 | 0.315 | 0.34375 | 36 | 3 | True |
| P002 | 512 | Decision-ZNE | Raw | 0.28 | 0.165 | 0.165 | 0.410714 | 29 | 6 | True |
| P002 | 1024 | Accuracy-ZNE | Raw | 0.075 | 0.015 | 0.015 | 0.8 | 14 | 2 | False |
| P002 | 2048 | Accuracy-ZNE | Raw | 0.01 | 0 | 0 | 1 | 2 | 0 | False |
| P002 | 4096 | Decision-ZNE | Raw | 0 | 0 | 0 | 0 | 0 | 0 | False |
| P002 | 8192 | Accuracy-ZNE | Raw | 0 | 0 | 0 | 0 | 0 | 0 | False |
| P003 | 256 | Decision-ZNE | Raw | 0.05 | 0.015 | 0.015 | 0.7 | 7 | 0 | False |
| P003 | 512 | Decision-ZNE | Raw | 0 | 0 | 0 | 0 | 0 | 0 | False |
| P003 | 1024 | Accuracy-ZNE | Raw | 0 | 0 | 0 | 0 | 0 | 0 | False |
| P003 | 2048 | Decision-ZNE | Raw | 0 | 0 | 0 | 0 | 0 | 0 | False |
| P003 | 4096 | Decision-ZNE | Raw | 0 | 0 | 0 | 0 | 0 | 0 | False |
| P003 | 8192 | Decision-ZNE | Raw | 0 | 0 | 0 | 0 | 0 | 0 | False |
| P004 | 256 | Decision-ZNE | Raw | 0.5 | 0.49 | 0.49 | 0.02 | 21 | 19 | True |
| P004 | 512 | Decision-ZNE | Raw | 0.405 | 0.39 | 0.39 | 0.037037 | 20 | 17 | True |
| P004 | 1024 | Decision-ZNE | Raw | 0.355 | 0.335 | 0.335 | 0.056338 | 20 | 16 | True |
| P004 | 2048 | Decision-ZNE | Raw | 0.28 | 0.25 | 0.25 | 0.107143 | 19 | 13 | True |
| P004 | 4096 | Decision-ZNE | Raw | 0.235 | 0.22 | 0.22 | 0.0638298 | 15 | 12 | True |
| P004 | 8192 | Decision-ZNE | Raw | 0.175 | 0.135 | 0.135 | 0.228571 | 13 | 5 | True |

## Pending

- T_final y potencia dinamica: pendiente Fase B.
