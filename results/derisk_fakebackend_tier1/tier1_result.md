# FakeBackend tier-chico result

**Scope:** calibrated device-noise stress test, NOT hardware evidence.

## Pre-registration

- source: `DERISK_FAKEBACKEND_TIER1_v1.md`
- sealed hash: `AA029CA5D491E9140CD0874611A4B621847E3C4E7598EF5D7F2BDE4E17C875CE`
- pool: C001-C048 complete; no Kolkata in-band filtering

## Ordering gate
- C001: PASS, abs_error=3.106e-06, tol=5.0e-05
- C002: PASS, abs_error=1.920e-06, tol=5.0e-05
- C003: PASS, abs_error=5.172e-07, tol=5.0e-05
- C004: PASS, abs_error=3.302e-07, tol=5.0e-05
- C005: PASS, abs_error=9.212e-07, tol=5.0e-05
- C006: PASS, abs_error=1.787e-06, tol=5.0e-05
- C007: PASS, abs_error=1.904e-06, tol=5.0e-05
- C008: PASS, abs_error=1.320e-07, tol=5.0e-05
- C009: PASS, abs_error=9.014e-07, tol=5.0e-05
- C010: PASS, abs_error=5.764e-07, tol=5.0e-05
- C011: PASS, abs_error=1.910e-06, tol=5.0e-05
- C012: PASS, abs_error=1.841e-06, tol=5.0e-05
- C013: PASS, abs_error=1.644e-07, tol=5.0e-05
- C014: PASS, abs_error=1.769e-07, tol=5.0e-05
- C015: PASS, abs_error=5.441e-07, tol=5.0e-05
- C016: PASS, abs_error=2.681e-06, tol=5.0e-05
- C017: PASS, abs_error=1.155e-06, tol=5.0e-05
- C018: PASS, abs_error=2.435e-06, tol=5.0e-05
- C019: PASS, abs_error=2.379e-06, tol=5.0e-05
- C020: PASS, abs_error=6.439e-07, tol=5.0e-05
- C021: PASS, abs_error=1.635e-06, tol=5.0e-05
- C022: PASS, abs_error=1.029e-06, tol=5.0e-05
- C023: PASS, abs_error=1.893e-06, tol=5.0e-05
- C024: PASS, abs_error=1.400e-06, tol=5.0e-05
- C025: PASS, abs_error=1.066e-06, tol=5.0e-05
- C026: PASS, abs_error=4.917e-07, tol=5.0e-05
- C027: PASS, abs_error=2.208e-06, tol=5.0e-05
- C028: PASS, abs_error=2.077e-07, tol=5.0e-05
- C029: PASS, abs_error=3.276e-06, tol=5.0e-05
- C030: PASS, abs_error=1.067e-06, tol=5.0e-05
- C031: PASS, abs_error=6.284e-07, tol=5.0e-05
- C032: PASS, abs_error=2.334e-06, tol=5.0e-05
- C033: PASS, abs_error=5.122e-07, tol=5.0e-05
- C034: PASS, abs_error=4.325e-07, tol=5.0e-05
- C035: PASS, abs_error=2.376e-06, tol=5.0e-05
- C036: PASS, abs_error=1.519e-06, tol=5.0e-05
- C037: PASS, abs_error=2.222e-06, tol=5.0e-05
- C038: PASS, abs_error=2.362e-06, tol=5.0e-05
- C039: PASS, abs_error=1.156e-07, tol=5.0e-05
- C040: PASS, abs_error=1.360e-06, tol=5.0e-05
- C041: PASS, abs_error=7.832e-07, tol=5.0e-05
- C042: PASS, abs_error=3.127e-07, tol=5.0e-05
- C043: PASS, abs_error=2.532e-06, tol=5.0e-05
- C044: PASS, abs_error=7.508e-07, tol=5.0e-05
- C045: PASS, abs_error=2.990e-06, tol=5.0e-05
- C046: PASS, abs_error=1.660e-06, tol=5.0e-05
- C047: PASS, abs_error=1.687e-07, tol=5.0e-05
- C048: PASS, abs_error=1.210e-06, tol=5.0e-05

## Determinism
- C001 B=512: raw=True, primitive=True, rem=True

## Primary endpoint

