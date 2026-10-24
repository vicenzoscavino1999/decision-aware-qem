# Pilot planning diagnostic

The same pilot samples fit the coefficients, select the methods and evaluate failure. Ideal margins enter the fit. These are descriptive oracle results, not held-out performance.

Failure includes every exact tie, reconstructed from integer MaxCut shot sums and exact rational comparison keys. Relative reduction is undefined when baseline failure is zero.

B is shots per candidate per noise scale: Raw uses B and ZNE uses 3B. The selection menu shares primitive records. These cells do not compare equal total policy costs.

Primary rule: failure in [0.15, 0.7], maximum distance to band edges, then lower failure, budget and cell id. The chosen budget is a planning convention, not a certified theoretical B*.

Power uses the exact one-sided McNemar test under a plug-in iid multinomial model of the pooled in-band pilot pairs. It assumes fixed selectors and independent future pairs with the same pooled probabilities. It does not account for instance clustering, fitting/selection uncertainty, or pilot-based choice of cells and budget.

The 48 x 40 design below is the historical planning target, not a claim about the size or power of the completed campaign. Comparing the observed reduction to 0.15 does not establish a minimum detectable effect or power at that target. A Monte Carlo value of 1 is not certainty.

## Planning summary

```json
{
  "scope": "same_sample_oracle_pilot_planning",
  "independent_pairs_assumed": true,
  "cluster_power_established": false,
  "minimum_detectable_effect_established": false,
  "primary_cell": "P004",
  "primary_budget": 512,
  "planned_pairs": 1920,
  "alpha": 0.05,
  "effect_target": 0.15,
  "pooled": {
    "budget": 512,
    "pilot_instances": 3,
    "paired_n_pilot": 600,
    "both_fail": 154,
    "both_ok": 339,
    "b": 78,
    "c": 29,
    "failure_rate_MSE_pooled": 0.38666666666666666,
    "failure_rate_DA_pooled": 0.305,
    "observed_rel_reduction_pooled": 0.21120689655172414,
    "observed_effect_meets_target": true
  },
  "exact_iid_plugin_power": 0.9999999999991854,
  "monte_carlo_iid_plugin_power": 1.0,
  "monte_carlo_repetitions": 10000
}
```

## All pilot cells

| cell | B | MSE method | GRI method | MSE failure | GRI failure | Raw failure | relative reduction | b | c | in band |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---|
| P001 | 256 | Decision-ZNE | Raw | 0.55 | 0.44 | 0.44 | 0.2 | 31 | 9 | True |
| P001 | 512 | Decision-ZNE | Raw | 0.475 | 0.36 | 0.36 | 0.242105263 | 29 | 6 | True |
| P001 | 1024 | Decision-ZNE | Raw | 0.36 | 0.24 | 0.24 | 0.333333333 | 31 | 7 | True |
| P001 | 2048 | Accuracy-ZNE | Raw | 0.25 | 0.19 | 0.19 | 0.24 | 18 | 6 | True |
| P001 | 4096 | Decision-ZNE | Raw | 0.15 | 0.065 | 0.065 | 0.566666667 | 20 | 3 | True |
| P001 | 8192 | Accuracy-ZNE | Raw | 0.045 | 0.015 | 0.015 | 0.666666667 | 7 | 1 | False |
| P002 | 256 | Decision-ZNE | Raw | 0.48 | 0.315 | 0.315 | 0.34375 | 36 | 3 | True |
| P002 | 512 | Decision-ZNE | Raw | 0.28 | 0.165 | 0.165 | 0.410714286 | 29 | 6 | True |
| P002 | 1024 | Accuracy-ZNE | Raw | 0.075 | 0.015 | 0.015 | 0.8 | 14 | 2 | False |
| P002 | 2048 | Accuracy-ZNE | Raw | 0.01 | 0 | 0 | 1 | 2 | 0 | False |
| P002 | 4096 | Decision-ZNE | Raw | 0 | 0 | 0 | undefined | 0 | 0 | False |
| P002 | 8192 | Accuracy-ZNE | Raw | 0 | 0 | 0 | undefined | 0 | 0 | False |
| P003 | 256 | Decision-ZNE | Raw | 0.05 | 0.015 | 0.015 | 0.7 | 7 | 0 | False |
| P003 | 512 | Decision-ZNE | Raw | 0 | 0 | 0 | undefined | 0 | 0 | False |
| P003 | 1024 | Accuracy-ZNE | Raw | 0 | 0 | 0 | undefined | 0 | 0 | False |
| P003 | 2048 | Decision-ZNE | Raw | 0 | 0 | 0 | undefined | 0 | 0 | False |
| P003 | 4096 | Decision-ZNE | Raw | 0 | 0 | 0 | undefined | 0 | 0 | False |
| P003 | 8192 | Decision-ZNE | Raw | 0 | 0 | 0 | undefined | 0 | 0 | False |
| P004 | 256 | Decision-ZNE | Raw | 0.5 | 0.49 | 0.49 | 0.02 | 21 | 19 | True |
| P004 | 512 | Decision-ZNE | Raw | 0.405 | 0.39 | 0.39 | 0.037037037 | 20 | 17 | True |
| P004 | 1024 | Decision-ZNE | Raw | 0.355 | 0.335 | 0.335 | 0.0563380282 | 20 | 16 | True |
| P004 | 2048 | Decision-ZNE | Raw | 0.28 | 0.25 | 0.25 | 0.107142857 | 19 | 13 | True |
| P004 | 4096 | Decision-ZNE | Raw | 0.235 | 0.22 | 0.22 | 0.0638297872 | 15 | 12 | True |
| P004 | 8192 | Decision-ZNE | Raw | 0.175 | 0.135 | 0.135 | 0.228571429 | 13 | 5 | True |
