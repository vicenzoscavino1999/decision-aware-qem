# Reviewer Clone Result

Date: 2026-06-29

Clone path:

```text
C:\Users\Vicenzo\AppData\Local\Temp\daqem_reviewer_clone_20260629_075947
```

Copy exclusions:

```text
.venv-aer/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
figures/
tmp/
reviewer_clone/
scratchpad/
```

The clone was outside `D:\paper fisica 5`, so no recursive self-copy was possible.
`figures/` was intentionally excluded from the copy.

Fresh Docker image built from the clone:

```text
daqem-reviewer-clone:test sha256:98c5f0bc586709da6a143064fa37bab5052ff064b249d924006e1e338bf6b0fa
```

Turnkey command run in the cloned package:

```text
docker run --rm --platform linux/amd64 daqem-reviewer-clone:test python scripts/reproduce_all.py
```

Result:

```text
VERIFY PASS
DETERMINISM CHECK: files=3 mismatches=0
157 passed, 3 skipped, 24 warnings
FREEZE AUDIT PASS: 52/52 intact, freeze_hash=sha256:2AF91BE182897D9885C1F09816B3342BB64EB499B15B1212CB4ACD6D110E4026
CONFIRMATORY VERIFY PASS
EXTENSION VERIFY PASS
FIGURES PASS: generated=5
REPRODUCE_ALL_PASS: Level 1 exact, determinism, tests, freeze audit, confirmatory verification, extension verification, and figures completed
```

Figure regeneration check:

```text
FIGURES_ABSENT_AT_IMAGE_START
FIGURES PASS: generated=5
wrote=figures/F1_accuracy_decision_separation.pdf
wrote=figures/F3_dynamic_success.pdf
wrote=figures/F4_e1_epsilon_terciles.pdf
wrote=figures/F5_e3_directional_ordering.pdf
wrote=figures/F6_gate0_full_vs_diagonal.pdf
```

Conclusion: the reviewer clone test passed. A fresh copy without `figures/`
successfully built Docker, reproduced Level 1, passed determinism, tests, freeze
audit, confirmatory verification, extension verification, and regenerated the five
paper figures from archived data.