Pooled over 48 C-ids at B*=512: failure_DA=0.451562, failure_MSE=0.489583, rel_reduction=0.0776596, CI=[0.038207525853621443, 0.11579183973920815], b=225, c=152, paired_n=1920, z=3.77262, p=8.07695e-05, reject=True.
- practical_threshold_0.15_pass: False

## Decision

- decision: CONFIRMED
- framing: primary pooled benefit significant at alpha=0.05

## Secondary endpoints

- multiplicity: Holm correction applied to secondary inferential paired tests; D1 and Raw+REM frequency are reported as pre-specified diagnostic frequencies.

| endpoint | instances | rows | paired_n | failure_MSE | failure_DA | rel_reduction | p | Holm p | Holm reject |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| in_band_uniform_frozen | 41 | 41 | 1640 | 0.491463 | 0.44878 | 0.0868486 | 8.24593e-05 | 0.000329837 | True |
| epsilon_tercile_easy | 16 | 16 | 640 | 0.229687 | 0.207813 | 0.0952381 | 0.0763535 | 0.0763535 | False |
| epsilon_tercile_medium | 16 | 16 | 640 | 0.565625 | 0.532813 | 0.058011 | 0.0268558 | 0.0537115 | False |
| epsilon_tercile_hard | 16 | 16 | 640 | 0.673438 | 0.614062 | 0.0881671 | 0.0013313 | 0.00399391 | True |
| auc_budget_grid | 48 | 288 | 11520 | 0.390191 | 0.35816 | 0.0820912 | 0 | 0 | True |

## D1 and Raw+REM frequency

- D1 full-Sigma vs diagonal flips: 59/288 (0.204861).
- DA selects Raw+REM: 85/288 (0.295139).

## Panel at B*

