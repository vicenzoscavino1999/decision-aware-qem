# Phase Diagram Grid Note

`grid.csv` computes Raw/CDR/PEC MSE and GRI over a `(budget, p1)` grid using the
existing proof-of-mechanism machinery in `experiments/phase_diagram_grid.py`.

Finding: under uniform depolarizing noise, the empirical phase diagram is
degenerate. Across the grid, the MSE-optimal method is CDR, while the
decision-optimal method is Raw equivalent to CDR because the locked CDR correction
is affine and decision-invariant. PEC is never decision-optimal in this uniform
channel regime (`lambda * gamma > 1`).

Therefore the grid is retained as support data and robustness evidence for section
1835 across the noise-rate axis, but it is not rendered as a paper figure. The
analytic PEC-CDR boundary from Eq. 1300 belongs in the manuscript text, not in this
empirical figure pipeline.
