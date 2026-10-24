# Contributing

Use the pinned Docker environment in the README. Native development requires Python 3.12.10 and the operating-system dependency lock. Keep generated results outside the package.

After changing numerical code, run relevant tests and the full reproduction. Compare exact decisions and counts, applying documented field-specific tolerances to floating values. Do not change expected outputs merely to make a failing test pass.

Original protocols, scientific freeze and archived inputs retain their hashes. Scientific-reference changes require a documented transition and new verification. Packaging, documentation or orchestration changes require a refreshed `release_manifest.json` and validation of the resulting package.

For a reproduction issue, include the software version, operating system, Docker image identifier, command, `execution.json` and the failed-step log. Omit credentials and unrelated local files.

The optional pre-commit hook parses Python, JSON and YAML. Dependency auditing in CI is informative; the scientific environment remains pinned for numerical reproduction.
