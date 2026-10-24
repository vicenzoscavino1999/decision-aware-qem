# Reproducibility plan for the Decision-Aware QEM PAP v13

This document defines the reproducibility package for the paper plan

**Decision-Aware Quantum Error Mitigation: Predicting Quantum Shot Cost from the
Decision Gap Kernel**

It is adapted to the experimental pre-analysis plan:

```text
EXPERIMENTAL_PLAN_v13_PRXQ.md
sha256:84317E348002DC98CFFB18D8F340A382C0675846C6298852E7465C0097628101
```

The goal is not only to publish code. The goal is to make the numerical and
pre-registered claims auditable: a reviewer should be able to rebuild the
environment, rerun the supported experiments, regenerate the paper figures, and
verify that the reported claims follow from the frozen PAP, frozen configs,
budget ledger, generated outputs, and archived hardware counts.

This is a standalone reproducibility plan for the PAP v13 project. It should be
implemented as a new reproduction package, not by modifying an unrelated paper's
reproducibility artifact.

## Core Decision

The official reproduction route is Docker-based.

Docker is the baseline environment, not an optional convenience layer. Native
Python installs can be documented for development, but the published
instructions should treat the container as the authoritative execution
environment.

The dependency policy is:

- `pyproject.toml`: canonical project metadata and dependency bounds.
- `requirements-lock.txt`: exact locked dependencies generated inside the
  container, preferably with hashes using `pip-compile --generate-hashes`.
- No loose, unpinned `requirements.txt` as a reproducibility artifact.
- No `environment.yml` unless a future dependency truly requires Conda.

Qiskit/Aer is required for Level 2 device-simulation runs. IBM Runtime or
backend-access clients are required only to generate new hardware data, and are
not part of the official reproduction path. Hardware reproduction is
analysis-from-archived-counts only.

## Reproduction Levels

The PAP has execution gates and experimental phases. The reproducibility package
uses three computational levels.

### Level 1 - deterministic core and mini regression

Level 1 is the fast, hard-reproducible core. It should not require a quantum
cloud account. It covers:

- deterministic construction of candidate sets, contrasts, gap kernels, and
  selectors on small cells;
- synthetic or exact simulator checks for `Sigma = L K L^T`;
- Gate 0 full-vs-diagonal mini regression;
- A3 pullback-frontier mini regression using a frozen synthetic or exact
  `C_dev`;
- GRI risk computation on a small fixed Gaussian cell;
- budget-ledger, schema, freeze-manifest, and claim-language consistency checks.

Level 1 is not expected to reproduce every large Aer experiment. It is the
reviewer's quick audit path for the decision-kernel machinery.

### Level 2 - recomputable simulation and Aer device model

Level 2 recomputes the scientific simulation outputs used for the paper:

- E0/E0.5 pilot gates where they are simulation-based;
- E1 static DA-QEM selector;
- E2 dynamic Batch Candidate Optimizer;
- E3 `B_star` prediction and directional ordering;
- E4 power, sensitivity, and failure-rate audit;
- E5 exact claim survival table;
- ablations, controls, and non-toy robustness cells R1-R3;
- `C_dev^true` versus `C_dev^learned` diagnostics when the learning run is
  simulation-based;
- GRI calibration and empirical fallback tables.

Level 2 must be reproducible under pinned seeds and pinned dependencies, but its
tolerances are not machine-epsilon tolerances. It verifies the registered
quantities, risk orderings, intervals, and claim verdicts within documented
tolerance.

### Level 3 - hardware analysis from archived counts

Level 3 never re-executes a quantum device. It consumes:

- archived IBM raw counts;
- calibration snapshots;
- job metadata;
- the frozen analysis code.

It reproduces only the analysis applied to archived counts:

- hardware-Sigma micro-cell estimates;
- hardware ordering at below/near/above budgets if those budgets were executed;
- local crossing-budget consistency if only one budget was executed;
- cluster bootstrap by epoch;
- hardware claim-language status.

Re-running hardware is a new experiment, not a reproduction.

## Release Phases

The package should be built in two phases.

### Phase A - submission-ready MVP

Goal: enough for a reviewer to verify the submitted numerical story.

Required scope:

- Clean repository skeleton.
- Simple functional Dockerfile.
- PAP hash captured in `PAP_HASH.txt`.
- Phase 0 executability schema and sample output structure.
- Frozen config layout for selectors, budgets, contrasts, GRI calibration, and
  A3 pullback specification.
- Level 1 deterministic mini regression for:
  - full-vs-diagonal Gate 0;
  - A3 projected flip tolerance;
  - GRI risk computation;
  - selector tie-breaking;
  - budget ledger validation.
- `run_all.py` supports `--mode fast`, `--level 1`, and schema-compatible output.
- `verify.py` validates schemas, tolerances, freeze manifest, and claim-language
  consistency.
- Core tests pass:
  - determinism;
  - budget ledger;
  - contrast matrix;
  - risk computation;
  - selector logic;
  - verifier negative tests.
- Minimal `README.md` explains `make reproduce-fast`, `make reproduce-full`,
  `make verify`, and `make analysis-from-hardware`.
- Minimal `METHODS.md` documents the simulator, risk computation, seeds, budget
  accounting, and hardware carve-out.
- Draft `CITATION.cff` and `.zenodo.json` exist.

Not required in Phase A:

- multi-stage Dockerfile;
- Docker digest pinning;
- GitHub Actions;
- pre-commit hooks;
- full Level 2 grid;
- full hardware archive;
- final Zenodo DOI.

### Phase B - archival release

Goal: enough for an independent researcher to reproduce, audit, and extend the
work several years later.

Required scope:

- Multi-stage Dockerfile pinned by digest.
- Full Level 2 recomputation of every simulation output used in the paper.
- Hardware analysis-from-counts path for every hardware figure/table included.
- Complete `METHODS.md`.
- Complete test suite.
- CI inside Docker.
- `CONTRIBUTING.md`.
- Pre-commit guardrails.
- Advisory dependency vulnerability check.
- Final GitHub release.
- Zenodo archival release with version-specific DOI.
- Final paper-to-code mapping and DOI in the manuscript.

## Repository Layout

Target public repository:

