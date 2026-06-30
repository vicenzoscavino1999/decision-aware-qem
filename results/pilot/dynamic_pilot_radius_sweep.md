# Dynamic Pilot Radius Sweep

Diagnostic recalibration probe only: not canonical, not part of verify/reference, and not frozen.

## Setup

- profile: radius_sweep
- instances: ['P001']
- trajectories_per_radius: 20
- max_rounds: 4
- candidates_per_round: 5
- budget_grid: [256, 512, 1024, 2048, 4096, 8192]
- B_max: 8192
- candidate_radius_grid: [0.12, 0.16, 0.24, 0.32]
- epsilon_quantile: 0.25
- selector_primary: method-only argmin; no decision_score_z.
- safeguards: same candidates, initial points, budget grid, stopping rule, and Aer shot memory for DA/MSE.

## Neutral Selection Rule

- choose smallest radius with DA ceiling >= 0.85 and MSE ceiling >= 0.85.
- require MSE rise = P_success(B_max) - P_success(256) >= 0.15.
- this rule does not use the DA-vs-MSE margin.

## Radius Selection Table

| radius | DA_P@256 | MSE_P@256 | DA_ceiling | MSE_ceiling | MSE_rise | low_budget_discriminates | eligible_by_rule |
|---:|---:|---:|---:|---:|---:|---|---|
| 0.12 | 0.6 | 0.6 | 0.65 | 0.7 | 0.1 | False | False |
| 0.16 | 0.65 | 0.6 | 0.7 | 0.65 | 0.05 | True | False |
| 0.24 | 0.75 | 0.75 | 0.8 | 0.8 | 0.05 | False | False |
| 0.32 | 0.8 | 0.7 | 0.8 | 0.8 | 0.1 | True | False |

- chosen_radius_by_rule: none
- if_none: propose increasing epsilon_quantile slightly before hash freeze; not applied here.

## P(success; B) Curves

