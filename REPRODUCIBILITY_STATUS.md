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

The current freeze contains 52 files. It was produced by a controlled transition
from `C25B4F02...` to `2AF91BE1...`: the original 49 frozen files remained
byte-identical and three already validated extension modules (`cdr.py`, `pec.py`,
and `structured_noise.py`) were added. The old hash remains the historical
pre-registration anchor; the current hash is the package-integrity anchor.

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
python scripts/verify_hardware_archive.py
python scripts/analysis_from_hardware.py
```

## Continuous Integration

`.github/workflows/reproduce.yml` is the public CI entry point. Each push or pull
request to `main` builds the canonical `linux/amd64` Docker image and runs
`python scripts/reproduce_all.py`, failing unless `REPRODUCE_ALL_PASS` appears in
the output. The workflow requires no quantum-cloud account, hardware access, or
secrets.

## Artifact Map

Level-1 reference:

```text
reproducibility/reference_level1/
```

Confirmatory archive:

```text
reproducibility/reference_confirmatory/
```

Numerical extension archive:

```text
reproducibility/reference_extension/
```

Hardware raw-count archive and calibration records:

```text
reproducibility/hardware/
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

Known limitations of frozen code are listed in `KNOWN_ISSUES.md`.

## Figure Boundary

The package regenerates 5 data-driven figures. The analytic Eq. 1300 boundary and
schematic C1/C2-style explanatory drawings belong to the manuscript text and are
not part of the executable reproduction bundle.

## Release Boundary

The next public release merges the additive robustness records, receives the
`v1.1.0` tag, and is then archived on Zenodo. DOI insertion and any published
container digest are release logistics, not unresolved numerical claims.
