FULL CORRECTED RELEASE SUITE
Run all tests, without a curated selection:
  python code/scripts/run_regression_tests.py --output-dir NEW_DIRECTORY
or use the root Docker entry point, reproduce.py --mode fast.

The historical Level 1/checkpoint/verifier infrastructure is integrated again.
The former skipped confirmatory archive assertions now test the corrected
E2/E3 records. Original assertions are retained in the previous release.
The suite includes corruption, incomplete-run, missing-output, decision-flip,
budget, numerical-core, pipeline, and physical-model regression checks.
