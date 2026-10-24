# Reviewer Clone Result

Date: 2026-07-02

Clone path:

```text
C:\Users\Vicenzo\AppData\Local\Temp\daqem_reviewer_clone_20260702_154650
```

Clone construction and exclusions:

```text
git archive HEAD -> fresh directory outside D:\paper fisica 5
figures/ removed before Docker build

Excluded or absent from the reviewer copy:
.venv-aer/
.venv*/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
figures/
tmp/
reviewer_clone/
scratchpad/
```

The clone was outside `D:\paper fisica 5`, so no recursive self-copy was
possible. `figures/` was intentionally removed before building the image, so
the figure step verifies regeneration from archived data rather than copied
PDFs.

Fresh Docker image built from the clone:

```text
daqem-reviewer-clone:test sha256:79c3732cc4f7605b938e77264f56557f7113969eac47078e08b55651cae315db
```

Turnkey command run in the cloned package:

```text
docker run --rm --platform linux/amd64 daqem-reviewer-clone:test python scripts/reproduce_all.py
```

Key output:

```text
VERIFY PASS
DETERMINISM CHECK: files=3 runs=3 comparisons=2 mismatches=0
161 passed, 3 skipped, 24 warnings in 177.63s (0:02:57)
FREEZE AUDIT PASS: 52/52 intact, freeze_hash=sha256:2AF91BE182897D9885C1F09816B3342BB64EB499B15B1212CB4ACD6D110E4026
CONFIRMATORY VERIFY PASS
EXTENSION VERIFY PASS
HARDWARE ARCHIVE VERIFY PASS: files=17 raw_count_jobs=13 device_level_language_allowed=false
HARDWARE ANALYSIS PASS: label=failed_or_inconclusive epochs=10 output=/app/results/hardware_sigma_attempt2/level3_from_archived_counts.json
FIGURES PASS: generated=5
REPRODUCE_ALL_PASS: Level 1 exact, determinism, tests, freeze audit, confirmatory verification, extension verification, hardware archive, hardware analysis, and figures completed
```

Figure regeneration check:

```text
figures/ absent from reviewer clone before Docker build
FIGURES PASS: generated=5
wrote=figures/F1_accuracy_decision_separation.pdf
wrote=figures/F3_dynamic_success.pdf
wrote=figures/F4_e1_epsilon_terciles.pdf
wrote=figures/F5_e3_directional_ordering.pdf
wrote=figures/F6_gate0_full_vs_diagonal.pdf
```

Audit history:

- 2026-07-02 attempt 1 failed at `hardware archive` because `.dockerignore`
  excluded `reproducibility/hardware/raw_counts/` from the Docker image.
- 2026-07-02 attempt 2 passed `hardware archive` but failed at
  `hardware analysis` because `atol=1e-12` did not survive the Windows-to-Docker
  BLAS/solver drift in the archived Level-3 comparison. The measured maximum
  drift was `1.5e-11`, with no verdict flips, so the comparison tolerance was
  restored to `1e-9` and documented.

Conclusion: the reviewer clone test passed. A fresh tracked snapshot without
`figures/` successfully built Docker, reproduced Level 1, passed determinism,
tests, freeze audit, confirmatory verification, extension verification,
hardware archive verification, hardware re-analysis, and regenerated the five
paper figures from archived data.
