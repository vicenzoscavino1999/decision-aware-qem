# Accuracy, Decision Risk, and Sampling Cost in Quantum Error Mitigation

Code, measurement records and analyses for manuscript **v45**, packaged as software version **1.2.0**. The [article](decision_residual_fields_theory_v45.pdf) and [LaTeX sources](manuscript/main.tex) are included.

The main command recalculates the reported analyses from archived inputs, runs the numerical tests, regenerates five empirical figures, replays signed-PEC and E1-partition decisions, and checks their correspondence with the article. Hardware analysis uses the included counts.

**[Guía completa en español](docs/REPRODUCIR_ES.md)** · [Methods](docs/METHODS.md) · [Results map](docs/RESULTS.md) · [Optional runs and compilation](docs/OPTIONAL.md)

## 1. Build the environment

Extract the reproduction package or clone the repository. Open a terminal in the directory containing this README and Dockerfile. Start Docker with Linux containers, then run:

```sh
docker build --platform linux/amd64 -t daqem:1.2.0 .
```

The image fixes Python 3.12.10, its Linux amd64 base image and the scientific dependencies. Building requires an internet connection; the reproduction runs offline.

## 2. Run the reproduction

Create an output directory outside the package and set its absolute path.

**PowerShell:**

```powershell
New-Item -ItemType Directory -Force ../daqem-results | Out-Null
$repro = (Resolve-Path -LiteralPath '../daqem-results').Path
```

**Bash:**

```bash
mkdir -p ../daqem-results
repro="$(cd ../daqem-results && pwd)"
```

Run this command in either terminal:

```sh
docker run --rm --network none --platform linux/amd64 --mount "type=bind,source=$repro,target=/reports" daqem:1.2.0 --mode all --workers 8 --output /reports/run
```

`--workers 8` requests eight worker processes where supported; use `4` or `2` for a smaller machine. The process prints `ANALYSIS` and `SUPPLEMENT` progress messages. Completion is reported as `REPRODUCE_PASS: all`, with `status: complete` in `run/execution.json`.

## 3. Read the results

| Output, relative to `daqem-results/` | Contents |
|---|---|
| `run/tests.xml` | Numerical and orchestration test results. |
| `run/analysis/results/` | Recalculated main analyses. |
| `run/figures/` | Five regenerated empirical figures. |
| `run/reference_comparison.json` | Comparison with the included numerical references. |
| `run/supplements.json` | PEC, E1-partition and manuscript-check receipt, with report paths. |
| `run/execution.json` | Environment, completed steps and execution status. |

The [results map](docs/RESULTS.md) connects these files to the article. Figure 1 is an original TikZ schematic; Figure 2 is drawn in the article source. Both are included and can be rebuilt using the [compilation instructions](docs/OPTIONAL.md#4-compile-the-article-and-the-overview).

## Resume and optional runs

Repeat the same command to resume with the same package and environment. Completed analysis blocks are checked before reuse. Supplement checks run in a new working subdirectory, preserving earlier reports. To start independently, choose another output directory.

`--mode fast` runs the tests, three exact Level-1 repetitions and the main manuscript check. `--mode analysis` recalculates the seven main analyses and empirical figures. `--mode supplements` runs PEC, E1 partitions and all manuscript checks. `--mode all` combines them.

The [optional routes](docs/OPTIONAL.md) repeat E1 fitting, replay E2 from its separately distributed 4.76 GB shot archive, generate a new E2 instance, or compile the PDF. `external_data.json` identifies the E2 archive and its SHA-256. The main command does not require that additional archive.

## Citation and licenses

The optional E2 shot archive is available at [Zenodo (10.5281/zenodo.23607497)](https://doi.org/10.5281/zenodo.23607497).

Citation metadata is in [CITATION.cff](CITATION.cff); Zenodo metadata is in [.zenodo.json](.zenodo.json). Code is licensed under [MIT](LICENSE); numerical outputs, original figures and measurement data are covered by [CC BY 4.0](LICENSE-DATA), subject to notices in individual files.

[CONTRIBUTING.md](CONTRIBUTING.md) explains development and validation. `release_manifest.json` identifies the complete package; historical protocols and evidence retain their original hashes.
