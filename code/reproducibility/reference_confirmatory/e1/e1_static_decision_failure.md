# E1 Static Decision Failure

Confirmatory smoke/full runner for Claim 1. Reuses pilot_power_report primitives; outputs are under results/confirmatory.

## Configuration

- profile: confirmatory_full
- B_star_operational: 512
- alpha: 0.05
- selector_rules: daqem.selectors.mse_selector / daqem.selectors.da_selector
- covariance_estimator: Ledoit-Wolf via pilot_power_report.method_gri_by_method

## Aggregate at B*

| instances | paired_n | both_fail | both_ok | b_DA_better | c_DA_worse | failure_rate_MSE | failure_rate_DA | observed_rel_reduction | mcnemar_one_sided_reject |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 48 | 1920 | 725 | 967 | 165 | 63 | 0.463542 | 0.410417 | 0.114607 | True |

## Instance Rows at B*

| cell | epsilon_tercile | gap_tercile | MSE_selected_method | DA_selected_method | failure_rate_MSE | failure_rate_DA | b_DA_better | c_DA_worse |
|---|---|---|---|---|---:|---:|---:|---:|
| C001 | easy | easy | Decision-ZNE | Raw | 0.025 | 0 | 1 | 0 |
| C002 | medium | medium | Accuracy-ZNE | Raw | 0.625 | 0.625 | 5 | 5 |
| C003 | easy | easy | Decision-ZNE | Raw | 0.275 | 0.225 | 4 | 2 |
| C004 | easy | easy | Accuracy-ZNE | Raw | 0.325 | 0.1 | 9 | 0 |
| C005 | medium | medium | Decision-ZNE | Raw | 0.55 | 0.375 | 7 | 0 |
| C006 | hard | hard | Decision-ZNE | Raw | 0.7 | 0.6 | 5 | 1 |
| C007 | medium | medium | Decision-ZNE | Raw | 0.425 | 0.375 | 4 | 2 |
| C008 | medium | medium | Decision-ZNE | Raw | 0.65 | 0.675 | 3 | 4 |
| C009 | easy | easy | Decision-ZNE | Raw | 0.175 | 0.15 | 2 | 1 |
| C010 | easy | easy | Decision-ZNE | Raw | 0.325 | 0.225 | 4 | 0 |
| C011 | easy | easy | Accuracy-ZNE | Raw | 0 | 0 | 0 | 0 |
| C012 | medium | medium | Decision-ZNE | Raw | 0.5 | 0.45 | 4 | 2 |
| C013 | medium | medium | Decision-ZNE | Raw | 0.425 | 0.4 | 4 | 3 |
| C014 | hard | hard | Accuracy-ZNE | Raw | 0.425 | 0.45 | 2 | 3 |
| C015 | easy | easy | Accuracy-ZNE | Raw | 0.25 | 0.075 | 8 | 1 |
| C016 | easy | easy | Decision-ZNE | Raw | 0.225 | 0.2 | 3 | 2 |
| C017 | hard | hard | Accuracy-ZNE | Raw | 0.7 | 0.75 | 0 | 2 |
| C018 | hard | hard | Decision-ZNE | Raw | 0.525 | 0.475 | 4 | 2 |
| C019 | easy | easy | Decision-ZNE | Raw | 0.175 | 0.125 | 3 | 1 |
| C020 | medium | medium | Decision-ZNE | Raw | 0.7 | 0.6 | 4 | 0 |
| C021 | medium | medium | Accuracy-ZNE | Raw | 0.525 | 0.325 | 9 | 1 |
| C022 | easy | easy | Decision-ZNE | Raw | 0.25 | 0.075 | 7 | 0 |
| C023 | easy | easy | Decision-ZNE | Raw | 0.05 | 0.05 | 0 | 0 |
| C024 | medium | medium | Accuracy-ZNE | Raw | 0.525 | 0.425 | 4 | 0 |
| C025 | easy | easy | Decision-ZNE | Raw | 0.275 | 0.175 | 4 | 0 |
| C026 | hard | hard | Accuracy-ZNE | Decision-ZNE | 0.5 | 0.525 | 0 | 1 |
| C027 | hard | hard | Decision-ZNE | Accuracy-ZNE | 0.65 | 0.65 | 0 | 0 |
| C028 | easy | easy | Accuracy-ZNE | Raw | 0.675 | 0.65 | 5 | 4 |
| C029 | medium | medium | Decision-ZNE | Raw | 0.275 | 0.2 | 3 | 0 |
| C030 | medium | medium | Decision-ZNE | Accuracy-ZNE | 0.7 | 0.6 | 4 | 0 |
| C031 | hard | hard | Decision-ZNE | Raw | 0.575 | 0.525 | 3 | 1 |
| C032 | hard | hard | Decision-ZNE | Raw | 0.45 | 0.425 | 5 | 4 |
| C033 | hard | hard | Decision-ZNE | Raw | 0.4 | 0.35 | 4 | 2 |
| C034 | hard | hard | Decision-ZNE | Raw | 0.75 | 0.775 | 2 | 3 |
| C035 | easy | easy | Decision-ZNE | Raw | 0.2 | 0.15 | 3 | 1 |
| C036 | easy | easy | Accuracy-ZNE | Raw | 0.375 | 0.275 | 5 | 1 |
| C037 | medium | medium | Decision-ZNE | Decision-ZNE | 0.4 | 0.4 | 0 | 0 |
| C038 | medium | medium | Accuracy-ZNE | Accuracy-ZNE | 0.6 | 0.6 | 0 | 0 |
| C039 | medium | medium | Accuracy-ZNE | Raw | 0.575 | 0.5 | 7 | 4 |
| C040 | hard | hard | Accuracy-ZNE | Raw | 0.6 | 0.45 | 8 | 2 |
| C041 | hard | hard | Accuracy-ZNE | Raw | 0.525 | 0.525 | 2 | 2 |
| C042 | hard | hard | Accuracy-ZNE | Decision-ZNE | 0.825 | 0.825 | 0 | 0 |
| C043 | medium | medium | Decision-ZNE | Decision-ZNE | 0.525 | 0.525 | 0 | 0 |
| C044 | hard | hard | Decision-ZNE | Decision-ZNE | 0.775 | 0.775 | 0 | 0 |
| C045 | hard | hard | Decision-ZNE | Raw | 0.7 | 0.675 | 4 | 3 |
| C046 | easy | easy | Decision-ZNE | Raw | 0.175 | 0.15 | 3 | 2 |
| C047 | hard | hard | Decision-ZNE | Accuracy-ZNE | 0.825 | 0.825 | 1 | 1 |
| C048 | medium | medium | Decision-ZNE | Raw | 0.55 | 0.4 | 6 | 0 |

## Stratified Report

| stratifier | stratum | instances | paired_n | failure_rate_MSE | failure_rate_DA | b_DA_better | c_DA_worse |
|---|---|---:|---:|---:|---:|---:|---:|
| epsilon_opt_tercile | easy | 16 | 640 | 0.235937 | 0.164062 | 61 | 15 |
| epsilon_opt_tercile | hard | 16 | 640 | 0.620313 | 0.6 | 40 | 27 |
| epsilon_opt_tercile | medium | 16 | 640 | 0.534375 | 0.467187 | 64 | 21 |
| decision_gap_tercile | easy | 16 | 640 | 0.235937 | 0.164062 | 61 | 15 |
| decision_gap_tercile | hard | 16 | 640 | 0.620313 | 0.6 | 40 | 27 |
| decision_gap_tercile | medium | 16 | 640 | 0.534375 | 0.467187 | 64 | 21 |
