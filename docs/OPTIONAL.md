# Optional runs and compilation

Build the image and define `repro` as described in the [README](../README.md). Run the commands below from the package root, one at a time.

## 1. Refit all E1 partitions

Prepare a fresh directory containing the original inputs and unchanged fitting code:

```sh
docker run --rm --network none --mount "type=bind,source=$repro,target=/reports" --entrypoint python daqem:1.2.0 -B /app/prepare_optional.py e1-refit --output /reports/e1-refit
```

Then run:

```sh
docker run --rm --network none --mount "type=bind,source=$repro,target=/reports" --entrypoint python daqem:1.2.0 -B /reports/e1-refit/runner.py baseline --workers 8
docker run --rm --network none --mount "type=bind,source=$repro,target=/reports" --entrypoint python daqem:1.2.0 -B /reports/e1-refit/runner.py alternatives --workers 8
docker run --rm --network none --mount "type=bind,source=$repro,target=/reports" --entrypoint python daqem:1.2.0 -B /reports/e1-refit/runner.py analyze
docker run --rm --network none --mount "type=bind,source=$repro,target=/reports" --entrypoint python daqem:1.2.0 -B /reports/e1-refit/verify.py
docker run --rm --network none --mount "type=bind,source=$repro,target=/reports" --entrypoint python daqem:1.2.0 -B /reports/e1-refit/verify_close_scores.py
docker run --rm --network none --mount "type=bind,source=$repro,target=/reports" --entrypoint python daqem:1.2.0 -B /reports/e1-refit/report.py
```

The alternative fits progress to `960/960`; verification reports must say `PASS`. To resume fitting, repeat the interrupted `baseline` or `alternatives` command. Repeating a completed study uses a new directory.

## 2. Replay E2 from individual shots

This optional route requires `datos_E2_v3.zip` (4,763,777,177 bytes), identified in `external_data.json`. Obtain it with the data release. Its SHA-256 is:

```text
5f417c4afd27fd64cd11ce697fd78c763fbbb18f1c3881aff5c14a2ab0698882
```

Place that ZIP in `daqem-results/` and extract a checked copy:

```sh
docker run --rm --network none --mount "type=bind,source=$repro,target=/reports" --entrypoint python daqem:1.2.0 -B /app/prepare_optional.py e2-shots --archive /reports/datos_E2_v3.zip --output /reports/e2-input
docker run --rm --network none --mount "type=bind,source=$repro,target=/reports" --entrypoint python daqem:1.2.0 -B /app/code/scripts/replay_e2_archive.py --raw-root /reports/e2-input/datos_E2_v3/e2_full_pc_v2 --output /reports/e2-replay --workers 8
```

The replay checks 25,600 round files and reconstructs 1,280 trajectories. Completion prints `E2_ARCHIVE_REPLAY_PASS`; `e2-replay/report.json` records `status: complete`, `decisions: 15360` and `new_simulated_rounds: 0`. Allow disk space for both the ZIP and its extracted inputs.

## 3. Generate a new E2 instance

```sh
docker run --rm --network none --mount "type=bind,source=$repro,target=/reports" --entrypoint python daqem:1.2.0 -B /app/code/scripts/regenerate_e2.py --instance C001 --trajectories 40 --output /reports/e2-new/C001
```

This generates the 40 trajectories of `C001`. A complete campaign uses `C001`–`C032`, each with its own output directory. Repeat the same command to resume; the report distinguishes new and reused rounds. Simulation is substantially longer than analysis replay.

## 4. Compile the article and the overview

With Python 3.10+ and a LaTeX distribution on the host, make a separate build copy:

```sh
python prepare_optional.py manuscript --output ../daqem-paper-build
cd ../daqem-paper-build
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

The output is `daqem-paper-build/main.pdf`. Figure 1 is already included as a vector PDF. To regenerate it from TikZ, run these commands from `daqem-paper-build/`, then repeat the three article compilation passes:

```sh
cd figures
pdflatex -interaction=nonstopmode -halt-on-error F0_estimation_decision_cost.tex
cd ..
```

The standalone figure requires `standalone`, TikZ, `amsmath`, `amssymb`, `fontenc` and `lmodern`. Figure 2 is rebuilt with the article. Compiling in the separate directory preserves the source package's file manifest.
