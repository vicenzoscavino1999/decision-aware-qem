# FakeBackend de-risk result

**Scope:** calibrated fake-backend stress test, NOT hardware.

## Ordering gate
- P004: PASS, abs_error=2.264e-06, tol=5.0e-05
- P001: PASS, abs_error=7.268e-07, tol=5.0e-05
- P002: PASS, abs_error=3.937e-07, tol=5.0e-05

## Mappings
- P004: virtual_to_physical=[16, 22, 25, 19, 20, 24, 23, 14, 26, 13], final_measurement=[13, 20, 23, 22, 19, 24, 26, 14, 25, 16], depth=114, size=305, swap_count=0
- P001: virtual_to_physical=[14, 25, 26, 24, 16, 23, 19, 13, 20, 22], final_measurement=[13, 23, 19, 26, 20, 24, 22, 16, 14, 25], depth=98, size=308, swap_count=0
- P002: virtual_to_physical=[15, 10, 7, 12, 6, 14, 18, 13, 16, 4], final_measurement=[18, 7, 4, 6, 15, 16, 10, 13, 14, 12], depth=124, size=323, swap_count=0

## Budget accounting
- Raw: `C_eval=B`.
- Accuracy-ZNE / Decision-ZNE: three scales with `floor(B/3)` shots each.
- Raw+REM: matched-total split with `f_calib=0.2`; calibration is paid from `B`.
- CDR: shares Raw evaluation shots; non-amortized `C_train=24576` is reported separately, so no matched-cost CDR advantage is claimed.

## Primary endpoint
P004, B*=512: DA=Raw+REM failure=0.375; MSE=CDR failure=0.400; DA-MSE=-0.025; rel_reduction=0.063; b=11, c=10, n=40.

## Secondary endpoint
P004 budget-band mean failure: DA=0.296, MSE=0.317, Raw=0.317, DA-MSE=-0.021.

## D1 and qualitative gate
- Full-vs-diagonal selector changed in 3/18 rows.
- DA selected a non-Raw method in 15 rows.

## Signal
- SIGNAL_FOR_GO: YES
- Framing: signal under this backend/menu/budget regime.

## Panel
| cell | budget | DA_selected_method | MSE_selected_method | failure_rate_DA | failure_rate_MSE | failure_rate_Raw | observed_rel_reduction | selector_changed_full_vs_diagonal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P001 | 256 | CDR | CDR | 0.475 | 0.475 | 0.475 | 0 | True |
| P001 | 512 | Raw | CDR | 0.5 | 0.5 | 0.5 | 0 | True |
| P001 | 1024 | CDR | CDR | 0.275 | 0.275 | 0.275 | 0 | False |
| P001 | 2048 | Raw+REM | CDR | 0.15 | 0.25 | 0.25 | 0.4 | False |
| P001 | 4096 | CDR | CDR | 0.125 | 0.125 | 0.125 | 0 | False |
| P001 | 8192 | CDR | CDR | 0.05 | 0.05 | 0.05 | 0 | False |
| P002 | 256 | Raw+REM | CDR | 0.525 | 0.65 | 0.65 | 0.192308 | True |
| P002 | 512 | CDR | CDR | 0.2 | 0.2 | 0.2 | 0 | False |
| P002 | 1024 | CDR | CDR | 0.05 | 0.05 | 0.05 | 0 | False |
| P002 | 2048 | Raw+REM | CDR | 0 | 0 | 0 | 0 | False |
| P002 | 4096 | CDR | CDR | 0 | 0 | 0 | 0 | False |
| P002 | 8192 | CDR | CDR | 0 | 0 | 0 | 0 | False |
| P004 | 256 | Raw | CDR | 0.45 | 0.45 | 0.45 | 0 | False |
| P004 | 512 | Raw+REM | CDR | 0.375 | 0.4 | 0.4 | 0.0625 | False |
| P004 | 1024 | Raw+REM | CDR | 0.3 | 0.4 | 0.4 | 0.25 | False |
| P004 | 2048 | CDR | CDR | 0.25 | 0.25 | 0.25 | 0 | False |
| P004 | 4096 | CDR | CDR | 0.125 | 0.125 | 0.125 | 0 | False |
| P004 | 8192 | Raw | CDR | 0.275 | 0.275 | 0.275 | 0 | False |

Duration seconds: 244.3
