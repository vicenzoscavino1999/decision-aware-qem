# CDR P0 Decision-Invariance Note

Date: 2026-06-24

Scope: P0 CDR only. No confirmatory instances, no pipeline run, no re-freeze.

## Finding

The locked P0 CDR estimator applies one global affine correction per instance:

```text
F_CDR(x) = a * F_raw(x) + b
```

The P0 validity evidence has positive non-degenerate slopes:

```text
abs(a) range = [1.0682280305898002, 1.155378985696129]
```

For any decision gap against the reference candidate `x0`,

```text
gap_CDR(i) = F_CDR(x_i) - F_CDR(x0)
           = a * (F_raw(x_i) - F_raw(x0))
           = a * gap_raw(i).
```

The intercept cancels. With positive `a`, the candidate ordering and argmin decision are unchanged.

For Gaussian decision risk,

```text
mu_CDR = a * mu_raw
Sigma_CDR = a^2 * Sigma_raw
```

so the standardized decision quantities, including `mu_i^2 / Sigma_ii`, are unchanged. Therefore the GRI/risk selector sees global-affine CDR as decision-equivalent to Raw.

## Consequence

CDR P0 is validated as a value-estimation correction: it improves the target estimate in the P0 smoke and six non-confirmatory validity instances. But it is decision-flat under the decision-kernel framework because it is a single positive affine transformation applied uniformly to every candidate.

This is useful evidence for the paper: an estimator can improve value/MSE while leaving the decision kernel unchanged. It supports the thesis that MSE improvement is not sufficient for decision improvement.

## Stop Decision

The CDR arm is stopped after P0 as the PRXQ decision lever. It should not advance to P1/P2/P3 unless a separately preregistered non-affine or candidate-specific CDR variant is introduced.

Next arm: PEC.

This stop decision is based on algebraic invariance of the locked P0 model, not on confirmatory outcomes and not on tuning CDR variants until DA wins.
