# Gate 0 Regime Probe

Diagnostic only: not canonical, not part of verify/reference.

- profile: regime_probe; instances: ['P001', 'P002']; candidate_count: 25; replicates: 40; budget_grid: [256, 512, 1024]

| instance | budget | Raw_failure_rate_emp | Raw_gri_full | max_delta_full_minus_diag | selector_changed_any |
|---|---:|---:|---:|---:|---|
| P001 | 256 | 0.425000 | 0.508375 | -1.934989e-01 | False |
| P001 | 512 | 0.250000 | 0.313762 | -1.110052e-01 | False |
| P001 | 1024 | 0.200000 | 0.217199 | -4.142684e-02 | False |
| P002 | 256 | 0.500000 | 0.424066 | -2.711277e-01 | False |
| P002 | 512 | 0.150000 | 0.136772 | -9.474858e-02 | False |
| P002 | 1024 | 0.000000 | 0.033019 | -3.052112e-02 | False |

- regime_ok: True
- adjustment_if_false: none
