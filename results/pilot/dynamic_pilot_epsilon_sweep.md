# Dynamic Pilot Epsilon Sweep

Diagnostic final epsilon recalibration probe only: not canonical, not part of verify/reference, and not frozen.

## Metric Fidelity Justification

Section 10.2 step 5 asks to record whether the decision was correct, and Section 10.4 defines the studied decision as choosing between candidates with noisy estimated values. Therefore the primary success metric is decision-quality within the shared candidate trajectory. Global-opt success remains a secondary diagnostic because it is dominated by the search geometry shared by DA and MSE. This metric change is set before inspecting DA-vs-MSE under the new metric and is intended to be frozen pre-hash.

## Setup

- profile: epsilon_sweep
- instances: ['P001']
- trajectories: 30
- max_rounds: 4
- candidates_per_round: 5
- budget_grid: [256, 512, 1024, 2048, 4096, 8192]
- B_max: 8192
- candidate_radius: 0.24
- epsilon_quantile_grid: [0.1, 0.05, 0.02, 0.01]
- rescore_only: epsilon changes success labels only; Aer trajectories were simulated once.
- selector_primary: method-only argmin; no decision_score_z.
- safeguards: same candidates, initial points, budget grid, stopping rule, and Aer shot memory for DA/MSE.

## Stopping Rule

- This is the final epsilon iteration.
- If an epsilon de-saturates the curve and crosses 0.80, that is the dynamic full regime.
- If none satisfies the rule, Claim 2 dynamic is reported as cost-based and epsilon is not tuned further.

## Neutral Epsilon Selection Rule

- choose the largest epsilon_quantile with MSE P_success@256 <= 0.6.
- require MSE to cross P_success >= 0.80 at some budget.
- require MSE rise = P_success@8192 - P_success@256 >= 0.2.
- this rule uses only the baseline MSE, not the DA-vs-MSE margin.

## Epsilon Eligibility Table

| epsilon_quantile | P_success_MSE@256 | P_success_MSE@8192 | rise_MSE | crosses_0.80 | eligible |
|---:|---:|---:|---:|---|---|
| 0.10 | 0.833333 | 1 | 0.166667 | True | False |
| 0.05 | 0.733333 | 1 | 0.266667 | True | False |
| 0.02 | 0.666667 | 0.933333 | 0.266667 | True | False |
| 0.01 | 0.6 | 0.866667 | 0.266667 | True | True |

- chosen_epsilon_quantile: 0.01
- if_none: not_applicable

## Decision-Quality Primary Curves

