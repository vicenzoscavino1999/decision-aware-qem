# Methods and reproduction scope

The main command recalculates the analyses reported in v45 from the archived inputs listed below. Generated files are written outside the source package.

| Component | Inputs | Calculation performed |
|---|---|---|
| Numerical core | Deterministic fixtures and test cases | Complete tests and three exact Level-1 repetitions. |
| E1 main comparison | Measurement samples and the 10/10/20 partition | Coefficient fitting, method selection, evaluation and shot accounting. |
| E2 | Saved trajectory outcomes | Success rates and full trajectory costs. Individual-shot replay is optional. |
| E3 | Circuits, settings and saved samples | Physical-model predictions, covariance estimates and risk/order comparisons. |
| A3 and C3 | Samples and learned-channel evidence | Bootstrap, covariance propagation and comparisons. |
| FakeKolkata | Archived output probability vectors | Sampling, fitting, selection and evaluation for the fixed ten-qubit block. |
| Hardware | Archived counts and calibration records | Classical predictions and epoch-level bootstrap. |
| CDR/PEC, noise and other controls | Included numerical evidence | Independent numerical checks of the archived relationships and outputs. |
| Signed PEC | Exact output laws, seeds and signed counts | Count regeneration from seeds; reconstruction of decisions, estimators, costs and moments. |
| E1 partitions | Samples, saved coefficients and decisions | Integer decision replay, MSE selection, budgets, balance and close-risk checks. Optional execution repeats fitting. |
| Readout identifiability | Discrete model in the article | Exact rational probabilities, energies and ideal minimizers. |

## Environment and randomness

The Dockerfile fixes the Linux amd64 base by digest. `requirements-lock.linux.txt` fixes dependency versions and distribution hashes. BLAS/OpenMP threads are limited to one per process. Seeds and instance identifiers determine the experiment-specific streams; bootstrap and supplement seeds are recorded in their protocols.

## Budgets and decisions

Static comparisons distinguish evaluation cost from full cost, including fitting and selection. Budget ledgers show these allocations. Strict static argmin counts ties as failures. Dynamic decisions retain the first batch candidate or the previous incumbent on an exact tie. Integer sums are used where the estimator admits them.

## Numerical comparison

Level-1 outputs must match exactly. Main-analysis decisions, counts and labels are compared exactly; floating values use field-specific tolerances in `code/reproducibility/config/tolerances.yaml`. Ordinary arithmetic uses absolute tolerance `1e-10` and relative tolerance `1e-8`; Gaussian probabilities allow absolute difference `1e-6`. Derivatives, risk differences and normalized ratios have separately specified rules.

The comparison is followed by checks linking v45 to the included references. E1 partitions reuse measurements; averaging and bootstrap retain the instance as the grouping unit. Signed PEC regenerates marginal signed-output counts from the included laws. Neither operation creates a new independent collection of landscapes.

## Acquisition routes

The main workflow reproduces analyses from archived inputs. It does not regenerate every simulation campaign from its initial circuit construction. E2 has separate commands for original-shot replay and new-round generation. Hardware reproduction uses archived counts; collecting new device data is a different experiment.
