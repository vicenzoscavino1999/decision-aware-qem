# Decision-Aware Quantum Error Mitigation

This repository is the reproduction package for a finite-shot quantum error
mitigation study on decision kernels: the objects that determine whether a noisy
estimator preserves the optimizer or ranking decision, not only its pointwise
accuracy. The package contains the frozen pre-analysis design, deterministic
core code, pilot and confirmatory runners, archived outputs, and verification
scaffolding. This README is result-neutral: it documents how the pipeline is
reproduced, not which claims pass.

## Current Status

The frozen design is content-hashed in `results/frozen/freeze_manifest.json`.
The current codebase is not a git repository; integrity is enforced by file
checksums and `PAP_HASH.txt`.

The implemented turnkey orchestration is currently limited to Level 1:

```powershell
.\.venv-aer\Scripts\python.exe -m pip install -e .
.\.venv-aer\Scripts\python.exe reproducibility\run_all.py --mode fast --level 1
.\.venv-aer\Scripts\python.exe reproducibility\verify.py --reference reproducibility\reference\
```

The scientific Level 2 confirmatory pipeline exists as direct experiment
scripts under `experiments/`, but it is not yet integrated into a single
turnkey `run_all.py --level 2` workflow. That integration is deferred to the
next reproducibility phase.

## Reproduction Levels

| Level | Purpose | Current route |
|---|---|---|
| Level 1 | Deterministic core and mini regression fixtures: contrasts, gap kernels, GRI, selectors, budget ledger, verifier behavior. | Turnkey through `run_all.py --mode fast --level 1` and `make reproduce-fast`. |
| Level 2 | Aer simulation outputs for pilot and confirmatory QAOA/MaxCut studies. | Science scripts exist and have been run directly; full orchestration is pending. |
| Level 3 | Hardware analysis from archived counts and calibration snapshots. | Analysis-from-archive only; no hardware re-execution is part of reproduction. |

## Make Targets

The `Makefile` exposes the intended public interface, but not every target is
fully wired yet.

| Target | Status today |
|---|---|
| `make test` | Runs the test suite. |
| `make reproduce-fast` | Supported Level 1 route: runs `run_all.py --mode fast --level 1`, then `verify.py`. |
| `make reproduce-level1` | Equivalent Level 1 route using the default fast mode. |
| `make verify` | Not a standalone first command: it expects generated outputs and `results/manifest.json` to already exist and match `reproducibility/reference/`. |
| `make reproduce-pilot` | Target exists, but current `run_all.py` only implements the fast/Level-1 subset. It is not the full pilot Level 2 workflow. |
| `make reproduce-confirmatory` | Aspirational until Level 2 orchestration is added. Confirmatory science currently runs via direct `python -m experiments.*` commands. |
| `make reproduce-full` | Aspirational. `run_all.py` raises `NotImplementedError` outside `--mode fast --level 1`. |
| `make analysis-from-hardware` | Aspirational until the Level 3 archive path is implemented. Hardware is never re-executed. |

## Recompute vs Archive Verification

Some blocks are cheap to recompute once the expensive simulation artifacts are
archived. Others are expensive Aer or density-matrix generation blocks and are
better verified by checksum unless the reviewer explicitly wants to spend the
compute.

| Tier | Blocks | Current evidence |
|---|---|---|
| Recompute-cheap | Level 1 mini regressions; E1 aggregation and paired McNemar from archived raws; E3 directional analysis from frozen A3 predictions; E2 `B(0.80)` aggregation from per-instance trajectory CSVs. | Seconds to minutes once inputs are present. |
| Verify-from-archive-only by default | Confirmatory raw generation, A3 density-matrix prediction generation, and E2 trajectory generation. | Measured raw generation: 18,446.3 s (~5h07m). A3: 2,959.409 s (~49m19s). E1 aggregation: 112.655 s (~1m53s). E2 trajectory generation: 124,628.911 s (~34h37m), 32 instances at ~64.9 min per instance on average. |

Determinism is expected by design: RNGs derive from
`reproducibility/config/rng_policy.yaml` (`root_seed: 260616`, `PCG64DXSM`) and
the Dockerfile pins single-thread numerical defaults. At this stage, full-scale
byte-identical confirmation of the expensive confirmatory archive is a pending
archive task, not a completed claim.

## Paper-To-Code Scope For The PRR Paper

The original reproduction plan was written for a broader PRXQ experimental blueprint. The actual paper reproduced here is `decision_residual_fields_theory_v18`, whose computational content is scoped to the decision-kernel theory, E1/E2/E3, and the pre-experimental proof-of-mechanism protocol. The claim adjudication table is in `results/claim_adjudication_table.csv`.

