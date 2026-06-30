# Reproducibility Status

## Freeze Provenance

The historical pre-registered ZNE anchor is:

```text
sha256:C25B4F0243F41C12F8AC685ADAF150E79E066D9910B4EEEF1707E0F9BA5A66EA
```

The current package freeze is:

```text
sha256:2AF91BE182897D9885C1F09816B3342BB64EB499B15B1212CB4ACD6D110E4026
```

The current freeze contains 52 files and includes the post-confirmatory extension
code. The controlled transition is documented in `STEP_7_refreeze_audit.md`.

Guardrail: frozen files are immutable unless a future re-freeze is explicitly
documented with old-to-new hashes and a reason.

## Canonical Commands

Full public reproduction:

```bash
docker build --platform linux/amd64 -t daqem-repro:local .
docker run --rm --platform linux/amd64 daqem-repro:local python scripts/reproduce_all.py
```

Individual verifiers:

```bash
python scripts/verify_freeze.py
python scripts/verify_confirmatory.py
python scripts/verify_extension.py
```

## Continuous Integration

`.github/workflows/reproduce.yml` defines the public CI entry point. Once the repository is pushed to GitHub, each push or pull request to `main` builds the canonical `linux/amd64` Docker image and runs `python scripts/reproduce_all.py`, failing unless `REPRODUCE_ALL_PASS` appears in the output. The workflow requires no quantum cloud account, no hardware, and no secrets.

## Artifact Map

Level-1 reference:

```text
reproducibility/reference_level1/
```

Confirmatory archive:

```text
reproducibility/reference_confirmatory/
```

Post-confirmatory extension archive:

```text
reproducibility/reference_extension/
```

Claim adjudication:

```text
results/claim_adjudication_table.csv
results/claim_adjudication_table.md
```

Frozen design artifacts:

```text
results/frozen/
```

Data-driven figures:

```text
figures/F1_accuracy_decision_separation.pdf
figures/F3_dynamic_success.pdf
figures/F4_e1_epsilon_terciles.pdf
figures/F5_e3_directional_ordering.pdf
figures/F6_gate0_full_vs_diagonal.pdf
```

The computed phase-diagram grid is retained as support data, not as a paper
figure:

```text
reproducibility/reference_extension/phase_diagram/grid.csv
reproducibility/reference_extension/phase_diagram/NOTE.md
```

## Figure Boundary

The package regenerates 5 data-driven figures. The analytic Eq. 1300 boundary and
schematic C1/C2-style explanatory drawings belong to the manuscript text and are
not part of the executable reproduction bundle.

## Release Boundary

Zenodo DOI minting and any registry/container digest publication are deferred to
final manuscript release. They are release logistics, not unresolved scientific
or numerical reproducibility claims.
