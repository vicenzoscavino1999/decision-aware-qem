# Results map — manuscript v45

The PDF has 34 pages. Output paths start at `run/`, inside the directory selected in the README. Included main-analysis references normally have the same path after removing `analysis/`.

| Article component | Recalculated output |
|---|---|
| E1; Section 10.3, Table 2, Figure 5 | `analysis/results/e1/summary.csv` |
| E1 learning and evaluation cost | `analysis/results/e1/budget_ledger.csv` |
| E2; Section 10.4, Figure 6 | `analysis/results/e2/e2_summary.json` |
| E3; Section 10.2, Figure 4 | `analysis/results/confirmatory/e3_summary.json` |
| FakeKolkata; Section 10.5 | `analysis/results/fakekolkata_fixed10/summary.json` |
| Hardware; Section 10.5, Appendix F | `analysis/results/hardware/hardware.json` |
| Learned channel; Appendix G | `analysis/results/pilot/c3_reanalysis.json` |

## Figures

| Figure | Source or generated PDF |
|---|---|
| 1: estimation, decision and shot allocation | Included source `manuscript/figures/F0_estimation_decision_cost.tex`. |
| 2: CDR–PEC boundary | TikZ source embedded in `manuscript/main.tex`. |
| 3: initial CDR/PEC control | `figures/F1_accuracy_decision_separation.pdf` |
| 4: E3 comparisons | `figures/F9_e3_comparisons.pdf` |
| 5: static E1 | `figures/F7_e1_reanalysis.pdf` |
| 6: full E2 cost | `figures/F8_dynamic_full_cost.pdf` |
| 7: full and diagonal covariance | `figures/F6_gate0_full_vs_diagonal.pdf` |

See [compilation instructions](OPTIONAL.md#4-compile-the-article-and-the-overview) for Figures 1–2. The package's `results_index.json` maps further controls, noise and ablations.

## Signed PEC — Section 10.1, Table 1, Appendix H.1

`run/supplements.json` gives the supplementary working directory. Its `pec/` subdirectory contains `results.json`, `cell_results.csv`, `laws/` and `records/`; `pec_verification.json` records the new count and decision replay.

The primary budget is 3,072 shots per candidate. Table 1 reports expected MSE and observed failure. The text also reports empirical MSE; these have separate columns in `cell_results.csv`.

## E1 partitions — Section 10.3, Appendix H

The same working directory contains `e1/`: `splits.json`, `split_summary.csv`, `average_summary.csv`, `instance_average_rates.csv`, `choices.csv` and `budget_ledger.csv`. Its new reports are `verification.json` and `close_score_verification.json`.

`comparison=evaluation` denotes evaluation cost; `comparison=end_to_end` denotes full cost. `S000` is the original partition; `S001`–`S020` are the alternatives used in sensitivity averages.

## Manuscript checks

The supplementary working directory's `manuscript/` contains `main.json`, `signed_pec.json`, `e1_partitions.json` and `readout.json`. These identify the v45 source/PDF and the checks against the numerical evidence.