```text
decision-aware-qem/
  README.md
  METHODS.md
  CONTRIBUTING.md
  LICENSE
  LICENSE-DATA
  CITATION.cff
  .zenodo.json
  PAP_HASH.txt
  EXPERIMENTAL_PLAN_v13_PRXQ.md
  REPRODUCIBILITY_PLAN_v13_PRXQ.md
  Dockerfile
  .dockerignore
  .pre-commit-config.yaml
  .devcontainer/
    devcontainer.json
  Makefile
  pyproject.toml
  requirements-lock.txt
  .github/
    workflows/
      reproduce.yml
  src/
    daqem/
      __init__.py
      candidates.py          # candidate grids and frozen candidate sets
      qaoa.py                # QAOA/MaxCut problem cells
      vqe.py                 # optional VQE/Ising/Heisenberg robustness cells
      noise.py               # Pauli, depolarizing, amplitude damping, dephasing
      cdev.py                # C_dev construction and sparse PL learning interface
      qem_methods.py         # Raw, Accuracy-ZNE, Decision-ZNE, optional CDR/PEC
      gap_kernel.py          # L, K, Sigma = L K L^T
      risk.py                # GRI, empirical risk, MVN probabilities
      selectors.py           # MSE and DA selector logic
      dynamic.py             # Batch Candidate Optimizer
      inference.py           # bootstrap, CI, gatekeeping, Romano-Wolf hooks
      budget.py              # budget ledger and cost accounting
      hardware.py            # analysis-from-counts helpers
      plotting.py
  experiments/
    e0_executability_audit.py
    gate0_pilot_full_vs_diagonal.py
    a3_pullback_frontier.py
    a3_gaussianity_sigmahat_audit.py
    cdev_learned_arm.py
    e1_static_da_selector.py
    e2_dynamic_batch_candidate_optimizer.py
    e3_bstar_prediction.py
    e4_power_sensitivity_audit.py
    e5_claim_survival_table.py
    ablation_full_vs_diagonal.py
    ablation_shuffled_L.py
    ablation_method_tuning.py
    ablation_gri_vs_empirical.py
    regime_frontier.py
    focal_lower_bound.py
    robustness_secondary_optimizers.py
    control_common_mode.py
    control_mse_enough.py
    control_affine.py
    robustness_generality_matrix.py
    hardware_sigma_microcell_analysis.py
    hardware_ordering_analysis.py
  scripts/
    generate_all_figures.py
    build_freeze_manifest.py
    update_reference_manifest.py
  reproducibility/
    run_all.py
    verify.py
    config/
      phase0_executability.yaml
      gate0_pilot.yaml
      a3_pullback_frontier.yaml
      a3_gaussianity.yaml
      cdev_learning.yaml
      gri_calibration.yaml
      method_tuning_ablation.yaml
      gri_empirical_ablation.yaml
      regime_frontier.yaml
      focal_lower_bound.yaml
      secondary_optimizers.yaml
      selectors.yaml
      budget_grid.yaml
      budget_ledger_schema.yaml
      dynamic_task.yaml
      inference.yaml
      rng_policy.yaml
      schemas.yaml
      tolerances.yaml
      claim_registry.yaml
    reference/
      reference_manifest.json
      checksums.sha256
      <canonical reference outputs>
    hardware/
      raw_counts/
      calibration_snapshots/
      job_metadata.json
  tests/
    fixtures/
      mini_gate0_reference.csv
      mini_a3_reference.csv
      mini_selector_reference.csv
    test_budget_ledger.py
    test_contrast_matrix.py
    test_gap_kernel.py
    test_gri_risk.py
    test_selector_logic.py
    test_e0_executability.py
    test_a3_pullback_frontier.py
    test_a3_gaussianity_sigmahat_audit.py
    test_cdev_learning.py
    test_checkpoint.py
    test_determinism.py
    test_regression.py
    test_verify.py
  data/
  results/
    .partial/
  figures/
  paper/
    main.tex
    references.bib
```

The `paper/` directory should remain clean. It should not contain `.aux`,
`.log`, `.out`, `.synctex.gz`, local editor files, or ad hoc generated data.

`LICENSE` covers code. `LICENSE-DATA` covers archived numerical outputs,
figures, and hardware counts, preferably under CC-BY-4.0.

## Docker Policy

During development, a pinned Python patch tag is acceptable:

```dockerfile
FROM python:3.12.4-slim
```

For the final archival release, pin by digest:

```dockerfile
FROM python:3.12.4-slim@sha256:<digest>
```

Do not use floating tags for the archived release.

Set deterministic numerical defaults:

```dockerfile
ENV PYTHONHASHSEED=0
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
```

The `.dockerignore` must exclude:

```text
.git
data/
results/
figures/
paper/
reproducibility/hardware/raw_counts/
*.pdf
__pycache__/
*.pyc
.mypy_cache/
.pytest_cache/
```

Hardware counts belong in the Zenodo deposit, not the Docker build context.

## Makefile Interface

User-facing commands:

```makefile
reproduce: reproduce-full verify

run:
	python reproducibility/run_all.py

verify:
	python reproducibility/verify.py --reference reproducibility/reference/

figures:
	python scripts/generate_all_figures.py

test:
	pytest tests/ -v

check: test verify

check-env:
	python reproducibility/run_all.py --check-env-only

reproduce-fast:
	python reproducibility/run_all.py --mode fast --level 1
	python reproducibility/verify.py --reference reproducibility/reference/

reproduce-level1:
	python reproducibility/run_all.py --level 1
	python reproducibility/verify.py --reference reproducibility/reference/

reproduce-pilot:
	python reproducibility/run_all.py --stage pilot
	python reproducibility/verify.py --reference reproducibility/reference/

reproduce-confirmatory:
	python reproducibility/run_all.py --stage confirmatory
	python reproducibility/verify.py --reference reproducibility/reference/

reproduce-full:
	python reproducibility/run_all.py --mode full --levels 1,2
	python reproducibility/verify.py --reference reproducibility/reference/

analysis-from-hardware:
	python reproducibility/run_all.py --level 3 --from-archived-counts
	python reproducibility/verify.py --reference reproducibility/reference/

determinism-check:
	python reproducibility/run_all.py --mode fast --level 1 --output results/determinism-run-1
	python reproducibility/run_all.py --mode fast --level 1 --output results/determinism-run-2
	python reproducibility/verify.py --reference results/determinism-run-1 --generated results/determinism-run-2 --exact-numeric
```

## Reproduction Command Contracts

`make reproduce-fast`:

- Runs a deterministic Level 1 subset.
- Must include:
  - a Gate 0 full-vs-diagonal mini cell;
  - an A3 projected flip tolerance mini cell;
  - a GRI risk computation mini cell;
  - selector tie-breaking and budget ledger checks.
- Should complete in minutes.
- A pass proves the code path, schemas, seeds, and core decision-kernel machinery
  are consistent with the reference subset.
- A pass does not prove the full PRXQ grid was recomputed.

`make reproduce-level1`:

- Recomputes the deterministic mini-regression outputs and unit-test fixtures.
- Has no cloud dependency.
- A pass means the core gap-kernel, selector, budget, and verification logic
  reproduces exactly inside the supported container.

`make reproduce-pilot`:

- Recomputes pilot-stage outputs that are designated recomputable:
  - E0 executability tables;
  - Gate 0 outputs;
  - A3 pullback-frontier outputs;
  - GRI calibration tables;
  - pilot power report;
  - regime-frontier output if 9.5-track language is claimed;
  - `C_dev^true` versus `C_dev^learned` diagnostics when simulation-based.
- Does not alter frozen confirmatory configs.
- A pass means the pilot artifacts match the archived reference state.

Current implementation note: A3/F1b and F1c-A/F1c-B pilot analyses are run by
their direct scripts, for example
`python -m experiments.a3_pullback_frontier --profile full`,
`python -m experiments.a3_gaussianity_sigmahat_audit --profile full`, and
`python -m experiments.cdev_learned_arm --profile full`. They are not yet
orchestrated by `run_all.py --stage pilot`.

Known issue: `results/pilot/pullback_frontier.csv` is written both by the
synthetic Level 1 pullback mini block and by the real A3 pilot script. Running
`run_all.py --level 1` after the real A3 pilot run can overwrite the real A3
CSV with the Level 1 mini output. This is flagged for orchestration cleanup and
should not be fixed by renaming existing artifacts in this sync.

`make reproduce-confirmatory`:

- Recomputes E1-E5 under frozen configs:
  - static decision failure;
  - dynamic shots-to-success;
  - `B_star` prediction or directional ordering;
  - power/sensitivity audit;
  - claim survival table.
- Uses the frozen budget ledger and frozen selector tables.
- A pass means the primary paper outputs reproduce within their registered
  tolerance tier.

`make reproduce-full`:

- Recomputes every Level 1 and Level 2 output needed for the manuscript figures,
  tables, and claim survival table.