| epsilon_quantile | selector | budget | selected_method | shots_per_candidate | trajectories | successes | P_success |
|---:|---|---:|---|---:|---:|---:|---:|
| 0.01 | DA | 256 | Raw | 256 | 30 | 21 | 0.7 |
| 0.01 | DA | 512 | Raw | 512 | 30 | 23 | 0.766667 |
| 0.01 | DA | 1024 | Raw | 1024 | 30 | 24 | 0.8 |
| 0.01 | DA | 2048 | Raw | 2048 | 30 | 26 | 0.866667 |
| 0.01 | DA | 4096 | Raw | 4096 | 30 | 24 | 0.8 |
| 0.01 | DA | 8192 | Raw | 8192 | 30 | 27 | 0.9 |
| 0.01 | MSE | 256 | Decision-ZNE | 768 | 30 | 18 | 0.6 |
| 0.01 | MSE | 512 | Decision-ZNE | 1536 | 30 | 24 | 0.8 |
| 0.01 | MSE | 1024 | Decision-ZNE | 3072 | 30 | 24 | 0.8 |
| 0.01 | MSE | 2048 | Accuracy-ZNE | 6144 | 30 | 28 | 0.933333 |
| 0.01 | MSE | 4096 | Decision-ZNE | 12288 | 30 | 25 | 0.833333 |
| 0.01 | MSE | 8192 | Accuracy-ZNE | 24576 | 30 | 26 | 0.866667 |
| 0.02 | DA | 256 | Raw | 256 | 30 | 23 | 0.766667 |
| 0.02 | DA | 512 | Raw | 512 | 30 | 26 | 0.866667 |
| 0.02 | DA | 1024 | Raw | 1024 | 30 | 26 | 0.866667 |
| 0.02 | DA | 2048 | Raw | 2048 | 30 | 28 | 0.933333 |
| 0.02 | DA | 4096 | Raw | 4096 | 30 | 26 | 0.866667 |
| 0.02 | DA | 8192 | Raw | 8192 | 30 | 29 | 0.966667 |
| 0.02 | MSE | 256 | Decision-ZNE | 768 | 30 | 20 | 0.666667 |
| 0.02 | MSE | 512 | Decision-ZNE | 1536 | 30 | 25 | 0.833333 |
| 0.02 | MSE | 1024 | Decision-ZNE | 3072 | 30 | 25 | 0.833333 |
| 0.02 | MSE | 2048 | Accuracy-ZNE | 6144 | 30 | 29 | 0.966667 |
| 0.02 | MSE | 4096 | Decision-ZNE | 12288 | 30 | 25 | 0.833333 |
| 0.02 | MSE | 8192 | Accuracy-ZNE | 24576 | 30 | 28 | 0.933333 |
| 0.05 | DA | 256 | Raw | 256 | 30 | 25 | 0.833333 |
| 0.05 | DA | 512 | Raw | 512 | 30 | 28 | 0.933333 |
| 0.05 | DA | 1024 | Raw | 1024 | 30 | 28 | 0.933333 |
| 0.05 | DA | 2048 | Raw | 2048 | 30 | 30 | 1 |
| 0.05 | DA | 4096 | Raw | 4096 | 30 | 30 | 1 |
| 0.05 | DA | 8192 | Raw | 8192 | 30 | 30 | 1 |
| 0.05 | MSE | 256 | Decision-ZNE | 768 | 30 | 22 | 0.733333 |
| 0.05 | MSE | 512 | Decision-ZNE | 1536 | 30 | 27 | 0.9 |
| 0.05 | MSE | 1024 | Decision-ZNE | 3072 | 30 | 28 | 0.933333 |
| 0.05 | MSE | 2048 | Accuracy-ZNE | 6144 | 30 | 30 | 1 |
| 0.05 | MSE | 4096 | Decision-ZNE | 12288 | 30 | 28 | 0.933333 |
| 0.05 | MSE | 8192 | Accuracy-ZNE | 24576 | 30 | 30 | 1 |
| 0.10 | DA | 256 | Raw | 256 | 30 | 28 | 0.933333 |
| 0.10 | DA | 512 | Raw | 512 | 30 | 30 | 1 |
| 0.10 | DA | 1024 | Raw | 1024 | 30 | 30 | 1 |
| 0.10 | DA | 2048 | Raw | 2048 | 30 | 30 | 1 |
| 0.10 | DA | 4096 | Raw | 4096 | 30 | 30 | 1 |
| 0.10 | DA | 8192 | Raw | 8192 | 30 | 30 | 1 |
| 0.10 | MSE | 256 | Decision-ZNE | 768 | 30 | 25 | 0.833333 |
| 0.10 | MSE | 512 | Decision-ZNE | 1536 | 30 | 30 | 1 |
| 0.10 | MSE | 1024 | Decision-ZNE | 3072 | 30 | 30 | 1 |
| 0.10 | MSE | 2048 | Accuracy-ZNE | 6144 | 30 | 30 | 1 |
| 0.10 | MSE | 4096 | Decision-ZNE | 12288 | 30 | 29 | 0.966667 |
| 0.10 | MSE | 8192 | Accuracy-ZNE | 24576 | 30 | 30 | 1 |

## Global-Opt Secondary Curves

