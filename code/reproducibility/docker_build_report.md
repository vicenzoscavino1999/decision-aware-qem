# Docker Build Report

Date: 2026-06-28

Scope: official Docker path check for `linux/amd64`. This report is additive and does not modify the frozen 49-file manifest.

## Docker Environment

```text
Client version: 27.5.1
Client OS/Arch: windows/amd64
Docker context: desktop-linux
Server: Docker Desktop 4.38.0 (181591)
Engine version: 27.5.1
Server OS/Arch: linux/amd64
```

Base image:

```text
python:3.12.4-slim@sha256:a3e58f9399353be051735f09be0316bfdeab571a5c6a24fd78b92df85bcb2d85
```

Built image:

```text
daqem-repro:local sha256:763e15e56cf87e04732b611ae03d53b676f153ab22a7c107e61b0fadf58e2cc3
```

## Build Result

Command:

```sh
docker build --platform linux/amd64 -t daqem-repro:local .
```

Result: PASS.

The build used the existing Dockerfile, which installs from `pyproject.toml` via `pip install -e .`. It did not install from the Windows-generated `requirements-lock.txt`.

## Fast Reproduction Check

Command:

```sh
docker run --rm --platform linux/amd64 daqem-repro:local sh -lc "python reproducibility/run_all.py --mode fast --level 1 && python reproducibility/verify.py --reference reproducibility/reference/ && pytest tests/ -q"
```

Result: FAIL at `verify.py`.

Exact output:

```text
VERIFY FAIL: reference/generated stage mismatch: pilot != level1
```

Interpretation: `run_all.py --mode fast --level 1` completed far enough for `verify.py` to run, but the generated manifest stage was `level1` while the checked reference expects `pilot`. Per the Docker task's fail-fast rule, the remaining Docker checks were not run after this failure.

`pytest tests/ -q` was not reached in this chained command.

## Linux Lockfile

`requirements-lock.linux.txt` was not generated in this run because the fast reproduction check failed at `verify.py`, and the task required stopping on build or verify failure.

Therefore no Windows-to-Linux package delta table was produced.

## L1 Determinism

The two-run Level-1 determinism check was not run because the Docker verify step failed first.

## Freeze Integrity

Frozen manifest check after the Docker build attempt:

```text
frozen_files=49
frozen_mismatches=0
freeze_hash=sha256:C25B4F0243F41C12F8AC685ADAF150E79E066D9910B4EEEF1707E0F9BA5A66EA
```

## Files Added Or Modified By This Docker Check

```text
.dockerignore
reproducibility/docker_build_report.md
```

`requirements-lock.linux.txt` was not created because execution stopped at the verify failure.

## Follow-up: Level-1 Reference And Clean Fast Path

Date: 2026-06-28

The earlier failure was a reference scope mismatch: `run_all.py --mode fast --level 1` generates `stage="level1"`, while `reproducibility/reference/manifest.json` is a pilot reference with `stage="pilot"`.

A new additive reference tree was generated inside the `linux/amd64` container and copied to:

```text
reproducibility/reference_level1/
```

The reference contains exactly the `level1` manifest and canonical outputs required by `verify.py`:

```text
frozen/budget_ledger.csv
level1/gate0_mini.csv
pilot/pullback_frontier.csv
manifest.json
.partial/checkpoint.json
reference_manifest.json
checksums.sha256
```

`Makefile` was updated so `reproduce-fast` and `reproduce-level1` use `reproducibility/reference_level1/`. The pilot and confirmatory targets were not changed.

Clean container command:

```sh
python reproducibility/run_all.py --mode fast --level 1 &&
python reproducibility/verify.py --reference reproducibility/reference_level1/
```

Result:

```text
VERIFY PASS
```

## Tests In The Official Image

Running the full chained command with tests:

```sh
python reproducibility/run_all.py --mode fast --level 1 &&
python reproducibility/verify.py --reference reproducibility/reference_level1/ &&
pytest tests/ -q
```

Result:

```text
VERIFY PASS
sh: 1: pytest: not found
```

This is a real Docker packaging finding: the current Dockerfile installs `pip install -e .` without the `dev` extra, so `pytest` is not present in the official image. No workaround was applied silently.

## Linux Lockfile

`pip freeze` inside the `daqem-repro:local` Linux container was written additively to:

```text
requirements-lock.linux.txt
```

Scientific package deltas versus the Windows lockfile:

| package | Windows lock | Linux lock |
|---|---:|---:|
| numpy | 2.4.6 | 2.5.0 |
| scipy | 1.18.0 | 1.18.0 |
| qiskit | 2.4.2 | 2.4.2 |
| qiskit-aer | 0.17.2 | 0.17.2 |

## Level-1 Determinism In Docker

Two independent fast Level-1 runs were executed inside the same `linux/amd64` container to separate output directories, and their canonical output file hashes were compared exactly.

```text
determinism_files=3
determinism_missing=0
determinism_mismatches=0
```

Result: PASS for canonical Level-1 outputs.

## Pinned Official Docker Image

Date: 2026-06-28

The Dockerfile was hardened to use the base image by digest and install from the Linux lockfile before installing the local package with `--no-deps -e .`.

Base image:

```text
python:3.12.4-slim@sha256:a3e58f9399353be051735f09be0316bfdeab571a5c6a24fd78b92df85bcb2d85
```

Built image:

```text
daqem-repro:pinned sha256:066fd42c556d5a2c2cdab262a0eba136f499b935691d5033b87363e3cc83aa9b
```

Pinned versions confirmed inside the image:

```text
numpy==2.5.0
cvxpy==1.9.2
scipy==1.18.0
qiskit==2.4.2
qiskit-aer==0.17.2
pytest==9.1.1
```

The Linux lockfile includes pytest and its direct support packages while preserving the core pins:

```text
pytest==9.1.1
pluggy==1.6.0
iniconfig==2.3.0
Pygments==2.20.0
```

## Pinned Fast Reproduction

Command:

```sh
python reproducibility/run_all.py --mode fast --level 1 &&
python reproducibility/verify.py --reference reproducibility/reference_level1/
```

Result:

```text
VERIFY PASS
```

## Pinned Test Suite

Command:

```sh
pytest tests/ -q
```

Result: FAIL.

Summary:

```text
6 failed, 154 passed, 24 warnings in 211.15s (0:03:31)
```

Failures:

```text
tests/test_confirmatory_wiring_b41.py::test_full_manifest_regeneration_matches_frozen_bytes_and_hash
  expected frozen manifest hash 71EE69F28807CF2D64A5E15D584B618C0D4D1588A7C706D7826B499D7E92BB60
  regenerated hash 48429DC0F2183681FFAE8DFDEDE1E9C8AD9BCC0E125A426526FD390B889785B4

tests/test_freeze_configs_b3.py::test_contrast_matrix_artifact_matches_gap_kernel_and_a3_dimensions
  FileNotFoundError: /app/results/pilot/a3_frozen_prediction/P001.npz

tests/test_freeze_manifest_b5.py::test_freeze_manifest_contains_explicit_freeze_file_list
  expected src/daqem/cdr.py in freeze manifest checksums

tests/test_verify_confirmatory.py::test_confirmatory_archive_verify_passes
tests/test_verify_confirmatory.py::test_confirmatory_verify_fails_on_corrupted_archive
tests/test_verify_confirmatory.py::test_confirmatory_summary_expected_targets
  archive_confirmatory_outputs.py failed because /app/results/confirmatory is not present in the clean image
```

No tolerances were changed and no frozen code was modified.

## Pinned Confirmatory Verification

Command:

```sh
python scripts/verify_confirmatory.py
```

Result:

```text
CONFIRMATORY VERIFY PASS
E1@512 paired_n=1920 b=165 c=63 failure_rate_MSE=0.463542 failure_rate_DA=0.410417
E3 active_pairs=502 ordering_matches=502 directional_match_fraction=1.000000
E2 reaches_0.80 DA=False MSE=False DA_instances=15 MSE_instances=14
```

This confirms that the archived confirmatory E1/E2/E3 results reproduce under the pinned `linux/amd64` Docker image using the Level-2 verifier.

## Official Docker Pin: numpy 2.4.6 / cvxpy 1.9.1

Date: 2026-06-28

Decision D1 switched the official Docker environment to the versions that produced the frozen Windows artifacts where possible:

```text
numpy==2.4.6
cvxpy==1.9.1
scipy==1.18.0
qiskit==2.4.2
qiskit-aer==0.17.2
pytest==9.1.1
```

Built image:

```text
daqem-repro:np246 sha256:c2c6f39e354b1c758ceb80a03dd8339545fa0f1211bc83787a2b939d338a92e3
```

The Level-1 reference was regenerated inside this image and copied to `reproducibility/reference_level1/`.

Clean fast reproduction inside the rebuilt image:

```sh
python reproducibility/run_all.py --mode fast --level 1 &&
python reproducibility/verify.py --reference reproducibility/reference_level1/
```

Result:

```text
VERIFY PASS
```

Full test suite inside the rebuilt image:

```text
6 failed, 154 passed, 24 warnings in 202.91s (0:03:22)
```

Effect of the numpy/cvxpy pin on the 6 known red tests:

| Failure bucket | Test(s) | Result after numpy 2.4.6 / cvxpy 1.9.1 |
| --- | --- | --- |
| B: confirmatory manifest byte hash | `test_confirmatory_wiring_b41.py::test_full_manifest_regeneration_matches_frozen_bytes_and_hash` | Still failing. Regenerated hash remains `48429DC0F2183681FFAE8DFDEDE1E9C8AD9BCC0E125A426526FD390B889785B4`, not frozen `71EE69F28807CF2D64A5E15D584B618C0D4D1588A7C706D7826B499D7E92BB60`. The pin alone does not restore byte identity. |
| A: missing pilot A3 artifact in clean Docker context | `test_freeze_configs_b3.py::test_contrast_matrix_artifact_matches_gap_kernel_and_a3_dimensions` | Still failing. `/app/results/pilot/a3_frozen_prediction/P001.npz` is not present in the clean image. |
| C: extension files not in old freeze manifest | `test_freeze_manifest_b5.py::test_freeze_manifest_contains_explicit_freeze_file_list` | Still failing. `src/daqem/cdr.py` is intentionally post-freeze and not in the C25B4F02 manifest. |
| A: missing confirmatory results in clean Docker context | `test_verify_confirmatory.py::{test_confirmatory_archive_verify_passes,test_confirmatory_verify_fails_on_corrupted_archive,test_confirmatory_summary_expected_targets}` | Still failing. `/app/results/confirmatory` is not present in the clean image, so the archive-from-results tests cannot run. |

Conclusion: the `numpy==2.4.6` / `cvxpy==1.9.1` pin makes the official fast reproduction path green, but it resolves none of the six known full-suite Docker failures by itself. The confirmatory manifest byte mismatch is not explained solely by the Linux numpy 2.5.0 drift.