- Includes required ablations: method tuning, full-vs-diagonal, shuffled `L`,
  and GRI-vs-empirical when core GRI is valid.
- Includes focal-lower-bound outputs only when that figure or claim is present.
- Does not re-execute hardware.
- Should report measured runtime and RAM on the supported Docker platform.

`make analysis-from-hardware`:

- Recomputes only Level 3 analysis from archived raw counts.
- Never contacts a backend.
- A pass means the hardware analysis pipeline applied to archived counts
  reproduces the reported hardware estimators and claim-language status.

`make verify`:

- Performs schema validation and numerical comparison.
- Validates the freeze manifest, budget ledger, claim registry, and claim survival
  table.
- Validates required ablation presence and optional-track gating.
- Applies tolerance tiers by level.
- Exits nonzero on hard-fail schema or numerical errors.

## Fallback Without Docker

The supported reproduction path is Docker on `linux/amd64`.

A non-Docker path may be documented for HPC, Podman, Singularity/Apptainer, or
locked-down machines, but it is not the archival standard.

Non-Docker users may run:

```bash
pip install -e .
export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
make reproduce-fast
```

Outside Docker, strict tolerances may fail because of BLAS/LAPACK differences.
Relaxed verification can be provided as diagnostic only, not as the official
reproduction route.

## Pre-flight Checks

Before expensive computation, `run_all.py` must execute pre-flight checks.

Required checks:

- Python, NumPy, SciPy, and Qiskit/Aer versions match the lockfile for the
  requested level.
- `PYTHONHASHSEED=0`.
- `OMP_NUM_THREADS=1`.
- `MKL_NUM_THREADS=1`.
- `OPENBLAS_NUM_THREADS=1`.
- Output directory is writable.
- No corrupt `.partial/` outputs unless resume mode is active.
- `PAP_HASH.txt` matches the hash recorded in `freeze_manifest.json` and
  `reference_manifest.json`.
- Frozen configs required by the requested stage exist.
- `results/frozen/budget_ledger.csv` exists before confirmatory runs.
- `results/frozen/contrast_matrices.npz` exists before selector or GRI runs.
- For Level 2: Qiskit/Aer imports succeed and the Aer seed is set.
- For `C_dev^learned`: sparse Pauli-Lindblad learning config exists and is
  accounted for in the budget ledger.
- For Level 3: raw counts, calibration snapshots, and job metadata exist and
  checksums match.

Critical failures abort before numerical work starts.

## Long-running Execution Policy

Any computation expected to exceed about 30 minutes should support checkpointing.

Rules:

- `run_all.py` writes block outputs under `results/.partial/`.
- A block is complete only after data and checksum are written.
- On startup, complete partial blocks are reused.
- Corrupt blocks are recomputed.
- `run_all.py --restart` deletes partial outputs and starts from scratch.
- The final `results/manifest.json` records whether the run was clean, resumed,
  or restarted.

Natural block identifiers:

```text
stage / experiment / problem_family / noise_family / depth / instance_id / method / budget / replicate_or_trajectory
```

Default error handling is fail-fast. A diagnostic `--continue-on-error` flag may
continue independent blocks, but the final manifest must mark failed outputs as
`incomplete`, and `verify.py` must fail required incomplete outputs.

## Hardware Reproduction Carve-out

Principle: quantum-device execution is not reproducible by re-running it.

Level 3 reproduction is analysis reproduction from archived raw data.

Every hardware job must archive:

- raw measurement counts per circuit:
  `reproducibility/hardware/raw_counts/<job_id>.json`;
- calibration snapshot at submission time:
  `reproducibility/hardware/calibration_snapshots/<job_id>.json`;
- job metadata:
  `reproducibility/hardware/job_metadata.json`;
- epoch/block mapping for interleaved execution;
- transpilation seed, backend name, UTC submission time, shot count, circuit
  hashes, and budget label.

`verify.py` must:

- fail if expected hardware archive files are missing;
- verify checksums;
- reproduce post-processing only;
- enforce hardware claim-language rules:
  - one near-crossing budget cannot claim directional ordering;
  - three budgets are required for budget-dependent hardware ordering;
  - hardware-Sigma micro-cell is required for a strong `device-level` headline.

Hardware outputs are not included in bit-for-bit determinism checks.

## Verification Policy

The repository needs explicit numerical verification, not only scripts that make
plots.

Required files:

```text
reproducibility/
  reference/
    reference_manifest.json
    checksums.sha256
    <canonical reference outputs>
  config/
    schemas.yaml
    tolerances.yaml
    rng_policy.yaml
    claim_registry.yaml
  run_all.py
  verify.py
```

The concrete output filenames come from the PAP v13 and the frozen configs. This
plan may name canonical expected outputs, but implementation should keep the PAP
as the scientific authority.

Minimum canonical outputs:

```text
results/pilot/executability_budget_table.csv
results/pilot/executability_budget_table.md
results/pilot/gate0_full_vs_diagonal.csv
results/pilot/pullback_frontier.csv

results/frozen/budget_ledger.csv
results/frozen/critical_bands.csv
results/frozen/contrast_matrices.npz
freeze_manifest.json

results/confirmatory/e1_static_decision_failure.csv
results/confirmatory/e2_dynamic_shots_to_success.csv
results/confirmatory/e3_bstar_prediction.csv
results/confirmatory/e4_power_sensitivity_audit.csv
results/confirmatory/e5_claim_survival_table.csv

results/ablations/full_vs_diagonal.csv
results/ablations/shuffled_L.csv
results/ablations/method_tuning.csv
results/ablations/gri_vs_empirical.csv
results/controls/common_mode.csv
results/controls/mse_enough.csv
results/controls/affine.csv
results/robustness/generality_matrix.csv
results/robustness/secondary_optimizers.csv
results/secondary/focal_lower_bound.csv

results/hardware/hardware_sigma_microcell.csv
results/hardware/hardware_ordering.csv

figures/focal_lower_bound.pdf

results/claim_adjudication_table.csv
results/manifest.json
```

Current pilot diagnostics are intentionally not canonical and are not part of
`verify.py`/`reproducibility/reference/`:

```text
results/pilot/regime_probe.md
results/pilot/a3_mean_crosscheck.md
results/pilot/a3_gaussianity.md
results/pilot/a3_sigmahat_audit.md
results/pilot/cdev_learned_arm.md
results/pilot/a3_frozen_prediction/*.npz
```

Future pilot/secondary blueprint outputs, if the corresponding paper claims are
included, remain governed by the PAP and frozen configs:

```text
results/pilot/pilot_power_report.md
results/pilot/mse_selector_table.csv
results/pilot/da_selector_table.csv
results/pilot/predicted_crossing_report.md
results/pilot/regime_frontier.csv
results/pilot/cdev_true_vs_learned.csv
results/pilot/gri_calibration_table.csv
```

`run_all.py` writes a manifest at the end of each execution:

```json
{
  "git_commit_sha": "abc123...",
  "git_dirty": false,
  "pap_hash": "sha256:84317E348002DC98CFFB18D8F340A382C0675846C6298852E7465C0097628101",
  "level": 2,
  "stage": "confirmatory",
  "python_version": "3.12.4",
  "platform": "Linux-x86_64",
  "timestamp_utc": "2026-06-20T00:00:00Z",
  "dependencies": {
    "numpy": "x.y.z",
    "scipy": "x.y.z",
    "qiskit": "x.y.z",
    "qiskit-aer": "x.y.z"
  },
  "rng": {
    "bit_generator": "PCG64DXSM",
    "root_seed": 260616
  },
  "runtime_seconds": 0.0,
  "execution_mode": "clean",
  "outputs": {
    "results/confirmatory/e1_static_decision_failure.csv": "sha256:..."
  }
}
```