| cell | epsilon_opt_tercile | uniform_in_band_B_star | DA_selected_method | MSE_selected_method | failure_rate_DA | failure_rate_MSE | failure_rate_Raw | observed_rel_reduction | b_DA_better | c_DA_worse |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C001 | easy | False | CDR | CDR | 0.125 | 0.125 | 0.125 | 0 | 0 | 0 |
| C002 | medium | True | Raw+REM | CDR | 0.7 | 0.75 | 0.75 | 0.0666667 | 8 | 6 |
| C003 | easy | True | Raw+REM | CDR | 0.3 | 0.3 | 0.3 | 0 | 8 | 8 |
| C004 | easy | True | Raw | CDR | 0.2 | 0.2 | 0.2 | 0 | 0 | 0 |
| C005 | medium | True | CDR | CDR | 0.375 | 0.375 | 0.375 | 0 | 0 | 0 |
| C006 | hard | True | Raw+REM | CDR | 0.525 | 0.65 | 0.65 | 0.192308 | 11 | 6 |
| C007 | medium | True | CDR | CDR | 0.425 | 0.425 | 0.425 | 0 | 0 | 0 |
| C008 | medium | True | Raw+REM | CDR | 0.55 | 0.75 | 0.75 | 0.266667 | 12 | 4 |
| C009 | easy | True | Raw+REM | CDR | 0.225 | 0.3 | 0.3 | 0.25 | 9 | 6 |
| C010 | easy | True | Raw | CDR | 0.3 | 0.3 | 0.3 | 0 | 0 | 0 |
| C011 | easy | False | Raw+REM | CDR | 0 | 0 | 0 | 0 | 0 | 0 |
| C012 | medium | True | Raw | CDR | 0.525 | 0.525 | 0.525 | 0 | 0 | 0 |
| C013 | medium | True | Raw+REM | CDR | 0.45 | 0.55 | 0.55 | 0.181818 | 12 | 8 |
| C014 | hard | True | Raw+REM | CDR | 0.5 | 0.5 | 0.5 | 0 | 12 | 12 |
| C015 | easy | True | Raw+REM | CDR | 0.1 | 0.2 | 0.2 | 0.5 | 7 | 3 |
| C016 | easy | True | Raw+REM | CDR | 0.175 | 0.275 | 0.275 | 0.363636 | 9 | 5 |
| C017 | hard | True | CDR | CDR | 0.725 | 0.725 | 0.725 | 0 | 0 | 0 |
| C018 | hard | True | Raw+REM | CDR | 0.75 | 0.875 | 0.875 | 0.142857 | 8 | 3 |
| C019 | easy | True | Raw+REM | CDR | 0.125 | 0.3 | 0.3 | 0.583333 | 11 | 4 |
| C020 | medium | True | Raw | CDR | 0.725 | 0.725 | 0.725 | 0 | 0 | 0 |
| C021 | medium | True | Raw+REM | CDR | 0.275 | 0.3 | 0.3 | 0.0833333 | 10 | 9 |
| C022 | easy | True | Raw | CDR | 0.2 | 0.2 | 0.2 | 0 | 0 | 0 |
| C023 | easy | False | Raw+REM | CDR | 0.075 | 0.025 | 0.025 | -2 | 1 | 3 |
| C024 | medium | True | CDR | CDR | 0.55 | 0.55 | 0.55 | 0 | 0 | 0 |
| C025 | easy | True | Raw | CDR | 0.225 | 0.225 | 0.225 | 0 | 0 | 0 |
| C026 | hard | True | Raw | CDR | 0.5 | 0.5 | 0.5 | 0 | 0 | 0 |
| C027 | hard | True | Raw+REM | CDR | 0.5 | 0.625 | 0.625 | 0.2 | 10 | 5 |
| C028 | easy | True | CDR | CDR | 0.55 | 0.55 | 0.55 | 0 | 0 | 0 |
| C029 | medium | True | Raw+REM | CDR | 0.35 | 0.3 | 0.3 | -0.166667 | 9 | 11 |
| C030 | medium | True | CDR | CDR | 0.55 | 0.55 | 0.55 | 0 | 0 | 0 |
| C031 | hard | True | Raw+REM | CDR | 0.55 | 0.725 | 0.725 | 0.241379 | 13 | 6 |
| C032 | hard | True | Raw | CDR | 0.625 | 0.625 | 0.625 | 0 | 0 | 0 |
| C033 | hard | True | Raw+REM | CDR | 0.3 | 0.35 | 0.35 | 0.142857 | 10 | 8 |
| C034 | hard | False | CDR | CDR | 0.8 | 0.8 | 0.8 | 0 | 0 | 0 |
| C035 | easy | True | CDR | CDR | 0.175 | 0.175 | 0.175 | 0 | 0 | 0 |
| C036 | easy | True | Raw+REM | CDR | 0.375 | 0.325 | 0.325 | -0.153846 | 10 | 12 |
| C037 | medium | True | CDR | CDR | 0.475 | 0.475 | 0.475 | 0 | 0 | 0 |
| C038 | medium | True | Raw+REM | CDR | 0.725 | 0.9 | 0.9 | 0.194444 | 10 | 3 |
| C039 | medium | True | CDR | CDR | 0.475 | 0.475 | 0.475 | 0 | 0 | 0 |
| C040 | hard | True | Raw | CDR | 0.525 | 0.525 | 0.525 | 0 | 0 | 0 |
| C041 | hard | True | Raw+REM | CDR | 0.625 | 0.675 | 0.675 | 0.0740741 | 9 | 7 |
| C042 | hard | False | Decision-ZNE | CDR | 0.7 | 0.775 | 0.775 | 0.0967742 | 9 | 6 |
| C043 | medium | True | Decision-ZNE | CDR | 0.65 | 0.675 | 0.675 | 0.037037 | 9 | 8 |
| C044 | hard | False | Raw+REM | CDR | 0.85 | 0.9 | 0.9 | 0.0555556 | 6 | 4 |
| C045 | hard | True | Decision-ZNE | CDR | 0.625 | 0.8 | 0.8 | 0.21875 | 12 | 5 |
| C046 | easy | True | CDR | CDR | 0.175 | 0.175 | 0.175 | 0 | 0 | 0 |
| C047 | hard | False | CDR | CDR | 0.725 | 0.725 | 0.725 | 0 | 0 | 0 |
| C048 | medium | True | Raw | CDR | 0.725 | 0.725 | 0.725 | 0 | 0 | 0 |

## Saturation check

- Raw failure mean at B*: 0.489583; rows >=0.95: 0/48.

## Outputs

- `results/derisk_fakebackend_tier1/tier1_result.json`
- `results/derisk_fakebackend_tier1/per_instance_budget_table.csv`
- `results/derisk_fakebackend_tier1/mapping_manifest.csv`

Duration seconds: 35182.9
