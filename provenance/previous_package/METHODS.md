# Computational reproduction of manuscript v39

## Scope and inputs

This package freezes the corrected scientific code and evidence used by v39.
`protocol.json` records the retrospective correction protocol. `inputs/` contains
the original primitive data and frozen protocol artifacts; `evidence/` preserves
the corrected and historical secondary analyses. `results/` is the scientific
reference, not a cache to be overwritten by the reviewer. New runs go outside the
package and carry their own source fingerprints, logs and output hashes.

The original experimental plan remains at code/EXPERIMENTAL_PLAN_v13_PRXQ.md,
with SHA-256 84317e348002dc98cffb18d8f340a382c0675846c6298852e7465c0097628101.
It is a historical anchor, not a claim that these corrections were preregistered.
The original reproduction plan and previous freeze are retained for comparison.

## Environment and random streams

Docker uses Python 3.12.10 on Linux amd64, with both stages pinned to the same
base-image digest. All scientific dependencies are pinned by version and Linux
wheel hash. Windows has its own recorded dependency list. Installing requires
network access; the validation run uses `--network none`. BLAS, OpenMP and MKL
are restricted to one thread per worker; the number of process workers is explicit.

The base RNG policy is root seed 260616, PCG64DXSM and SHA-256-derived streams
keyed by instance, method, budget, replicate and stream. Retrospective analyses
also use their explicitly frozen namespaces, recorded in protocol.json and the
producing code. The E1 split is the deterministic v19 10/10/20 split. E3 uses
20 training and 20 test replicates. FakeKolkata uses the fixed v20 namespace and
10 fit, 10 selection and 20 evaluation replicates. Bootstrap resampling is seeded.
E2 saves its complete generation identity, dependency versions, candidate angles
and per-round shot arrays; a changed identity cannot reuse those rounds.

## Numerical quantities and decisions

Primitive samples produce method means, gap covariances and covariance gradients.
The GRI calculation is a multivariate Gaussian probability approximation, with
the simulator mean convention specified by each endpoint. Method-specific means
and the fixed ideal-mean covariance diagnostic remain separate in E3.
Independent checks recompute primitive moments, covariance propagation,
directional derivatives, strict rational tie decisions and sample partitions.

Accuracy-ZNE rational coefficients preserve exact ties; the operational decision
rule, including tied competitors, is tested against integer objective sums.
All counts, selected methods, pass/fail labels and claim statuses must agree
exactly across a reproduction. Matching a floating tolerance cannot excuse a
decision flip. Negative tests deliberately alter these fields and must fail.

Floating comparison rules are in code/reproducibility/config/tolerances.yaml.
Level 1 requires exact canonical output bytes across three runs. Most Level 2
arithmetic uses absolute 1e-10 and relative 1e-8. Approximate CDF risks use the
original plan's absolute 1e-6 bound; a difference of two risks uses 2e-6 and its
half-difference uses 1e-6. Gradient/map fields use absolute 1e-9.

The calibration repeated 192 FakeKolkata scores three times on Linux: within-Linux
drift was zero, while the maximum Windows/Linux difference was 6.48863744e-7.
All samples and decisions were identical. The measurements are retained under
validation/linux_validation/. These bounds do not change the scientific estimator.

Ratios with inactive near-zero thresholds can have large absolute roundoff.
Independent verifiers validate the quotient equation and physical numerator;
cross-platform comparison checks those numerators and denominators separately,
with the CDF bound only on risk-derived denominators. Verdicts remain exact.

## Analysis stages and costs

E1 reconstructs fitting, selection, holdout decisions and full ledgers from the
archived primitive samples. E3 regenerates the classical density-model
probabilities and frozen predictions for 48 cells, then recomputes covariances,
contrasts and holdout comparisons. A3 rebuilds bootstrap covariance evidence and
calibration for 72 cases. C3 propagates learned-channel evidence and verifies its
sampling intervals and physical projected errors at the same tolerance.

E2's integrated stage aggregates saved trajectories and charges the union of
primitive acquisitions plus amortized static-selector training. The separate
shot replay verifies 25,600 round hashes, reconstructs their moments, checks
candidate angles and repeats all 1,280 trajectories and 15,360 selector-budget
outcomes. The fresh runner simulates missing rounds, saves their states atomically
and resumes valid rounds. Its default one-trajectory run is explicitly partial.

FakeKolkata repeats sampling, fitting, selection and costs from archived noisy
probability vectors on the documented fixed ten-qubit block. It does not
recompute every noisy density matrix in the default integrated command.
Hardware reprocesses archived counts and calibrations, classical predictions and
10,000 epoch-cluster bootstrap replicates. It does not rerun the quantum device.

CDR/PEC, noise, controls and learned-channel/ablation evidence receive independent
numerical checks. The affine CDR control and PEC effective-shot proxy retain their
documented interpretations. These checks are not fresh auxiliary acquisitions.

## Failure recovery and verification

Preflight checks the complete file inventory, every file hash, PAP anchor, exact
Python/dependency versions and a writable external destination. Python -O is
rejected because scientific assertions must be active. Output directories have
one writer. A root identity binds the run to the exact release and environment.

Blocks commit completion receipts only after expected outputs exist and hash
correctly. Repeating the command validates before reuse. A damaged block is
regenerated; a source change requires a new destination or explicit --restart,
which archives the prior files. Actual E1 recovery was tested by corrupting one
completed cell, rebuilding it and preserving an intact second cell unchanged.
Separate tests exercise interrupted writes and false completion records.

Ten numerical verifier jobs check the seven integrated stages and auxiliary
evidence. compare_release.py compares 305 scientific files with exact discrete
values. Five figures are regenerated from those tables. verify_manuscript.py
checks 30 numerical/descriptive assertions and the five figure-source mappings.
The shipped PDF is preserved; TeX compilation requires a separate TeX installation.

Execution logs include elapsed time and peak summed process RSS sampled every
250 ms; shared memory may be counted more than once. Do not treat this sum as
physical RAM consumption. The final report records the container and machine
resources used, rather than assuming a runtime on another computer.

## Remaining archival-release boundaries

The integrated offline analysis and archived-hardware route are executable.
Full fresh Level 2 generation of every retained simulation campaign in one
canonical run is a separate, still-open completion criterion of Phase B.
The GitHub workflow is prepared and its commands are tested locally; a remote CI
run, public tag, Zenodo version DOI and manuscript DOI update happen on publication.
Historical optional experiments absent from v39 are not added to the paper.