`verify.py` should:

1. Load generated outputs.
2. Load reference outputs.
3. Validate schemas before numerical comparisons.
4. Fail on missing rows.
5. Fail on extra or missing columns.
6. Fail on unexpected data types.
7. Fail on `NaN` or `Inf`.
8. Match rows by explicit keys.
9. Compare numeric fields using `tolerances.yaml`.
10. Validate budget-ledger arithmetic.
11. Validate freeze-manifest hashes.
12. Validate selector tables against frozen inputs.
13. Validate claim survival table against gate statuses.
14. Validate claim-language restrictions.
15. Validate hardware carve-out rules.
16. Exit nonzero on hard failures.

No soft pass is allowed for claim-critical fields. Warning-only fields must be
explicitly marked as warning-only in `schemas.yaml`.

## Schema Requirements

Illustrative schemas:

```yaml
executability_budget_table.csv:
  format: csv
  level: 1
  row_matching_key: [block]
  columns:
    block: {type: string}
    primary_unit: {type: string}
    N_minimum: {type: float, min: 0}
    estimated_shots: {type: float, min: 0}
    wall_hours: {type: float, min: 0}
    backend_or_resource: {type: string}
    risk: {type: string}
    decision: {type: string, allowed: [go, no-go, conditional]}

budget_ledger.csv:
  format: csv
  level: 1
  row_matching_key: [method, selector, task, B_nominal, amortization_flag]
  columns:
    method: {type: string}
    selector: {type: string}
    task: {type: string}
    B_nominal: {type: int, min: 1}
    C_train: {type: float, min: 0}
    C_select: {type: float, min: 0}
    C_eval: {type: float, min: 0}
    C_calib: {type: float, min: 0}
    C_noiselearn: {type: float, min: 0}
    C_Sigmahat: {type: float, min: 0}
    C_overhead: {type: float, min: 0}
    C_total: {type: float, min: 0}
    amortization_flag: {type: string, allowed: [non_amortized, amortized]}

freeze_manifest.json:
  format: json
  level: 1
  required_fields:
    git_commit_sha: {type: string}
    git_dirty: {type: bool}
    docker_image_digest: {type: string}
    python_version: {type: string}
    qiskit_version: {type: string}
    qiskit_aer_version: {type: string}
    pap_hash: {type: string}
    experimental_plan_hash: {type: string}
    config_hashes: {type: object}
    script_hashes: {type: object}
    pilot_output_hashes: {type: object}
    confirmatory_analysis_script_hashes: {type: object}
    freeze_timestamp_utc: {type: string}

gate0_full_vs_diagonal.csv:
  format: csv
  level: 1
  row_matching_key: [problem_cell, method, budget]
  columns:
    problem_cell: {type: string}
    method: {type: string}
    budget: {type: int, min: 1}
    gri_full: {type: float, min: 0, max: 1}
    gri_diagonal: {type: float, min: 0, max: 1}
    delta_gri_full_minus_diagonal: {type: float}
    margin_threshold: {type: float, min: 0}
    selector_full: {type: string}
    selector_diagonal: {type: string}
    selector_changed: {type: bool}
    bstar_prediction_gain: {type: float}
    criterion_triggered: {type: string, allowed: [gri_margin, selector_change, bstar_prediction_gain, multiple, none]}
    mechanism_relevant: {type: bool}
    gate0_status: {type: string, allowed: [pass, fail, diagnostic]}

pullback_frontier.csv:
  format: csv
  level: 2
  row_matching_key: [problem_cell, pair_id, budget]
  columns:
    problem_cell: {type: string}
    pair_id: {type: string}
    budget: {type: int, min: 1}
    active_pair: {type: bool}
    delta_rank_projected: {type: float, min: 0}
    tau_flip_projected: {type: float, min: 0}
    projected_error_over_tolerance: {type: float, min: 0}
    frobenius_error_over_tolerance: {type: float, min: 0}
    predicted_order: {type: string}
    empirical_order: {type: string}
    ordering_match: {type: bool}
    a3_status: {type: string, allowed: [pass, fail, ambiguous, diagnostic]}
    pass_label: {type: string, allowed: [directionally_sensitive_pass, frobenius_proxy_only, fail, ambiguous, diagnostic]}

cdev_true_vs_learned.csv:
  format: csv
  level: 2
  row_matching_key: [problem_cell, method, budget, pair_id]
  columns:
    problem_cell: {type: string}
    method: {type: string}
    budget: {type: int, min: 1}
    pair_id: {type: string}
    e_C: {type: float, min: 0}
    relative_weighted_generator_error_max: {type: float, min: 0}
    support_F1: {type: float, min: 0, max: 1}
    support_F1_min: {type: float, min: 0, max: 1}
    e_Sigma_C: {type: float, min: 0}
    secondary_relative_frobenius_error_max: {type: float, min: 0}
    delta_rank_C: {type: float, min: 0}
    rho_C: {type: float, min: 0}
    active_pair: {type: bool}
    c1_recovery_pass: {type: bool}
    c2_decision_pass: {type: bool}
    c3_interpretation:
      type: string
      allowed: [noise_learning_failure_not_pullback_failure, pullback_or_sampling_model_failure, finite_sample_covariance_estimation_limited, GRI_distributional_assumption_limited]
      allow_empty_if_a3_status: [pass, diagnostic]
    a3_status_from_cdev: {type: string, allowed: [pass, noise_learning_limited, theory_or_model_limited, inconclusive, empirical_fallback_only, diagnostic]}

gri_calibration_table.csv:
  format: csv
  level: 2
  row_matching_key: [method, budget]
  columns:
    method: {type: string}
    budget: {type: int, min: 1}
    R_gri: {type: float, min: 0, max: 1}
    R_emp: {type: float, min: 0, max: 1}
    delta_gri: {type: float, min: 0}
    tau_R: {type: float, min: 0}
    gri_valid: {type: bool}

e1_static_decision_failure.csv:
  format: csv
  level: 2
  row_matching_key: [instance_id, budget]
  columns:
    instance_id: {type: string}
    budget: {type: int, min: 1}
    method_selected_MSE: {type: string}
    method_selected_DA: {type: string}
    R_dec_MSE: {type: float, min: 0, max: 1}
    R_dec_DA: {type: float, min: 0, max: 1}
    delta_R_static: {type: float}
    ci_lower_delta_R_static: {type: float}
    ci_upper_delta_R_static: {type: float}
    relative_failure_reduction: {type: float}
    claim1_min_relative_failure_reduction: {type: float, min: 0}
    regret_mean: {type: float, min: 0}
    n_paired_decisions: {type: int, min: 1}
    statistical_success: {type: bool}
    practical_success: {type: bool}

e2_dynamic_shots_to_success.csv:
  format: csv
  level: 2
  row_matching_key: [instance_id]
  columns:
    instance_id: {type: string}
    B_to_success_DA_0p8: {type: float, min: 0}
    B_to_success_MSE_0p8: {type: float, min: 0}
    delta_B_0p8: {type: float}
    ci_lower_delta_B_0p8: {type: float}
    ci_upper_delta_B_0p8: {type: float}
    shot_savings: {type: float}
    claim2_min_shot_savings: {type: float, min: 0}
    n_trajectories: {type: int, min: 1}
    statistical_success: {type: bool}
    practical_success: {type: bool}

e3_bstar_prediction.csv:
  format: csv
  level: 2
  row_matching_key: [problem_cell, pair_id]
  columns:
    problem_cell: {type: string}
    pair_id: {type: string}
    B_star_pred: {type: float, min: 0}
    B_star_lo: {type: float, min: 0}
    B_star_hi: {type: float, min: 0}
    B_star_obs: {type: float, min: 0}
    W_star: {type: float, min: 0}
    A3_pullback_gate: {type: string, allowed: [pass, fail, ambiguous, diagnostic]}
    directional_ordering_pass: {type: bool}
    claim3_level: {type: string, allowed: [3A, 3B, 3C]}

regime_frontier.csv:
  format: csv
  level: 2
  track: optional_9p5
  row_matching_key: [problem_cell, method_pair, regime_axis, grid_point]
  columns:
    problem_cell: {type: string}
    method_pair: {type: string}
    regime_axis: {type: string}
    grid_point: {type: float}
    predicted_DA_advantage: {type: float}
    observed_DA_advantage: {type: float}
    predicted_win_region: {type: bool}
    observed_win_region: {type: bool}
    frontier_error: {type: float, min: 0}
    derived_before_confirmatory: {type: bool}
    track95_support: {type: string, allowed: [supportive, diagnostic, fail]}

e4_power_sensitivity_audit.csv:
  format: csv
  level: 2
  row_matching_key: [problem_cell, budget]
  columns:
    problem_cell: {type: string}
    budget: {type: int, min: 1}
    mse_failure_rate: {type: float, min: 0, max: 1}
    raw_failure_rate: {type: float, min: 0, max: 1}
    n_effective_paired_decisions: {type: int, min: 1}
    delta_R_static_ci_width: {type: float, min: 0}
    delta_B_0p8_ci_width: {type: float, min: 0}
    epsilon_opt_sensitivity_status: {type: string, allowed: [pass, fail, diagnostic]}
    regime_status: {type: string, allowed: [usable, too_easy, too_hard, underpowered]}

method_tuning.csv:
  format: csv
  level: 2
  row_matching_key: [problem_cell, budget, method_family]
  columns:
    problem_cell: {type: string}
    budget: {type: int, min: 1}
    method_family: {type: string, allowed: [ZNE, CDR, PEC, other]}
    accuracy_tuned_method: {type: string}
    decision_tuned_method: {type: string}
    R_accuracy_tuned: {type: float, min: 0, max: 1}
    R_decision_tuned: {type: float, min: 0, max: 1}
    delta_R_decision_minus_accuracy: {type: float}
    ci_upper_delta_R: {type: float}
    method_tuning_effect: {type: string, allowed: [decision_tuning_helps, no_difference, accuracy_tuning_helps, inconclusive]}

gri_vs_empirical.csv:
  format: csv
  level: 2
  required_if: core_GRI_valid
  row_matching_key: [problem_cell, budget]
  columns:
    problem_cell: {type: string}
    budget: {type: int, min: 1}
    method_selected_GRI: {type: string}
    method_selected_empirical: {type: string}
    selector_agreement: {type: bool}
    R_GRI_selector: {type: float, min: 0, max: 1}
    R_empirical_selector: {type: float, min: 0, max: 1}
    delta_R_GRI_minus_empirical: {type: float}
    ci_upper_delta_R: {type: float}
    conclusion: {type: string, allowed: [GRI_matches_empirical, GRI_worse, GRI_better, inconclusive, not_applicable]}

focal_lower_bound.csv:
  format: csv
  level: 2
  track: secondary
  row_matching_key: [problem_cell, method_pair, budget]
  columns:
    problem_cell: {type: string}
    method_pair: {type: string}
    budget: {type: int, min: 1}
    lower_bound: {type: float}
    observed_gap: {type: float}
    bound_satisfied: {type: bool}
    figure_panel: {type: string}

secondary_optimizers.csv:
  format: csv
  level: 2
  track: robustness_only
  required_if: secondary_optimizers_included_in_manuscript
  row_matching_key: [problem_cell, optimizer, selector, budget]
  columns:
    problem_cell: {type: string}
    optimizer: {type: string, allowed: [SPSA, COBYLA]}
    selector: {type: string, allowed: [MSE, DA]}
    budget: {type: int, min: 1}
    same_stopping_rule: {type: bool}
    success_probability: {type: float, min: 0, max: 1}
    final_regret_mean: {type: float, min: 0}
    best_seen_regret_mean: {type: float, min: 0}
    robustness_status: {type: string, allowed: [same_sign_support, contradicts_primary, inconclusive, not_applicable]}

common_mode.csv:
  format: csv
  level: 2
  row_matching_key: [problem_cell, method, budget, perturbation_id]
  columns:
    problem_cell: {type: string}
    method: {type: string}
    budget: {type: int, min: 1}
    perturbation_id: {type: string}
    common_mode_variance: {type: float, min: 0}
    ambient_MSE_change: {type: float}
    decision_risk_change: {type: float}
    pass_common_mode_invariance: {type: bool}

mse_enough.csv:
  format: csv
  level: 2
  row_matching_key: [problem_cell, condition_id, budget]
  columns:
    problem_cell: {type: string}
    condition_id: {type: string}
    budget: {type: int, min: 1}
    condition_type: {type: string, allowed: [isotropic_gap_noise, common_scalar_covariance, affine_positive_residual, decision_irrelevant_variance, other]}
    mse_order: {type: string}
    decision_order: {type: string}
    orders_match: {type: bool}
    conclusion: {type: string, allowed: [MSE_enough_in_restricted_case, MSE_not_enough, diagnostic]}

affine.csv:
  format: csv
  level: 2
  row_matching_key: [problem_cell, method, transform_id]
  columns:
    problem_cell: {type: string}
    method: {type: string}
    transform_id: {type: string}
    alpha: {type: float}
    c: {type: float}
    alpha_positive: {type: bool}
    argmin_preserved: {type: bool}
    ambient_MSE: {type: float, min: 0}
    decision_failure_changed: {type: bool}

hardware_sigma_microcell.csv:
  format: csv
  level: 3
  row_matching_key: [backend_id, epoch_id, problem_cell, method, budget, gap_id]
  columns:
    backend_id: {type: string}
    epoch_id: {type: string}
    problem_cell: {type: string}
    method: {type: string}
    budget: {type: int, min: 1}
    gap_id: {type: string}
    sigma_pred: {type: float, min: 0}
    sigma_hat: {type: float, min: 0}
    ci_lower_sigma_hat: {type: float, min: 0}
    ci_upper_sigma_hat: {type: float, min: 0}
    relative_error: {type: float, min: 0}
    microcell_pass: {type: bool}
    allowed_language: {type: string, allowed: [device_level_microcell_only, no_device_level_language, inconclusive_stress_test]}

hardware_ordering.csv:
  format: csv
  level: 3
  row_matching_key: [backend_id, epoch_id, problem_cell, budget_label]
  columns:
    backend_id: {type: string}
    epoch_id: {type: string}
    problem_cell: {type: string}
    budget_label: {type: string, allowed: [below_crossing, near_crossing, above_crossing, other]}
    budget: {type: int, min: 1}
    predicted_order: {type: string}
    observed_order: {type: string}
    ordering_match: {type: bool}
    minimum_detectable_ordering_flip: {type: float, min: 0}
    powered_for_directional_ordering: {type: bool}
    allowed_language: {type: string, allowed: [directionally_consistent_budget_dependent_ordering, locally_consistent_at_crossing_budget, inconclusive_stress_test, external_validity_limited]}

e5_claim_survival_table.csv:
  format: csv
  level: 2
  row_matching_key: [claim_id]
  columns:
    claim_id: {type: string, allowed: [Claim1, Claim2, Claim3A, Claim3B, Gate0, A3, GRI, HardwareSigma, HardwareOrdering]}
    statistical_success: {type: bool}
    practical_success: {type: bool}
    allowed_language: {type: string}
    forbidden_language_triggered: {type: bool}
```

