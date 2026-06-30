# Contributing

This repository is a research reproduction artifact. The primary goal is to
preserve the frozen numerical record while making reproduction failures easy to
diagnose.

## Reporting Reproduction Failures

Please include:

- Git tag or archive identifier used for the run.
- Docker image id or digest, if Docker was used.
- Operating system and architecture.
- Python version and whether the run was Docker or native.
- `results/manifest.json` or the relevant generated manifest.
- Complete command log, especially the first failing command and traceback.
- Whether `python scripts/verify_freeze.py` reports the frozen files intact.

## Pull Requests

Pull requests should be narrowly scoped to reproduction infrastructure:

- verifier fixes,
- schema fixes,
- packaging or Docker fixes,
- documentation clarifications for reproducibility,
- tests that cover reproduction behavior.

Scientific design changes, frozen-file edits, or output-changing changes require
an explicit documented re-freeze. Do not edit files listed in
`results/frozen/freeze_manifest.json` unless the change is part of such a
documented re-freeze.
