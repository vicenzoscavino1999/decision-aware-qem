# Known Issues

## Frozen pilot epsilon-sweep branch

`experiments/e2_dynamic_batch_candidate_optimizer.py` contains a latent `NameError`
in the pilot `epsilon_sweep` profile around line 1387: the branch references
`build_candidate_landscape`, but the frozen helper name is
`landscape_for_instance`.

Scope:

- affects only re-running the pilot `epsilon_sweep` profile;
- does not affect the confirmatory `full` profile used for the published E2
  results;
- does not affect the archived confirmatory numbers, which were independently
  recomputed and verified through the public archive checks.

The file is part of the 52-file frozen set
(`freeze_hash=sha256:2AF91BE182897D9885C1F09816B3342BB64EB499B15B1212CB4ACD6D110E4026`),
so the typo is documented here rather than patched in place. A code fix should be
made only in a future documented re-freeze.