| epsilon_quantile | selector | budget | selected_method | shots_per_candidate | trajectories | successes | P_success |
|---:|---|---:|---|---:|---:|---:|---:|
| 0.01 | DA | 256 | Raw | 256 | 30 | 6 | 0.2 |
| 0.01 | DA | 512 | Raw | 512 | 30 | 7 | 0.233333 |
| 0.01 | DA | 1024 | Raw | 1024 | 30 | 7 | 0.233333 |
| 0.01 | DA | 2048 | Raw | 2048 | 30 | 8 | 0.266667 |
| 0.01 | DA | 4096 | Raw | 4096 | 30 | 7 | 0.233333 |
| 0.01 | DA | 8192 | Raw | 8192 | 30 | 8 | 0.266667 |
| 0.01 | MSE | 256 | Decision-ZNE | 768 | 30 | 4 | 0.133333 |
| 0.01 | MSE | 512 | Decision-ZNE | 1536 | 30 | 6 | 0.2 |
| 0.01 | MSE | 1024 | Decision-ZNE | 3072 | 30 | 6 | 0.2 |
| 0.01 | MSE | 2048 | Accuracy-ZNE | 6144 | 30 | 7 | 0.233333 |
| 0.01 | MSE | 4096 | Decision-ZNE | 12288 | 30 | 6 | 0.2 |
| 0.01 | MSE | 8192 | Accuracy-ZNE | 24576 | 30 | 7 | 0.233333 |
| 0.02 | DA | 256 | Raw | 256 | 30 | 6 | 0.2 |
| 0.02 | DA | 512 | Raw | 512 | 30 | 8 | 0.266667 |
| 0.02 | DA | 1024 | Raw | 1024 | 30 | 8 | 0.266667 |
| 0.02 | DA | 2048 | Raw | 2048 | 30 | 9 | 0.3 |
| 0.02 | DA | 4096 | Raw | 4096 | 30 | 8 | 0.266667 |
| 0.02 | DA | 8192 | Raw | 8192 | 30 | 9 | 0.3 |
| 0.02 | MSE | 256 | Decision-ZNE | 768 | 30 | 4 | 0.133333 |
| 0.02 | MSE | 512 | Decision-ZNE | 1536 | 30 | 7 | 0.233333 |
| 0.02 | MSE | 1024 | Decision-ZNE | 3072 | 30 | 7 | 0.233333 |
| 0.02 | MSE | 2048 | Accuracy-ZNE | 6144 | 30 | 8 | 0.266667 |
| 0.02 | MSE | 4096 | Decision-ZNE | 12288 | 30 | 7 | 0.233333 |
| 0.02 | MSE | 8192 | Accuracy-ZNE | 24576 | 30 | 8 | 0.266667 |
| 0.05 | DA | 256 | Raw | 256 | 30 | 9 | 0.3 |
| 0.05 | DA | 512 | Raw | 512 | 30 | 10 | 0.333333 |
| 0.05 | DA | 1024 | Raw | 1024 | 30 | 10 | 0.333333 |
| 0.05 | DA | 2048 | Raw | 2048 | 30 | 10 | 0.333333 |
| 0.05 | DA | 4096 | Raw | 4096 | 30 | 11 | 0.366667 |
| 0.05 | DA | 8192 | Raw | 8192 | 30 | 11 | 0.366667 |
| 0.05 | MSE | 256 | Decision-ZNE | 768 | 30 | 7 | 0.233333 |
| 0.05 | MSE | 512 | Decision-ZNE | 1536 | 30 | 10 | 0.333333 |
| 0.05 | MSE | 1024 | Decision-ZNE | 3072 | 30 | 10 | 0.333333 |
| 0.05 | MSE | 2048 | Accuracy-ZNE | 6144 | 30 | 11 | 0.366667 |
| 0.05 | MSE | 4096 | Decision-ZNE | 12288 | 30 | 11 | 0.366667 |
| 0.05 | MSE | 8192 | Accuracy-ZNE | 24576 | 30 | 11 | 0.366667 |
| 0.10 | DA | 256 | Raw | 256 | 30 | 16 | 0.533333 |
| 0.10 | DA | 512 | Raw | 512 | 30 | 17 | 0.566667 |
| 0.10 | DA | 1024 | Raw | 1024 | 30 | 17 | 0.566667 |
| 0.10 | DA | 2048 | Raw | 2048 | 30 | 18 | 0.6 |
| 0.10 | DA | 4096 | Raw | 4096 | 30 | 18 | 0.6 |
| 0.10 | DA | 8192 | Raw | 8192 | 30 | 19 | 0.633333 |
| 0.10 | MSE | 256 | Decision-ZNE | 768 | 30 | 14 | 0.466667 |
| 0.10 | MSE | 512 | Decision-ZNE | 1536 | 30 | 17 | 0.566667 |
| 0.10 | MSE | 1024 | Decision-ZNE | 3072 | 30 | 18 | 0.6 |
| 0.10 | MSE | 2048 | Accuracy-ZNE | 6144 | 30 | 19 | 0.633333 |
| 0.10 | MSE | 4096 | Decision-ZNE | 12288 | 30 | 18 | 0.6 |
| 0.10 | MSE | 8192 | Accuracy-ZNE | 24576 | 30 | 19 | 0.633333 |

## Chosen Epsilon Decision-Quality Primary (0.01)

| selector | reaches_0.80 | B_nominal | shots_total_per_candidate | selected_method |
|---|---|---|---|---|
| DA | True | 1024 | 1024 | Raw |
| MSE | True | 512 | 1536 | Decision-ZNE |
- decision_quality_shot_savings_ratio_MSE_over_DA: 1.5
- decision_quality_advantage_type: cost_only

## Chosen Epsilon Global-Opt Secondary (0.01)

| selector | reaches_0.80 | B_nominal | shots_total_per_candidate | selected_method |
|---|---|---|---|---|
| DA | False | not_reached | not_reached | not_reached |
| MSE | False | not_reached | not_reached | not_reached |
- global_opt_shot_savings_ratio_MSE_over_DA: not_computed
- global_opt_advantage_type: no_cost_advantage

## Cost

- aer_runs: 360
- circuits: 1800
- shots_at_B_max: 14745600
- wall_seconds: 598.5