## Claim Adjudication Outputs

Because the experimental plan is a PAP, the prediction and claim adjudication is
a canonical output.

Required file:

```text
results/claim_adjudication_table.csv
```

Minimum schema:

```yaml
claim_adjudication_table.csv:
  format: csv
  level: 2
  row_matching_key: [claim_id]
  columns:
    claim_id:
      type: string
      allowed: [Claim1_static_failure, Claim2_shots_to_success, Claim3A_bstar, Claim3B_directional_ordering, Gate0_full_vs_diagonal, A3_pullback, GRI_calibration, HardwareSigma, HardwareOrdering]
    precondition_status:
      type: string
      allowed: [pass, fail, not_run, not_applicable]
    estimate:
      type: float
      allow_nan_if_status: [not_run, not_applicable]
    ci_lower:
      type: float
      allow_nan_if_status: [not_run, not_applicable]
    ci_upper:
      type: float
      allow_nan_if_status: [not_run, not_applicable]
    practical_threshold:
      type: string
    statistical_verdict:
      type: string
      allowed: [CONFIRM, REFUTE, INCONCLUSIVE, NOT_APPLICABLE]
    practical_verdict:
      type: string
      allowed: [PASS, FAIL, INCONCLUSIVE, NOT_APPLICABLE]
    allowed_language:
      type: string
```

