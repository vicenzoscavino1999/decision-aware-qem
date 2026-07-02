# Decision-Aware Quantum Error Mitigation

This repository is the public reproduction package for the accompanying manuscript,
*Decision Kernels for Quantum Error Mitigation: Why Accuracy Gains Need Not Improve
Downstream Decisions*. It contains the frozen design and core implementation,
archived confirmatory and robustness results, hardware raw counts, deterministic
verification tools, and the five data-driven figures used by the manuscript. The
package verifies reported results without requiring quantum-cloud credentials.

## Quick Start

The canonical platform is Docker on `linux/amd64`, using a base image pinned by
digest and the hash-locked `requirements-lock.linux.txt`.

```bash
docker build --platform linux/amd64 -t daqem-repro:local .
docker run --rm --platform linux/amd64 daqem-repro:local python scripts/reproduce_all.py
```

Equivalent command inside the image:

```bash
make reproduce-all
```

The successful run ends with:

```text
REPRODUCE_ALL_PASS: Level 1 exact, determinism, tests, freeze audit, confirmatory verification, extension verification, hardware archive, hardware analysis, and figures completed
```

The workflow recomputes the deterministic Level-1 fixtures, performs a three-run
determinism check, runs the full test suite, audits the 52-file freeze, verifies the
confirmatory and extension archives, verifies and reanalyzes the hardware archive,
and regenerates the five figures. See [REPRODUCING.md](REPRODUCING.md) for the
command-by-command guide and [REPRODUCIBILITY_STATUS.md](REPRODUCIBILITY_STATUS.md)
for the artifact map.

## Reproduction Levels

| Level | Scope | Public route |
|---|---|---|
| Level 1 | Deterministic core fixtures for contrasts, gap kernels, GRI, selectors, budget accounting, and verifier behavior. | Recomputed exactly by `scripts/reproduce_all.py` or `make reproduce-fast`. |
| Level 2 | Qiskit Aer pilot, confirmatory E1/E2/E3, and numerical mechanism studies. | Expensive simulation outputs are archived; their checksums, endpoints, and derived tables are verified by `verify_confirmatory.py` and `verify_extension.py`. |
| Level 3 | Hardware covariance analysis from captured counts, calibration snapshots, and job metadata. | `make analysis-from-hardware`; verification never submits a hardware job. |

Full regeneration of the expensive Level-2 trajectories remains available through
the experiment-specific runners and checkpoints. It is not the default public path:
the recorded confirmatory raw generation, A3 prediction, and E2 trajectories require
approximately 5 hours, 49 minutes, and 35 hours, respectively.

## Make Targets

| Target | Current behavior |
|---|---|
| `make reproduce-all` | Canonical public workflow; runs all nine verification and regeneration steps. |
| `make test` | Runs the full test suite. |
| `make reproduce-fast` | Recomputes and verifies the fast Level-1 reference. |
| `make reproduce-level1` | Equivalent Level-1 route using the default fast mode. |
| `make verify-confirmatory` | Verifies archived E1/E2/E3 results. |
| `make verify-extension` | Verifies the numerical-extension archive. |
| `make analysis-from-hardware` | Verifies hardware raw counts and recomputes the Level-3 endpoint. |
| `make figures` | Regenerates the five data-driven manuscript figures. |
| `make determinism-check` | Runs a standalone exact two-run Level-1 comparison in fixed output directories; the canonical workflow uses three temporary runs. |
| `make check-env` | Runs the environment preflight only. |
| `make run` | Runs the default fast Level-1 generator without the complete umbrella verification. |
| `make verify` | Verifies an already generated compatible result tree against the original reference. |
| `make archive-confirmatory` | Maintainer utility; requires the complete host-side `results/confirmatory/` source tree. |
| `make reproduce-pilot` | Runs the legacy Level-1 pilot-stage fixture, not the full Level-2 pilot campaign. |
| `make reproduce-confirmatory` | Legacy compatibility target; not the supported confirmatory archive-verification route. |
| `make reproduce-full`, `make reproduce` | Legacy targets outside the supported public interface; use `make reproduce-all`. |
| `make check` | Runs tests plus the context-dependent `make verify` target. |

## Pre-Registered Robustness Studies

