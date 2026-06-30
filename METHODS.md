# Methods

This document summarizes the computational methods implemented in the
reproduction package. It is result-neutral: endpoints, selectors, risks, and
budgets are described here, but no claim verdicts or venue decisions are made.

## Simulator

Level 2 simulation uses Qiskit Aer. The validated local environment reports:

```text
Python 3.12.4
qiskit-aer 0.17.2
qiskit 2.4.2
scipy 1.18.0
cvxpy 1.9.1
```

The Dockerfile uses `python:3.12.4-slim` and fixes single-thread numerical
defaults through `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`,
and `OPENBLAS_NUM_THREADS=1`.

Pinned package versions are recorded in `requirements-lock.txt`, but that file
was generated on Windows and is not the final Linux/Docker lockfile. The
reproducible `linux/amd64` environment is a Phase B task: regenerate the
lockfile inside the container and then build-verify the Docker image from that
container-native lock.

The official hardware policy is analysis-from-archive only. Re-running a
quantum device is a new experiment, not reproduction.

## Decision Gaps and GRI

For a candidate landscape with reference optimizer index `0`, the contrast
matrix `L` contains rows `e_i - e_0`. The decision covariance is

```text
Sigma = L K L^T
```

where `K` is the residual covariance in candidate space. This is implemented in
`src/daqem/gap_kernel.py`.

The Gaussian risk index (GRI) is implemented in `src/daqem/risk.py` as the
probability that the estimated gap vector leaves the positive orthant:

```text
R(mu, Sigma; B) = 1 - Phi_d(sqrt(B) * mu; 0, Sigma)
```

The code uses `scipy.stats.norm` for one-dimensional gaps and
`scipy.stats.multivariate_normal.cdf(..., allow_singular=True)` for multivariate
gaps, with a deterministic `PCG64DXSM` generator passed to SciPy's CDF backend.

The signed diagonal exponent is zero if any margin is nonpositive; otherwise it
uses the diagonal Gaussian rate

```text
min_i mu_i^2 / (2 Sigma_ii).
```

Empirical decision risk is the mean of failure indicators.

## Selectors

`src/daqem/selectors.py` defines two primary selectors:

- `mse_selector`: chooses the method with minimum estimator MSE.
- `da_selector`: chooses the method with minimum GRI when the Gaussian audit is
  valid; otherwise it uses the empirical-risk fallback.

Both selectors use lexicographic tie-breaking by method name. This is the code
path preserved by the freeze, even where planning documents note a different
tie-break convention for exact ties.

## QEM Methods

The frozen core menu is:

```text
Raw
Accuracy-ZNE
Decision-ZNE
```

Raw uses one active scale. Accuracy-ZNE and Decision-ZNE use the frozen scale
set `[1.0, 2.0, 3.0]`.

Accuracy-ZNE uses Richardson constraints. Decision-ZNE uses the decision-aware
SOCP rule implemented in `src/daqem/qem_methods.py`; the rule is frozen, and
per-cell coefficients are read from frozen A3 prediction artifacts when needed.

## Randomness

All deterministic streams follow `reproducibility/config/rng_policy.yaml`:

```text
root_seed: 260616
bit_generator: PCG64DXSM
seed_derivation: sha256(root_seed, instance_id, method, budget, replicate_id, stream) -> first_8_bytes_uint64
global_numpy_seed: forbidden
```

The package should not call `np.random.seed()` globally. New stochastic code
should derive a local generator through `daqem.rng.make_rng(...)`.

## RNG Seed Streams

The frozen `rng_policy.yaml` is not edited for the PRR rescope. Its `stream`
field is the namespace used to separate bootstrap, Aer, candidate-generation,
and extension randomness while keeping the same root seed and SHA256 derivation
rule.

Current stream usage:

| Purpose | Stream name(s) | Where used |
|---|---|---|
| Level-1 smoke generation | `gate0`, `a3` | `reproducibility/run_all.py` |
| QAOA/Aer counts | `aer_counts`, `gate0_pilot_generation`, `executability`, `executability_batch` | `src/daqem/qaoa.py`, `experiments/gate0_pilot_full_vs_diagonal.py`, `experiments/e0_executability_audit.py` |
| Candidate landscapes and dynamic trajectories | `ideal_search`, `shared_initial`, `round_<t>`, `batch_scale_<scale_idx>` | `src/daqem/candidates.py`, `experiments/e2_dynamic_batch_candidate_optimizer.py` |
| Paired/bootstrap inference | `paired_observed_outcome_bootstrap`, `f1c_joint_bootstrap`, `f1c_sigmahat_bootstrap`, `f1c_sigmahat_subsample`, `ci` | `experiments/pilot_power_report.py`, `experiments/a3_gaussianity_sigmahat_audit.py`, `experiments/proof_of_mechanism_run.py` |
| Learned/noise diagnostic arms | `cdev_learning_<profile>`, `multinomial_probabilities` | `experiments/cdev_learned_arm.py`, `experiments/r1_full_run.py` |
| CDR extension | `cdr_training`, `cdr_training_shots`, `cdr_target_shots` | `src/daqem/cdr.py` |
| PEC extension | `pec_quasiprob_sampling`, `pec_aer_counts`, `pec_raw_reference`, `het_channel` | `src/daqem/pec.py`, `reproducibility/config/het_pec_derisk.yaml` |
| Proof-of-mechanism CRN/order | `method_order`, `proof_multinomial`, `proof_effective_multinomial` | `experiments/proof_of_mechanism_run.py` |
| Transpiler randomness | not used in current runners | The current reproduction path does not rely on stochastic transpiler passes. If a stochastic transpiler path is added, it should derive its seed through `make_rng(..., stream="transpiler")` rather than introducing a global seed. |

## Budget Accounting

The budget ledger follows PAP section 4.4. The cost components in
`src/daqem/budget.py` are:

```text
C_train
C_select
C_eval
C_calib
C_noiselearn
C_Sigmahat
C_overhead
```

`C_total` is the sum of those seven components. The amortized cost used for
some reporting is `C_eval + C_overhead`.

The frozen confirmatory allocation records:

```text
budget_grid: [256, 512, 1024, 2048, 4096, 8192]
B_star_operational: 512
Raw active scales: 1
Accuracy-ZNE active scales: 3
Decision-ZNE active scales: 3
```

For matched-cost dynamic reporting, the total shot cost per candidate is the
nominal budget multiplied by the number of active scales.

## Inference and Tolerances

The frozen inference config uses:

- Ledoit-Wolf covariance shrinkage as the primary covariance estimator, with
  sample covariance as fallback when required by the implementation.
- A paired McNemar-style one-sided test for the static primary comparison.
- `alpha_primary = 0.05`.
- `bootstrap_repetitions = 10000` where bootstrap intervals or projected power
  are required.

Verification tolerances are in `reproducibility/config/tolerances.yaml`:

```text
Level 1 numeric_abs = 1e-12
Level 2 numeric_abs = 1e-6
Level 3 numeric_abs = 1e-12
verdict_fields.hard_fail_on_flip = true
```

Any pass/fail or claim-verdict flip is a hard reproducibility failure.

## Recompute and Archive Policy

Cheap aggregation steps can be recomputed from archived inputs. Expensive Aer
and density-matrix generation blocks are archive-first unless the reviewer
explicitly requests a full recomputation.

Measured confirmatory timings in this workspace:

| Block | Measured duration |
|---|---:|
| raw generation | 18,446.3 s (~5h07m) |
| A3 density-matrix prediction | 2,959.409 s (~49m19s) |
| E1 aggregation | 112.655 s (~1m53s) |
| E2 trajectory generation | 124,628.911 s (~34h37m) |

The recorded E2 checkpoint contains 32 complete instances, with mean
per-instance duration about 64.9 minutes.

## Hardware Carve-Out

Level 3 consumes archived hardware counts, calibration snapshots, and job
metadata. It reproduces the analysis applied to those archived records only.
The reproduction package must never submit new jobs to a quantum backend as
part of verification.

## Long-Running Execution

Long runs should be started as detached processes and monitored through their
own logs and checkpoint files. The current generic `run_all.py` harness supports
checkpoint/resume for the fast Level 1 path only. Level 2 confirmatory runners
use their own direct script entry points and per-instance checkpoints.

Example Level 1 run:

```powershell
.\.venv-aer\Scripts\python.exe reproducibility\run_all.py --mode fast --level 1
.\.venv-aer\Scripts\python.exe reproducibility\verify.py --reference reproducibility\reference\
```

If a Level 2 runner is interrupted, re-run the same experiment command without
changing frozen configs or source files. Completed per-instance artifacts are
reused by the runner-specific checkpoint logic.