`verify.py` must enforce:

- Claim 2 is the first gate in the primary family.
- Claim 1 cannot be headline if Claim 2 fails.
- Claim 1 statistical success requires `ci_upper_delta_R_static < 0`; practical
  success requires `relative_failure_reduction >= 0.15`.
- Claim 2 statistical success requires `ci_upper_delta_B_0p8 < 0`; practical
  success requires `shot_savings >= 0.20`.
- Gate 0 passes only if the full kernel changes GRI, selector, or `B_star`
  prediction by the frozen margin; a diagonal-only or no-trigger result forbids
  physical covariance language.
- A3 `pass` requires active pairs to satisfy
  `projected_error_over_tolerance < 1` and `ordering_match == true`; a
  Frobenius-only pass is diagnostic and cannot support Claim 3A/3B.
- Claim 3A requires `A3_pullback_gate == pass`, `W_star <= 0.5`, and the
  Cdev learned-versus-true arm not to mark A3 as noise-learning limited.
- Claim 3B requires `A3_pullback_gate == pass` and directional ordering.
- `device-level` title/headline requires hardware-Sigma micro-cell pass.
- Hardware directional ordering requires below/near/above budgets.
- If GRI is invalid in the core, GRI-based Claim 3 language is forbidden.
- If only amortized accounting wins, the primary claim is not allowed.
- E4 must mark `regime_status == usable` for primary cells; too-easy, too-hard,
  or underpowered cells cannot be used to claim a primary win.
- The required ablations `method_tuning.csv`, `full_vs_diagonal.csv`, and
  `shuffled_L.csv` must exist for every primary cell; `gri_vs_empirical.csv`
  must exist when core GRI is valid.
- `freeze_manifest.json` must contain Docker digest, config hashes, script
  hashes, PAP hash, pilot output hashes, and confirmatory script hashes before
  confirmatory reproduction is accepted.
- `regime_frontier.csv` and `focal_lower_bound.csv` are required only for a
  9.5-track or lower-bound figure claim; otherwise they must be marked
  `not_applicable` in the claim registry.
- `secondary_optimizers.csv` is required only if SPSA/COBYLA robustness appears
  in the manuscript; every included row must certify `same_stopping_rule == true`
  for DA and MSE.
- Hardware and control outputs must satisfy their explicit schemas before they
  can appear in figures, supplements, or claim-language checks.
- `claim_registry.yaml` must encode the absolute forbidden-language list from
  PAP §22 exactly, including: `DA always wins`, `MSE is useless`,
  `CDR/PEC generally worse/better`, `universal superiority`, and
  `saturates lower bound`.

## Tolerance Tiers

`verify.py` selects tolerances by level and by field role.

- **Level 1 deterministic core:** tight tolerances. These cover exact/synthetic
  gap-kernel, selector, budget, and verifier fixtures.
- **Level 2 simulation/Aer:** documented relaxed tolerances. These cover risk
  probabilities, crossing estimates, empirical success rates, covariance
  estimates, and CI endpoints under pinned seeds.
- **Level 3 hardware analysis:** tight tolerances for deterministic
  post-processing of archived counts, but no expectation that physical values
  are reproducible by re-running the device.

Every tolerance entry must include a one-line justification.

Tolerance registration policy:

- Calibrate Level 1 tolerances from at least three fast container runs.
- Calibrate Level 2 tolerances separately, with the Aer seed pinned.
- Use `max(observed_difference) * 10` as default safety factor.
- If observed difference is zero, use machine-level tolerance and document it.
- Do not increase tolerances simply to make a failed full run pass.
- Treat claim-critical verdict flips as failures even if individual numeric
  differences are small.

## Reference Data Update Policy

Reference data changes only when scientific outputs change.

Rules:

- Do not update reference data for formatting, logging, or documentation-only
  changes.
- Every reference update requires a commit message explaining why numerical
  values changed.
- If paper values change, create a new version tag.
- Hardware raw counts are never overwritten; a new hardware run creates new job
  ids and new archived files.
- `reference_manifest.json` records Git tag, commit, PAP hash, creation time,
  and per-file checksums.

## Execution Logging Policy

`run_all.py` should use Python `logging`, not raw `print()`.

Required behavior:

- Write logs to `results/run.log`.
- Use `ISO_TIMESTAMP | LEVEL | MODULE | MESSAGE`.
- Log each block start, finish, duration, and output hash.
- Log pre-flight checks.
- Log execution mode: clean, resumed, or restarted.
- Log level, stage, and experiment id.
- For hardware analysis, log job ids and epoch ids consumed.
- Record log path in `results/manifest.json`.

## Data Policy

The README must state:

### Archived in the Zenodo deposit

- canonical CSV/JSON outputs declared by the PAP and frozen configs;
- freeze manifests and PAP hash;
- claim adjudication and survival tables;
- figures;
- hardware raw counts, calibration snapshots, and job metadata;
- Docker image digest or build instructions.

### Recomputable

- Level 1 deterministic mini-regression outputs via `make reproduce-level1`;
- Level 2 simulation outputs via `make reproduce-full`;
- figures via `make figures`.

### Analysis-reproducible only

- Level 3 hardware outputs via `make analysis-from-hardware`.

The quantum device is never re-executed as part of reproduction.

## Platform Support

Supported platform: Docker on `linux/amd64`.

Native Windows, native macOS, and `linux/arm64` are development paths only.
Results may differ at the ULP level because BLAS/LAPACK implementations differ.

Out of scope:

- GPU reproduction;
- native Windows as official path;
- native macOS as official path;
- interactive notebooks as official path;
- future unpinned dependency versions;
- quantum hardware re-execution.

## Paper-to-code Mapping

The README should include a table mapping every paper claim, figure, and table to
code and verification outputs.

Template:

```markdown
| Paper element | PAP anchor | Source code | Output | Verification |
| --- | --- | --- | --- | --- |
| Static DA selector reduces decision failure | Claim 1, E1 | `experiments/e1_static_da_selector.py` | `results/confirmatory/e1_static_decision_failure.csv`, Fig. 2 | `verify.py` checks schema, CI, practical threshold |
| Dynamic shots-to-success | Claim 2, E2 | `experiments/e2_dynamic_batch_candidate_optimizer.py` | `results/confirmatory/e2_dynamic_shots_to_success.csv`, Fig. 3 | `verify.py` checks `B_DA(0.8) < B_MSE(0.8)` and savings |
| B-star prediction / directional ordering | Claim 3, E3 | `experiments/e3_bstar_prediction.py` | `results/confirmatory/e3_bstar_prediction.csv`, Fig. 4 | `verify.py` enforces 3A/3B/3C rules |
| Gate 0 full-vs-diagonal | PAP 5.0, 12.1.1 | `experiments/gate0_pilot_full_vs_diagonal.py` | `results/pilot/gate0_full_vs_diagonal.csv` | `verify.py` gates physical-covariance language |
| A3 pullback frontier | PAP 3.3.1, 16.1 | `experiments/a3_pullback_frontier.py`, `src/daqem/cdev.py` | `results/pilot/pullback_frontier.csv` | `verify.py` checks projected flip tolerance |
| A3 Gaussianity / Sigmahat audit | PAP 7.3, 7.4 | `experiments/a3_gaussianity_sigmahat_audit.py` | `results/pilot/a3_gaussianity.md`, `results/pilot/a3_sigmahat_audit.md` | Diagnostic, not canonical/reference |
| C_dev learned arm | PAP 16.1.0.1, 4.4.1 | `experiments/cdev_learned_arm.py`, `src/daqem/cdev.py` | `results/pilot/cdev_learned_arm.md` | Diagnostic, not canonical/reference |
| Accuracy-ZNE-only vs DA/Decision-ZNE-only tuning | PAP 12 | `experiments/ablation_method_tuning.py` | `results/ablations/method_tuning.csv` | `verify.py` checks method-tuning effect schema |
| GRI selector vs empirical-risk selector | PAP 12, PAP 7 | `experiments/ablation_gri_vs_empirical.py` | `results/ablations/gri_vs_empirical.csv` | Required when core GRI is valid |
| Regime frontier for 9.5 track | PAP 16.1.1 | `experiments/regime_frontier.py` | `results/pilot/regime_frontier.csv` | Required only for 9.5-track language |
| Focal lower bound | PAP 16.2 | `experiments/focal_lower_bound.py` | `results/secondary/focal_lower_bound.csv`, `figures/focal_lower_bound.pdf` | Required only if the lower-bound figure/claim is included |
| SPSA/COBYLA robustness | PAP 10.4 | `experiments/robustness_secondary_optimizers.py` | `results/robustness/secondary_optimizers.csv` | Required only if secondary optimizers are included; same stopping rule enforced |
| Controls | PAP 12, Appendix controls | `experiments/control_common_mode.py`, `experiments/control_mse_enough.py`, `experiments/control_affine.py` | `results/controls/*.csv` | `verify.py` checks control schemas before figures |
| Budget ledger fairness | PAP 4 | `src/daqem/budget.py` | `results/frozen/budget_ledger.csv` | `tests/test_budget_ledger.py`, `verify.py` arithmetic checks |
| Hardware-Sigma micro-cell | PAP 15.1.1 | `experiments/hardware_sigma_microcell_analysis.py` | `results/hardware/hardware_sigma_microcell.csv` | `verify.py` analysis-from-counts only |
```

Pilot traceability also includes the decision records
`STEP_3_decision_venue.md` and
`DECISION_DIFERIDA_F1cB_canal_heterogeneo.md`.

## Tests

Required tests:

```text
tests/
  test_a3_gaussianity_sigmahat_audit.py
  test_a3_pullback_frontier.py
  test_budget_ledger.py
  test_cdev_learning.py
  test_checkpoint.py
  test_contrast_matrix.py
  test_determinism.py
  test_e0_executability.py
  test_gap_kernel.py
  test_gri_risk.py
  test_qem_methods.py
  test_regression.py
  test_selector_logic.py
  test_verify.py
```

Responsibilities:

- `test_budget_ledger.py`: verifies `C_total` arithmetic and non-amortized
  comparison constraints.
- `test_contrast_matrix.py`: verifies `L 1 = 0`, frozen shape, and row ordering.
- `test_gap_kernel.py`: verifies `Sigma = L K L^T` and PSD handling.
- `test_gri_risk.py`: checks Gaussian risk against direct Monte Carlo on a fixed
  small cell.
- `test_selector_logic.py`: checks MSE and DA selector rules, fallback, and
  tie-breaking.
- `test_e0_executability.py`: checks executability gate logic, strict hardware
  flag parsing, and E0 schema behavior.
- `test_a3_pullback_frontier.py`: checks projected ranking error, flip
  tolerance, and the A3 frozen-before-Sigmahat boundary.
- `test_a3_gaussianity_sigmahat_audit.py`: checks joint bootstrap and
  GRI-vs-empirical calibration logic.
- `test_cdev_learning.py`: checks the implemented C_dev learning helpers and
  smoke-profile sparse basis.
- `test_checkpoint.py`: checks checkpoint/resume, atomic writes, and block
  fingerprint behavior.
- `test_qem_methods.py`: checks Richardson/ZNE coefficients and SOCP
  constraints.
- `test_determinism.py`: same Level 1 seed produces identical canonical outputs.
- `test_regression.py`: mini reference CSVs match.
- `test_verify.py`: verifier passes clean outputs and fails perturbed outputs.

The two most important tests are `test_determinism.py` and `test_verify.py`.
Without them, the reproduction package can silently drift or falsely pass.
`test_verify.py` should include at least:

- clean outputs pass;
- missing rows fail;
- extra columns fail;
- missing columns fail;
- `NaN`/`Inf` fails;
- type mismatch fails;
- budget-ledger arithmetic mismatch fails;
- freeze-manifest hash or Docker digest mismatch fails;
- missing required ablation output fails;
- missing same-stopping-rule certification fails when SPSA/COBYLA robustness is
  included;
- missing hardware/control schema fields fail when those outputs are included;
- claim-language violation fails;
- missing hardware counts fail for Level 3;
- Level 2 relaxed tier is used only for Level 2;
- missing PAP hash fails or hard-warns before computation.

## Randomness Policy

The PAP fixes:

```yaml
rng:
  library: numpy
  bit_generator: PCG64DXSM
  root_seed: 260616
  seed_derivation: hash(instance_id, method, budget, replicate_id, stream)
```

Implementation rules:

- Use `numpy.random.Generator(numpy.random.PCG64DXSM(seed))`.
- Do not use global `np.random.seed()` in the reproduction path.
- Derive seeds deterministically from named identifiers.
- Record seed derivation in `reproducibility/config/rng_policy.yaml`.
- Record bootstrap seeds separately.
- Record Aer seeds separately for Level 2.
- Record transpiler seeds for any hardware-generated archive.

## Continuous Integration

CI should run the fast reproduction path inside Docker.

CI checks:

- package installation;
- unit tests;
- fast Level 1 reproduction;
- verification against committed small reference outputs;
- no cloud account required;
- no hardware archive required unless a small schema fixture is included.

The full Level 2 grid and Level 3 hardware analysis do not need to run in CI.

Recommended workflow behavior:

- build Docker image;
- run `make reproduce-fast`;
- run `make test`;
- upload `ci-results/` on failure;
- run `pip-audit` as advisory only.

## When Verification Fails

Triage guide:

```text
Verification failure
+-- Missing PAP hash or freeze artifact
|   +-- Check PAP_HASH.txt and freeze_manifest.json.
+-- Budget ledger failure
|   +-- Recompute C_total columns and check non-amortized vs amortized flags.
+-- Gate0 status changed
|   +-- Check contrast matrix, GRI code, and mini-regression reference.
+-- A3 projected error/tolerance changed
|   +-- Check Sigma_pred, Sigma_hat, gradient perturbation scale, PSD handling.
+-- GRI calibration failure
|   +-- Check seeds, empirical risk table, MVN probability backend.
+-- Claim survival changed
|   +-- Check gate statuses and claim-language rules before changing results.
+-- Level 2 tolerance exceeded slightly
|   +-- Check Aer seed and dependency versions.
+-- Level 2 tolerance exceeded strongly
|   +-- Treat as potential scientific/code discrepancy.
+-- Hardware analysis failure
|   +-- Check raw-count checksums, job metadata, calibration snapshot, epoch map.
+-- Figure checksum differs
|   +-- Verify underlying numerical data; figure PDFs are not bit-identical targets.
```

## Versioning Policy

Use explicit Git tags:

```text
v1.0.0-initial-submission
v1.0.1-initial-submission-fix
v1.1.0-revision-1
v1.2.0-revision-2
```

Rules:

- `v1.0.0` accompanies the first submitted manuscript.
- Patch versions fix code/docs without changing reported numerical values.
- Minor versions change reported results, figures, tables, or responses.
- Major versions are for substantial rewrites.
- The manuscript cites the version-specific Zenodo DOI.

## Zenodo and GitHub Release Policy

The repository should include:

```text
CITATION.cff
.zenodo.json
LICENSE
LICENSE-DATA
```

Draft `.zenodo.json`:

```json
{
  "title": "Code and data for: Decision-Aware Quantum Error Mitigation",
  "creators": [
    {
      "name": "Apellido, Vicenzo",
      "orcid": "0000-0000-0000-0000"
    }
  ],
  "description": "Reproduction package for the numerical experiments, frozen pre-analysis plan, decision-kernel outputs, budget ledger, and archived hardware-count analysis accompanying the paper on decision-aware quantum error mitigation.",
  "license": "MIT",
  "upload_type": "software",
  "keywords": [
    "quantum error mitigation",
    "decision risk",
    "finite shots",
    "QAOA",
    "gap kernel",
    "quantum computing"
  ],
  "related_identifiers": []
}
```

Use MIT for code and CC-BY-4.0 for data/figures/hardware counts through
`LICENSE-DATA` and README data policy.

## Contributing Policy

`CONTRIBUTING.md` should state that this is a research reproduction artifact.

Issues reporting reproduction failures should include:

- Git tag;
- Docker image digest;
- execution level;
- `results/manifest.json`;
- `results/run.log`;
- generated output path;
- host platform.

Pull requests should be limited to documented bug fixes, reproducibility fixes,
or verifier/schema improvements.

## METHODS.md Content

Required sections:

1. Three-level reproduction architecture.
2. Candidate set and reference truth construction.
3. QAOA-MaxCut primary cell and optional VQE/portfolio robustness cells.
4. Noise families and parameter conventions.
5. QEM method definitions: Raw, Accuracy-ZNE, Decision-ZNE, optional CDR/PEC.
6. Contrast matrix construction and gap-kernel convention.
7. GRI computation and empirical fallback.
8. Gate 0 full-vs-diagonal.
9. A3 projected flip tolerance and risk-gradient estimation.
10. `C_dev^true` versus `C_dev^learned` gates C1/C2/C3.
11. Budget ledger and non-amortized accounting.
12. Required ablations: method tuning, full-vs-diagonal, shuffled `L`, and
    conditional GRI-vs-empirical selector.
13. Static decision failure endpoint.
14. Dynamic Batch Candidate Optimizer endpoint.
15. Secondary SPSA/COBYLA robustness, if included, with the same stopping rule
    for DA and MSE.
16. `B_star` prediction and 3A/3B/3C demotion rules.
17. Optional 9.5-track regime frontier and focal lower bound.
18. Bootstrap, CI, gatekeeping, and multiplicity.
19. RNG and seed derivation.
20. Hardware-Sigma micro-cell and hardware ordering carve-out.
21. Control outputs: common-mode, MSE-enough, and affine.
22. Claim-language registry, including PAP §22 absolute forbidden phrases.
23. Verification, tolerances, and limitations.

For Phase A, `METHODS.md` may be shorter but must document enough for
`reproduce-fast` and `verify` to be understood.

## Implementation Sequence

Recommended order:

| # | Phase | Task | Exit criterion |
|---|---|---|---|
| 1 | A | Create clean repo skeleton | Layout exists and imports work. |
| 2 | A | Add `pyproject.toml`, Dockerfile, Makefile, `.dockerignore`, `PAP_HASH.txt` | Docker build succeeds. |
| 3 | A | Implement `candidates.py`, `gap_kernel.py`, `risk.py`, `selectors.py`, `budget.py` | Core modules import without side effects. |
| 4 | A | Implement Level 1 mini fixtures for Gate 0, A3, GRI, selectors, budget ledger | `make reproduce-fast` writes outputs. |
| 5 | A | Implement schemas, tolerances, and minimal `verify.py` | Clean outputs pass; perturbed outputs fail. |
| 6 | A | Add core tests | Determinism and verifier tests pass. |
| 7 | A | Add minimal README and METHODS | Reviewer can run fast path. |
| 8 | A | Wire E0/E0.5 pilot artifacts | Pilot outputs are schema-valid. |
| 9 | A | Wire E1/E2/E3 small or partial confirmatory path | Confirmatory schemas are stable. |
| 10 | A | Generate reference outputs and reference manifest | `make verify` passes from clean Docker. |
| 11 | B | Implement full Level 2 QAOA/Aer simulation grid | `make reproduce-full` runs E1-E5. |
| 12 | B | Implement required ablations, controls, and robustness cells | Method-tuning, full-vs-diagonal, shuffled-`L`, conditional GRI-vs-empirical, and secondary outputs verify. |
| 13 | B | Implement `C_dev^learned` sparse PL interface and C1/C2/C3 reports | A3 failure modes are distinguishable. |
| 14 | B | Implement optional SPSA/COBYLA robustness path if included | Same stopping rule is certified and output schema verifies. |
| 15 | B | Implement hardware analysis-from-counts path | `make analysis-from-hardware` works from archive. |
| 16 | B | Implement optional 9.5 regime-frontier and focal-lower-bound outputs if claimed | 9.5-track or lower-bound language has canonical CSV/figure support. |
| 17 | B | Add checkpoint/resume and structured logs | Interrupted full run resumes. |
| 18 | B | Complete tests and CI | CI passes fast path inside Docker. |
| 19 | B | Calibrate tolerances from repeated container runs | `tolerances.yaml` has justifications. |
| 20 | B | Finalize Zenodo/GitHub release metadata | DOI and Git tag match manuscript. |

## Immediate Next Step

Start with Phase A steps 1-5:

1. create the clean repository skeleton;
2. add Docker/Makefile/PAP hash;
3. implement the core Level 1 modules for gap kernels, GRI, selectors, and
   budget ledger;
4. create mini reference fixtures for Gate 0 and A3;
5. implement `verify.py` with hard-fail semantics for schemas, budget ledger,
   claim language, and PAP/freeze hashes.

Do not start large Level 2 grids or hardware work before the fast path and
verifier are credible. The PAP is gate-driven; the reproduction package should
be gate-driven too.