| Paper component | PAP/manuscript anchor | Source code | Output/archive | Verification |
|---|---|---|---|---|
| Claim 1 / E1 static decision failure | Confirmatory static endpoint; B*=512; practical threshold 0.15 | `experiments/e1_static_da_selector.py` | `reproducibility/reference_confirmatory/e1/e1_static_decision_failure.csv`; `confirmatory_claims_summary.json` | `python scripts/verify_confirmatory.py`; adjudicated in `results/claim_adjudication_table.csv` |
| Claim 2 / E2 shots-to-success | Dynamic endpoint; B(0.80); PAP rule 2647 | `experiments/e2_dynamic_batch_candidate_optimizer.py` | `reproducibility/reference_confirmatory/e2/`; `confirmatory_claims_summary.json` | `python scripts/verify_confirmatory.py`; adjudicated as non-headline support because B(0.80) is not reached in aggregate |
| Claim 3B / E3 directional ordering | A3/3B directional endpoint; 3A crossing not applicable | `experiments/e3_bstar_prediction.py`; `experiments/a3_pullback_frontier.py` | `reproducibility/reference_confirmatory/e3/e3_pullback_frontier.csv`; `confirmatory_claims_summary.json` | `python scripts/verify_confirmatory.py`; 502/502 active-pair ordering matches |
| Gate 0 full-vs-diagonal | Pilot mechanism gate for decision covariance relevance | `experiments/gate0_pilot_full_vs_diagonal.py` | `results/pilot/gate0_full_vs_diagonal.csv` | Included as a precondition/mechanism row in `results/claim_adjudication_table.csv` |
| A3 pullback frontier | Pullback mechanism and directional prediction | `experiments/a3_pullback_frontier.py` | `results/pilot/pullback_frontier.csv`; `results/pilot/a3_frozen_prediction/` | Included as a precondition/mechanism row in `results/claim_adjudication_table.csv` |
| §1835 proof-of-mechanism | Pre-experimental coexistence protocol | `experiments/proof_of_mechanism_run.py`; `experiments/proof_of_mechanism_coexistence_table.py`; `src/daqem/cdr.py`; `src/daqem/pec.py` | `reproducibility/reference_extension/proof_of_mechanism/` | `python scripts/verify_extension.py`; CDR affine control plus PEC coexistence table |
| Budget ledger | Cost-accounting and matched-budget record | `src/daqem/budget.py`; freeze artifacts | `results/frozen/budget_ledger.csv`; `reproducibility/reference_level1/frozen/budget_ledger.csv` | `verify.py` for Level 1; manifest checksums for frozen artifacts |
| E4/E5, method-tuning/shuffled-L/GRI-vs-empirical ablations, R2/R3, regime-frontier 9.5, focal lower bound, secondary optimizers, hardware L3 | Broader PRXQ blueprint only | Stubs or deferred scripts may exist | No PRR claim output | Marked `NOT_APPLICABLE` in `results/claim_adjudication_table.md` |

## Data And Code Availability For PRR

The official reproducibility platform is Docker `linux/amd64` with the pinned Linux lockfile, including `numpy==2.4.6`, `cvxpy==1.9.1`, `scipy==1.18.0`, `qiskit==2.4.2`, and `qiskit-aer==0.17.2`.

Supported verification routes:

```sh
make reproduce-fast
python scripts/verify_confirmatory.py
python scripts/verify_extension.py
```

`make reproduce-fast` recomputes the deterministic Level-1 path and verifies against `reproducibility/reference_level1/`. `scripts/verify_confirmatory.py` verifies the archived E1/E2/E3 confirmatory results in `reproducibility/reference_confirmatory/`. `scripts/verify_extension.py` verifies the post-confirmatory extension archive in `reproducibility/reference_extension/`, including the §1835 proof-of-mechanism coexistence table.

The expensive Level-2 Aer trajectory outputs are archived rather than regenerated by default. Full regeneration is possible through the direct experiment scripts, but it is not the default PRR verification path.

## Docker

Docker is the official reproduction environment in the plan. The current
development Dockerfile is intentionally simple:

```powershell
docker build -t daqem-repro:0.1.0 .
docker run --rm daqem-repro:0.1.0 python -m pytest tests/ -q
docker run --rm daqem-repro:0.1.0 make reproduce-fast
```

The archival release should pin the base image by digest. The present
Dockerfile uses `python:3.12.4-slim` and sets:

```text
PYTHONHASHSEED=0
OMP_NUM_THREADS=1
MKL_NUM_THREADS=1
OPENBLAS_NUM_THREADS=1
```

Important packaging caveat: the current Dockerfile installs with
`pip install -e .`, so dependency resolution follows the bounds in
`pyproject.toml`; it does not install from `requirements-lock.txt` yet. That is
intentional for now. The committed lockfile was generated on Windows and
contains Windows-only NTLM authentication dependencies from the
`qiskit-ibm-runtime` chain (`sspilib`, `pyspnego`, `requests_ntlm`). On
`linux/amd64`, the same stack uses the GSSAPI/Kerberos path instead, so
`pip install -r requirements-lock.txt` is not expected to be portable as-is.
The correct reproducible pinning step is deferred to Phase B: regenerate the
lockfile inside a clean Linux container, then change the Dockerfile to install
from that Linux lockfile and build-verify the image. This environment has not
build-tested Docker; the `docker build` and `make reproduce-fast` examples
above are structural commands, not verified container-build results here.

## Native Windows Development

The validated local path uses the project virtual environment:

```powershell
cd "D:\paper fisica 5"
.\.venv-aer\Scripts\python.exe -m pip install -e .
.\.venv-aer\Scripts\python.exe -m pytest tests\ -q
.\.venv-aer\Scripts\python.exe reproducibility\run_all.py --mode fast --level 1
.\.venv-aer\Scripts\python.exe reproducibility\verify.py --reference reproducibility\reference\
```

Use native execution for development and inspection. Use Docker for the public
archival path once the Level 2 orchestration is complete.

## Citation and Licenses

Citation metadata is drafted in `CITATION.cff` and `.zenodo.json`. The title in
those files is a draft taken from the manuscript v18; it must be confirmed
before DOI minting or submission.

Code is licensed under MIT (`LICENSE`). Archived numerical outputs, figures,
counts, and related data are licensed under CC BY 4.0 (`LICENSE-DATA`).