| radius | selector | budget | selected_method | shots_per_candidate | trajectories | successes | P_success |
|---:|---|---:|---|---:|---:|---:|---:|
| 0.12 | DA | 256 | Raw | 256 | 20 | 12 | 0.6 |
| 0.12 | DA | 512 | Raw | 512 | 20 | 12 | 0.6 |
| 0.12 | DA | 1024 | Raw | 1024 | 20 | 13 | 0.65 |
| 0.12 | DA | 2048 | Raw | 2048 | 20 | 13 | 0.65 |
| 0.12 | DA | 4096 | Raw | 4096 | 20 | 14 | 0.7 |
| 0.12 | DA | 8192 | Raw | 8192 | 20 | 13 | 0.65 |
| 0.12 | MSE | 256 | Decision-ZNE | 768 | 20 | 12 | 0.6 |
| 0.12 | MSE | 512 | Decision-ZNE | 1536 | 20 | 11 | 0.55 |
| 0.12 | MSE | 1024 | Decision-ZNE | 3072 | 20 | 13 | 0.65 |
| 0.12 | MSE | 2048 | Accuracy-ZNE | 6144 | 20 | 13 | 0.65 |
| 0.12 | MSE | 4096 | Decision-ZNE | 12288 | 20 | 14 | 0.7 |
| 0.12 | MSE | 8192 | Accuracy-ZNE | 24576 | 20 | 14 | 0.7 |
| 0.16 | DA | 256 | Raw | 256 | 20 | 13 | 0.65 |
| 0.16 | DA | 512 | Raw | 512 | 20 | 14 | 0.7 |
| 0.16 | DA | 1024 | Raw | 1024 | 20 | 14 | 0.7 |
| 0.16 | DA | 2048 | Raw | 2048 | 20 | 13 | 0.65 |
| 0.16 | DA | 4096 | Raw | 4096 | 20 | 13 | 0.65 |
| 0.16 | DA | 8192 | Raw | 8192 | 20 | 14 | 0.7 |
| 0.16 | MSE | 256 | Decision-ZNE | 768 | 20 | 12 | 0.6 |
| 0.16 | MSE | 512 | Decision-ZNE | 1536 | 20 | 14 | 0.7 |
| 0.16 | MSE | 1024 | Decision-ZNE | 3072 | 20 | 14 | 0.7 |
| 0.16 | MSE | 2048 | Accuracy-ZNE | 6144 | 20 | 13 | 0.65 |
| 0.16 | MSE | 4096 | Decision-ZNE | 12288 | 20 | 13 | 0.65 |
| 0.16 | MSE | 8192 | Accuracy-ZNE | 24576 | 20 | 13 | 0.65 |
| 0.24 | DA | 256 | Raw | 256 | 20 | 15 | 0.75 |
| 0.24 | DA | 512 | Raw | 512 | 20 | 16 | 0.8 |
| 0.24 | DA | 1024 | Raw | 1024 | 20 | 16 | 0.8 |
| 0.24 | DA | 2048 | Raw | 2048 | 20 | 17 | 0.85 |
| 0.24 | DA | 4096 | Raw | 4096 | 20 | 16 | 0.8 |
| 0.24 | DA | 8192 | Raw | 8192 | 20 | 16 | 0.8 |
| 0.24 | MSE | 256 | Decision-ZNE | 768 | 20 | 15 | 0.75 |
| 0.24 | MSE | 512 | Decision-ZNE | 1536 | 20 | 16 | 0.8 |
| 0.24 | MSE | 1024 | Decision-ZNE | 3072 | 20 | 16 | 0.8 |
| 0.24 | MSE | 2048 | Accuracy-ZNE | 6144 | 20 | 17 | 0.85 |
| 0.24 | MSE | 4096 | Decision-ZNE | 12288 | 20 | 16 | 0.8 |
| 0.24 | MSE | 8192 | Accuracy-ZNE | 24576 | 20 | 16 | 0.8 |
| 0.32 | DA | 256 | Raw | 256 | 20 | 16 | 0.8 |
| 0.32 | DA | 512 | Raw | 512 | 20 | 16 | 0.8 |
| 0.32 | DA | 1024 | Raw | 1024 | 20 | 16 | 0.8 |
| 0.32 | DA | 2048 | Raw | 2048 | 20 | 16 | 0.8 |
| 0.32 | DA | 4096 | Raw | 4096 | 20 | 16 | 0.8 |
| 0.32 | DA | 8192 | Raw | 8192 | 20 | 16 | 0.8 |
| 0.32 | MSE | 256 | Decision-ZNE | 768 | 20 | 14 | 0.7 |
| 0.32 | MSE | 512 | Decision-ZNE | 1536 | 20 | 15 | 0.75 |
| 0.32 | MSE | 1024 | Decision-ZNE | 3072 | 20 | 16 | 0.8 |
| 0.32 | MSE | 2048 | Accuracy-ZNE | 6144 | 20 | 16 | 0.8 |
| 0.32 | MSE | 4096 | Decision-ZNE | 12288 | 20 | 16 | 0.8 |
| 0.32 | MSE | 8192 | Accuracy-ZNE | 24576 | 20 | 16 | 0.8 |

## B(0.80) Matched Cost By Radius

| radius | selector | reaches_0.80 | B_nominal | shots_total_per_candidate | selected_method |
|---:|---|---|---|---|---|
| 0.12 | DA | False | not_reached | not_reached | not_reached |
| 0.12 | MSE | False | not_reached | not_reached | not_reached |
| 0.16 | DA | False | not_reached | not_reached | not_reached |
| 0.16 | MSE | False | not_reached | not_reached | not_reached |
| 0.24 | DA | True | 512 | 512 | Raw |
| 0.24 | MSE | True | 512 | 1536 | Decision-ZNE |
| 0.32 | DA | True | 256 | 256 | Raw |
| 0.32 | MSE | True | 1024 | 3072 | Decision-ZNE |

## Shot Savings Ratio

- radius_0.12_ratio_MSE_over_DA: not_computed
- radius_0.16_ratio_MSE_over_DA: not_computed
- radius_0.24_ratio_MSE_over_DA: 3
- radius_0.32_ratio_MSE_over_DA: 12

## Cost

- aer_runs: 960
- circuits: 4800
- shots_at_B_max: 39321600
- wall_seconds: 1715.11