The primary confirmatory package remains anchored to the 52-file freeze. Additional
studies are isolated from that package, governed by hash-locked protocols, and
reported without changing the frozen E1/E2/E3 results.

| Study | Scope | Protocol record |
|---|---|---|
| Calibrated simulator mechanism check | Three-cell `FakeKolkataV2` check with Raw+REM added to the frozen method menu. | `DERISK_FAKEBACKEND_v1.md` (`6210C6F1`) |
| Calibrated device-noise evaluation | Blind C001--C048 pool under `FakeKolkataV2`, with matched budgets and paired replicates. | `DERISK_FAKEBACKEND_TIER1_v1.md` (`AA029CA5`) |
| Hardware covariance micro-cell | Four-qubit `ibm_marrakesh` pullback test; the first selected path stopped at its characterization gate. | `HARDWARE_SIGMA_MICROCELL_v1.md` (`734FC61A`) |
| Hardware covariance amendment | One blind path re-selection under a sealed amendment; no further hardware retry is part of the package. | `HARDWARE_SIGMA_MICROCELL_v1_1_AMENDMENT.md` (`934F0E4F`) |

Fake-backend studies are deterministically recomputable but relatively slow. Hardware
evidence is analysis-reproducible from `reproducibility/hardware/`: raw counts,
calibration snapshots, job metadata, and claim-language status are archived and
checksummed. Verification does not reconnect to the device.

## Paper-to-Code Map

| Manuscript component | Implementation | Canonical evidence | Verification |
|---|---|---|---|
| Static decision failure (E1) | `experiments/e1_static_da_selector.py` | `reproducibility/reference_confirmatory/e1/` | `scripts/verify_confirmatory.py` |
| Dynamic shots-to-success (E2) | `experiments/e2_dynamic_batch_candidate_optimizer.py` | `reproducibility/reference_confirmatory/e2/` | `scripts/verify_confirmatory.py` |
| Directional ordering (E3) | `experiments/e3_bstar_prediction.py`; `experiments/a3_pullback_frontier.py` | `reproducibility/reference_confirmatory/e3/` | `scripts/verify_confirmatory.py` |
| Covariance pre-check | `experiments/gate0_pilot_full_vs_diagonal.py` | `results/pilot/gate0_full_vs_diagonal.csv` | freeze and Level-1 checks |
| Pullback validation | `experiments/a3_pullback_frontier.py` | `results/pilot/pullback_frontier.csv` | confirmatory and freeze checks |
| Numerical mechanism check | `experiments/proof_of_mechanism_run.py`; `experiments/proof_of_mechanism_coexistence_table.py` | `reproducibility/reference_extension/proof_of_mechanism/` | `scripts/verify_extension.py` |
| Calibrated device-noise robustness | `experiments/derisk_fakebackend/` | archived result tables and sealed protocols | test suite and archive checks |
| Hardware covariance micro-cell | `experiments/hardware_sigma/`; `scripts/analysis_from_hardware.py` | `reproducibility/hardware/` | `scripts/verify_hardware_archive.py`; Level-3 reanalysis |
| Budget accounting | `src/daqem/budget.py` | `results/frozen/budget_ledger.csv` | Level-1 verifier and freeze audit |

Experiments listed as `NOT_APPLICABLE` in
`results/claim_adjudication_table.md` are beyond the scope of the accompanying
manuscript and are not implied by the public reproduction command.

## Data and Code Availability

The repository archives four complementary evidence sets:

- `reproducibility/reference_level1/`: deterministic Level-1 reference;
- `reproducibility/reference_confirmatory/`: E1/E2/E3 confirmatory archive;
- `reproducibility/reference_extension/`: numerical mechanism and robustness archive;
- `reproducibility/hardware/`: raw hardware counts, calibration records, and metadata.

Continuous integration builds the canonical Docker image and runs
`scripts/reproduce_all.py` on every push and pull request to `main`. Known frozen
limitations are documented in [KNOWN_ISSUES.md](KNOWN_ISSUES.md).

## Citation and Licenses

Citation metadata is provided in `CITATION.cff` and `.zenodo.json`. A
version-specific Zenodo DOI will be added to those files at release.

Code is licensed under MIT (`LICENSE`). Archived numerical outputs, figures,
counts, and related data are licensed under CC BY 4.0 (`LICENSE-DATA`).
