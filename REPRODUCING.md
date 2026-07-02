# Reproducing The Package

This package is reproduced through the canonical Docker path:
`linux/amd64`, Python 3.12.4, a base image pinned by digest, and a Linux
lockfile installed with `pip --require-hashes`.

The pinned scientific core is:

```text
numpy==2.4.6
cvxpy==1.9.1
scipy==1.18.0
qiskit==2.4.2
qiskit-aer==0.17.2
matplotlib==3.11.0
```

## One Command

Build the image:

```bash
docker build --platform linux/amd64 -t daqem-repro:local .
```

Run the full public reproduction:

```bash
docker run --rm --platform linux/amd64 daqem-repro:local python scripts/reproduce_all.py
```

Equivalent Makefile path inside the image:

```bash
docker run --rm --platform linux/amd64 daqem-repro:local make reproduce-all
```

Expected final line:

```text
REPRODUCE_ALL_PASS: Level 1 exact, determinism, tests, freeze audit, confirmatory verification, extension verification, hardware archive, hardware analysis, and figures completed
```

## What This Checks

The umbrella command performs, fail-fast:

1. Level-1 reproduction and exact verification against `reproducibility/reference_level1/`.
2. Level-1 determinism across three independent temporary output directories.
3. The full test suite; platform-specific skips are allowed only when explicitly marked.
4. Freeze audit: 52/52 frozen files intact.
5. Confirmatory verification from `reproducibility/reference_confirmatory/`.
6. Extension verification from `reproducibility/reference_extension/`.
7. Hardware-archive checksum and completeness verification from `reproducibility/hardware/`.
8. Level-3 hardware analysis recomputed from archived raw counts, with no device access.
9. Regeneration of the 5 data-driven manuscript figures from archived data.

Typical runtime is about 10-20 minutes including the Docker build, depending on
network and CPU.

## Clean Clone Validation

The end-to-end reviewer clone test is recorded in
`reproducibility/REVIEWER_CLONE_RESULT.md`. It copies the repository to a fresh
directory outside the working tree, excludes `figures/`, builds Docker from that
copy, and confirms that `scripts/reproduce_all.py` regenerates all five figures.
The current GitHub workflow repeats the canonical Docker reproduction on every
push and pull request to `main`.

## Cross-Platform Note

Docker is the canonical platform. Outside Docker, use the same lockfile and the
deterministic environment variables from the Dockerfile. Exact byte identity of
floating-point CSVs is not treated as a cross-platform contract where BLAS/solver
ULPs can differ; the verifier applies the registered Level-1/Level-2 tolerances
for numerical files while still checking exact hashes for frozen artifacts and
non-floating outputs.
