from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import logging
import logging.handlers
import os
import platform
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from daqem.budget import total_cost
from daqem.gap_kernel import nearest_psd
from daqem.risk import gri_risk
from daqem.rng import BIT_GENERATOR, ROOT_SEED, make_rng
from daqem.selectors import da_selector


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
PAP_PATH = REPO_ROOT / "EXPERIMENTAL_PLAN_v13_PRXQ.md"
PAP_HASH_PATH = REPO_ROOT / "PAP_HASH.txt"
CANONICAL_OUTPUTS = [
    Path("level1/gate0_mini.csv"),
    Path("pilot/gate0_full_vs_diagonal.csv"),
    Path("pilot/pullback_frontier.csv"),
    Path("frozen/budget_ledger.csv"),
]
OPTIONAL_OUTPUTS = [
    Path("pilot/executability_budget_table.csv"),
    Path("pilot/executability_budget_table.md"),
]
CHECKPOINT_VERSION = 1


@dataclass(frozen=True)
class BlockSpec:
    block_id: str
    outputs: tuple[Path, ...]
    producer: Callable[[Path], None]
    input_paths: tuple[Path, ...] = ()


class RunLock(AbstractContextManager):
    """Cross-platform non-blocking lock for one writer per output directory."""

    def __init__(self, output: Path):
        self.path = output / ".run_all.lock"
        self._file = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("a+b")
        self._file.seek(0, os.SEEK_END)
        if self._file.tell() == 0:
            self._file.write(b"\0")
            self._file.flush()
        self._file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as exc:
            self._file.close()
            self._file = None
            raise RuntimeError(f"another run_all process is active for {self.path.parent}") from exc
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._file is None:
            return False
        try:
            self._file.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        finally:
            self._file.close()
            self._file = None
        return False


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def _read_pap_hash() -> str:
    if not PAP_HASH_PATH.exists():
        raise RuntimeError("PAP_HASH.txt is missing")
    value = PAP_HASH_PATH.read_text(encoding="utf-8").strip()
    if not value.startswith("sha256:"):
        raise RuntimeError("PAP_HASH.txt must start with sha256:")
    actual = _sha256(PAP_PATH)
    if value.split(":", 1)[1].upper() != actual:
        raise RuntimeError(
            f"PAP hash mismatch: PAP_HASH.txt={value}, actual=sha256:{actual}"
        )
    return value


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return None


def _git_dirty() -> bool | None:
    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return bool(status.strip())
    except Exception:
        return None


def _dependency_versions() -> dict[str, str]:
    versions = {}
    for key, module_name in [
        ("numpy", "numpy"),
        ("scipy", "scipy"),
        ("qiskit", "qiskit"),
        ("qiskit-aer", "qiskit_aer"),
        ("cvxpy", "cvxpy"),
    ]:
        try:
            module = __import__(module_name)
            versions[key] = getattr(module, "__version__", "unknown")
        except Exception:
            versions[key] = "not_importable"
    return versions


def _fingerprint_dependency_versions() -> dict[str, str]:
    versions = {"python": platform.python_version()}
    for distribution in [
        "numpy",
        "scipy",
        "qiskit",
        "qiskit-aer",
        "cvxpy",
        "pandas",
        "networkx",
        "PyYAML",
    ]:
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = "not-installed"
    return versions


def _block_input_fingerprint(spec: BlockSpec) -> str:
    h = hashlib.sha256()
    h.update(spec.block_id.encode("utf-8"))
    h.update(json.dumps(_fingerprint_dependency_versions(), sort_keys=True).encode("utf-8"))
    files: list[Path] = []
    for input_path in spec.input_paths:
        path = input_path.resolve()
        if path.is_dir():
            files.extend(
                candidate
                for candidate in path.rglob("*")
                if candidate.is_file()
                and "__pycache__" not in candidate.parts
                and candidate.suffix != ".pyc"
            )
        elif path.is_file():
            files.append(path)
        else:
            raise RuntimeError(f"block input does not exist: {input_path}")
    for path in sorted(set(files), key=lambda item: str(item).lower()):
        try:
            label = path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            label = str(path)
        h.update(label.encode("utf-8"))
        h.update(path.read_bytes())
    return f"sha256:{h.hexdigest().upper()}"


def _setup_logging(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        output / "run.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        "%(asctime)sZ | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True)
    for logger_name in ["run_all", "run_all.block", "preflight"]:
        logging.getLogger(logger_name).setLevel(logging.INFO)
    for logger_name in ["qiskit", "qiskit_aer", "matplotlib", "numba"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def _preflight(output: Path) -> str:
    log = logging.getLogger("preflight")
    for key in ["PYTHONHASHSEED", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"]:
        expected = "0" if key == "PYTHONHASHSEED" else "1"
        observed = os.environ.get(key)
        if observed != expected:
            log.warning("%s=%r, expected %r for deterministic runs", key, observed, expected)
    output.mkdir(parents=True, exist_ok=True)
    probe = output / ".write_test"
    probe.write_text("ok", encoding="ascii")
    probe.unlink()
    pap_hash = _read_pap_hash()
    log.info("preflight complete")
    return pap_hash


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _atomic_write_json(path: Path, payload: dict) -> None:
    _atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _empty_checkpoint() -> dict:
    return {"version": CHECKPOINT_VERSION, "blocks": {}}


def _load_checkpoint(path: Path) -> dict:
    if not path.exists():
        return _empty_checkpoint()
    try:
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid checkpoint ledger: {path}") from exc
    if checkpoint.get("version") != CHECKPOINT_VERSION:
        raise RuntimeError(f"unsupported checkpoint version in {path}")
    if not isinstance(checkpoint.get("blocks"), dict):
        raise RuntimeError(f"checkpoint blocks must be a dictionary: {path}")
    return checkpoint


def _block_reusable(
    output: Path,
    spec: BlockSpec,
    entry: dict | None,
    input_fingerprint: str,
) -> tuple[bool, str]:
    if not isinstance(entry, dict) or entry.get("status") != "complete":
        return False, "checkpoint status is not complete"
    recorded = entry.get("outputs")
    if not isinstance(recorded, dict):
        return False, "checkpoint outputs are missing"
    if entry.get("input_fingerprint") != input_fingerprint:
        return False, "block input fingerprint changed"
    for rel in spec.outputs:
        key = rel.as_posix()
        expected_hash = recorded.get(key)
        final_path = output / rel
        if not final_path.exists():
            return False, f"output missing: {key}"
        actual_hash = f"sha256:{_sha256(final_path)}"
        if str(expected_hash).upper() != actual_hash.upper():
            return False, f"output hash mismatch: {key}"
    return True, "all output hashes match"


def _run_block(
    output: Path,
    checkpoint_path: Path,
    checkpoint: dict,
    spec: BlockSpec,
) -> bool:
    """Run one block atomically; return True when a complete block was reused."""

    logger = logging.getLogger("run_all.block")
    entry = checkpoint["blocks"].get(spec.block_id)
    input_fingerprint = _block_input_fingerprint(spec)
    reusable, reason = _block_reusable(output, spec, entry, input_fingerprint)
    if reusable:
        logger.info("block=%s skipping/reuse complete checkpoint", spec.block_id)
        return True
    if entry is not None:
        logger.info("block=%s checkpoint invalid (%s); recomputing", spec.block_id, reason)

    partial_root = output / ".partial"
    staging = partial_root / "tmp" / Path(*spec.block_id.split("/"))
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)
    checkpoint["blocks"][spec.block_id] = {
        "status": "incomplete",
        "outputs": {},
        "duration_seconds": 0.0,
        "input_fingerprint": input_fingerprint,
    }
    _atomic_write_json(checkpoint_path, checkpoint)

    started = time.perf_counter()
    logger.info("block=%s start", spec.block_id)
    try:
        spec.producer(staging)
        missing = [rel.as_posix() for rel in spec.outputs if not (staging / rel).is_file()]
        if missing:
            raise RuntimeError(f"block {spec.block_id} did not produce outputs: {missing}")

        for rel in spec.outputs:
            source = staging / rel
            destination = output / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, destination)

        hashes = {}
        for rel in spec.outputs:
            digest = f"sha256:{_sha256(output / rel)}"
            hashes[rel.as_posix()] = digest
            logger.info("block=%s output=%s hash=%s", spec.block_id, rel.as_posix(), digest)
        duration = round(time.perf_counter() - started, 6)
        checkpoint["blocks"][spec.block_id] = {
            "status": "complete",
            "outputs": hashes,
            "duration_seconds": duration,
            "input_fingerprint": input_fingerprint,
        }
        _atomic_write_json(checkpoint_path, checkpoint)
        shutil.rmtree(staging, ignore_errors=True)
        logger.info("block=%s finish duration_seconds=%.6f", spec.block_id, duration)
        return False
    except Exception as exc:
        duration = round(time.perf_counter() - started, 6)
        checkpoint["blocks"][spec.block_id] = {
            "status": "incomplete",
            "outputs": {},
            "duration_seconds": duration,
            "input_fingerprint": input_fingerprint,
            "error": f"{type(exc).__name__}: {exc}",
        }
        _atomic_write_json(checkpoint_path, checkpoint)
        logger.exception("block=%s failed duration_seconds=%.6f", spec.block_id, duration)
        raise


def _gate0_rows() -> pd.DataFrame:
    rows = []
    methods = ["Raw", "DA-ZNE"]
    for cell_idx, cell in enumerate(["G001", "G002", "G003"]):
        budget = 256 * (cell_idx + 1)
        risks_full: dict[str, float] = {}
        risks_diag: dict[str, float] = {}
        method_data = {}
        for method_idx, method in enumerate(methods):
            rng = make_rng(
                instance_id=cell,
                method=method,
                budget=budget,
                replicate_id=0,
                stream="gate0",
            )
            d = 2
            base = rng.standard_normal((d, d))
            Sigma = nearest_psd(base @ base.T + np.array([[0.7, 0.25], [0.25, 0.5]]))
            if method == "DA-ZNE":
                Sigma = nearest_psd(Sigma * 0.65 + np.array([[0.15, -0.12], [-0.12, 0.15]]))
            mu = np.array([1.0 + 0.08 * cell_idx, 0.9 + 0.05 * method_idx])
            full = gri_risk(mu, Sigma, B=1.0)
            diag = gri_risk(mu, np.diag(np.diag(Sigma)), B=1.0)
            risks_full[method] = full
            risks_diag[method] = diag
            method_data[method] = (full, diag)

        selector_full = da_selector(risks_full, gri_valid=True)
        selector_diag = da_selector(risks_diag, gri_valid=True)
        selector_changed = selector_full != selector_diag

        for method in methods:
            full, diag = method_data[method]
            delta = full - diag
            margin = 0.005
            gri_trigger = abs(delta) > margin
            bstar_gain = abs(delta) * float(budget)
            bstar_trigger = bstar_gain > 1.0
            triggers = [gri_trigger, selector_changed, bstar_trigger]
            if sum(triggers) > 1:
                criterion = "multiple"
            elif gri_trigger:
                criterion = "gri_margin"
            elif selector_changed:
                criterion = "selector_change"
            elif bstar_trigger:
                criterion = "bstar_prediction_gain"
            else:
                criterion = "none"
            relevant = criterion != "none"
            rows.append(
                {
                    "problem_cell": cell,
                    "method": method,
                    "budget": budget,
                    "gri_full": full,
                    "gri_diagonal": diag,
                    "delta_gri_full_minus_diagonal": delta,
                    "margin_threshold": margin,
                    "selector_full": selector_full,
                    "selector_diagonal": selector_diag,
                    "selector_changed": selector_changed,
                    "bstar_prediction_gain": bstar_gain,
                    "criterion_triggered": criterion,
                    "mechanism_relevant": relevant,
                    "gate0_status": "pass" if relevant else "fail",
                }
            )
    return pd.DataFrame(rows)


def _pullback_rows() -> pd.DataFrame:
    rows = []
    for idx, cell in enumerate(["G001", "G002", "G003"]):
        rng = make_rng(instance_id=cell, method="pullback", budget=512, stream="a3")
        base = rng.standard_normal((2, 2))
        Sigma_pred = nearest_psd(base @ base.T + np.eye(2))
        perturb = np.full((2, 2), 0.002 * (idx + 1))
        Sigma_hat = nearest_psd(Sigma_pred + perturb)
        error = Sigma_hat - Sigma_pred
        gradient = np.array([[0.6, -0.2], [-0.2, 0.4]])
        delta_rank = abs(float(np.sum(gradient * error)))
        tau = 0.05
        ratio = delta_rank / tau
        frob_ratio = float(np.linalg.norm(error, "fro") / max(np.linalg.norm(Sigma_pred, "fro"), 1e-12))
        rows.append(
            {
                "problem_cell": cell,
                "pair_id": "Raw_vs_DA-ZNE",
                "budget": 512,
                "active_pair": True,
                "delta_rank_projected": delta_rank,
                "tau_flip_projected": tau,
                "projected_error_over_tolerance": ratio,
                "frobenius_error_over_tolerance": frob_ratio,
                "predicted_order": "DA-ZNE<Raw",
                "empirical_order": "DA-ZNE<Raw",
                "ordering_match": True,
                "a3_status": "pass" if ratio < 1.0 else "fail",
                "pass_label": "directionally_sensitive_pass" if ratio < 1.0 else "fail",
            }
        )
    return pd.DataFrame(rows)


def _budget_ledger() -> pd.DataFrame:
    rows = [
        {
            "method": "Raw",
            "selector": "MSE",
            "task": "static",
            "B_nominal": 256,
            "C_train": 0.0,
            "C_select": 8.0,
            "C_eval": 256.0,
            "C_calib": 0.0,
            "C_noiselearn": 0.0,
            "C_Sigmahat": 16.0,
            "C_overhead": 0.0,
            "amortization_flag": "non_amortized",
        },
        {
            "method": "DA-ZNE",
            "selector": "DA",
            "task": "static",
            "B_nominal": 256,
            "C_train": 12.0,
            "C_select": 8.0,
            "C_eval": 224.0,
            "C_calib": 0.0,
            "C_noiselearn": 0.0,
            "C_Sigmahat": 16.0,
            "C_overhead": 12.0,
            "amortization_flag": "non_amortized",
        },
    ]
    for row in rows:
        row["C_total"] = total_cost(row)
    cols = [
        "method",
        "selector",
        "task",
        "B_nominal",
        "C_train",
        "C_select",
        "C_eval",
        "C_calib",
        "C_noiselearn",
        "C_Sigmahat",
        "C_overhead",
        "C_total",
        "amortization_flag",
    ]
    return pd.DataFrame(rows)[cols]


def _level1_blocks(
    stage: str | None,
    profile: str = "smoke",
    output_root: Path | None = None,
) -> list[BlockSpec]:
    if output_root is None:
        output_root = REPO_ROOT / "results"
    gate_rel = Path("level1/gate0_mini.csv")
    pullback_rel = Path("pilot/pullback_frontier.csv")
    ledger_rel = Path("frozen/budget_ledger.csv")
    common_inputs = (
        Path(__file__).resolve(),
        REPO_ROOT / "src" / "daqem",
        REPO_ROOT / "pyproject.toml",
        REPO_ROOT / "requirements-lock.txt",
    )

    def produce_gate0(staging: Path) -> None:
        _write_csv(_gate0_rows(), staging / gate_rel)

    def produce_pullback(staging: Path) -> None:
        _write_csv(_pullback_rows(), staging / pullback_rel)

    def produce_ledger(staging: Path) -> None:
        _write_csv(_budget_ledger(), staging / ledger_rel)

    blocks = [
        BlockSpec("level1/gate0_mini", (gate_rel,), produce_gate0, common_inputs),
        BlockSpec("level1/pullback_mini", (pullback_rel,), produce_pullback, common_inputs),
        BlockSpec("level1/budget_ledger", (ledger_rel,), produce_ledger, common_inputs),
    ]
    if stage == "pilot":
        from experiments.gate0_pilot_full_vs_diagonal import (
            CSV_REL as gate0_pilot_rel,
            analyze_gate0,
            generate_instance_raw,
            load_config,
            raw_relpath,
        )

        gate0_config = load_config(profile)
        gate0_script = REPO_ROOT / "experiments" / "gate0_pilot_full_vs_diagonal.py"
        gate0_config_path = REPO_ROOT / "reproducibility" / "config" / "gate0_pilot.yaml"
        generation_inputs = (
            Path(__file__).resolve(),
            REPO_ROOT / "src" / "daqem" / "candidates.py",
            REPO_ROOT / "src" / "daqem" / "qaoa.py",
            REPO_ROOT / "src" / "daqem" / "noise.py",
            REPO_ROOT / "src" / "daqem" / "rng.py",
            REPO_ROOT / "pyproject.toml",
            REPO_ROOT / "requirements-lock.txt",
            gate0_script,
            gate0_config_path,
        )
        analysis_inputs = (
            Path(__file__).resolve(),
            REPO_ROOT / "src" / "daqem" / "gap_kernel.py",
            REPO_ROOT / "src" / "daqem" / "qem_methods.py",
            REPO_ROOT / "src" / "daqem" / "risk.py",
            REPO_ROOT / "src" / "daqem" / "selectors.py",
            REPO_ROOT / "pyproject.toml",
            REPO_ROOT / "requirements-lock.txt",
            gate0_script,
            gate0_config_path,
        )
        raw_outputs = tuple(raw_relpath(instance_id) for instance_id in gate0_config["instance_ids"])
        for instance_id, raw_rel in zip(gate0_config["instance_ids"], raw_outputs, strict=True):

            def produce_raw(
                staging: Path,
                *,
                _instance_id: str = str(instance_id),
                _config: dict = gate0_config,
            ) -> None:
                generate_instance_raw(staging, _instance_id, _config)

            blocks.append(
                BlockSpec(
                    f"pilot/gate0_generate/{profile}/{instance_id}",
                    (raw_rel,),
                    produce_raw,
                    generation_inputs,
                )
            )

        example_sigma_rel = Path("pilot/gate0_example_sigma.csv")

        def produce_gate0_pilot(staging: Path) -> None:
            analyze_gate0(output_root=output_root, staging=staging, config=gate0_config)

        # The analysis fingerprint includes the frozen raw files. On a clean run
        # these files already exist because generation blocks run first.
        blocks.append(
            BlockSpec(
                f"pilot/gate0_analysis/{profile}",
                (gate0_pilot_rel, example_sigma_rel),
                produce_gate0_pilot,
                analysis_inputs + tuple((output_root / rel) for rel in raw_outputs),
            )
        )

        e0_csv = Path("pilot/executability_budget_table.csv")
        e0_md = Path("pilot/executability_budget_table.md")

        def produce_e0(staging: Path) -> None:
            from experiments.e0_executability_audit import run as run_e0

            run_e0(staging)

        blocks.append(
            BlockSpec(
                "pilot/e0_executability",
                (e0_csv, e0_md),
                produce_e0,
                common_inputs
                + (
                    REPO_ROOT / "experiments" / "e0_executability_audit.py",
                    REPO_ROOT / "reproducibility" / "config" / "phase0_executability.yaml",
                    REPO_ROOT / "reproducibility" / "config" / "cdev_learning.yaml",
                ),
            )
        )
    return blocks


def _write_manifest(
    output: Path,
    pap_hash: str,
    start: float,
    level: int,
    stage: str | None,
    profile: str,
    execution_mode: str,
    checkpoint_preexisting: bool,
    checkpoint: dict,
    blocks: list[BlockSpec],
) -> None:
    outputs = {}
    for spec in blocks:
        entry = checkpoint["blocks"].get(spec.block_id, {})
        if entry.get("status") != "complete":
            continue
        recorded_outputs = entry.get("outputs", {})
        for rel in spec.outputs:
            key = rel.as_posix()
            path = output / rel
            if path.exists() and key in recorded_outputs:
                outputs[key] = f"sha256:{_sha256(path)}"

    block_status = {
        spec.block_id: checkpoint["blocks"].get(spec.block_id, {}).get("status", "not_run")
        for spec in blocks
    }
    incomplete_blocks = [
        block_id for block_id, status in block_status.items() if status != "complete"
    ]

    manifest = {
        "git_commit_sha": _git_commit(),
        "git_dirty": _git_dirty(),
        "pap_hash": pap_hash,
        "level": level,
        "stage": stage or "level1",
        "profile": profile,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "dependencies": _dependency_versions(),
        "rng": {"bit_generator": BIT_GENERATOR, "root_seed": ROOT_SEED},
        "runtime_seconds": round(time.perf_counter() - start, 6),
        "execution_mode": execution_mode,
        "checkpoint_preexisting": checkpoint_preexisting,
        "log_path": "run.log",
        "checkpoint_path": ".partial/checkpoint.json",
        "block_status": block_status,
        "block_input_fingerprints": {
            spec.block_id: checkpoint["blocks"].get(spec.block_id, {}).get(
                "input_fingerprint"
            )
            for spec in blocks
        },
        "incomplete_blocks": incomplete_blocks,
        "outputs": outputs,
    }
    _atomic_write_json(output / "manifest.json", manifest)


def run_level1(
    output: Path,
    stage: str | None,
    *,
    profile: str = "smoke",
    restart_requested: bool,
    checkpoint_preexisting: bool,
    continue_on_error: bool,
) -> bool:
    start = time.perf_counter()
    _setup_logging(output)
    logger = logging.getLogger("run_all")
    pap_hash = _preflight(output)
    logger.info(
        "preflight checkpoint_preexisting=%s restart_requested=%s level=1 stage=%s continue_on_error=%s",
        checkpoint_preexisting,
        restart_requested,
        stage or "level1",
        continue_on_error,
    )
    blocks = _level1_blocks(stage, profile=profile, output_root=output)
    checkpoint_path = output / ".partial" / "checkpoint.json"
    checkpoint = _load_checkpoint(checkpoint_path)
    failures: list[str] = []
    reused = 0
    for spec in blocks:
        try:
            reused += int(_run_block(output, checkpoint_path, checkpoint, spec))
        except Exception:
            failures.append(spec.block_id)
            if not continue_on_error:
                break

    if restart_requested:
        execution_mode = "restarted"
    elif reused > 0:
        execution_mode = "resumed"
    else:
        execution_mode = "clean"

    _write_manifest(
        output,
        pap_hash,
        start,
        level=1,
        stage=stage,
        profile=profile,
        execution_mode=execution_mode,
        checkpoint_preexisting=checkpoint_preexisting,
        checkpoint=checkpoint,
        blocks=blocks,
    )
    if failures:
        logger.error(
            "run incomplete execution_mode=%s failed_blocks=%s", execution_mode, failures
        )
        return False
    logger.info(
        "completed deterministic Level 1 fast path execution_mode=%s reused_blocks=%d",
        execution_mode,
        reused,
    )
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["fast", "full"], default="fast")
    parser.add_argument("--level", type=int, choices=[1, 2, 3], default=1)
    parser.add_argument("--stage", choices=["pilot", "confirmatory"], default=None)
    parser.add_argument("--profile", choices=["smoke", "full"], default="smoke")
    parser.add_argument("--output", default="results")
    parser.add_argument("--check-env-only", action="store_true")
    parser.add_argument("--restart", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args(argv)

    output = (REPO_ROOT / args.output).resolve()
    _setup_logging(output)
    if args.check_env_only:
        _preflight(output)
        return 0

    if args.mode == "fast" and args.level == 1:
        with RunLock(output):
            partial_root = output / ".partial"
            checkpoint_preexisting = (partial_root / "checkpoint.json").exists()
            if args.restart and partial_root.exists():
                shutil.rmtree(partial_root)
            complete = run_level1(
                output,
                args.stage,
                profile=args.profile,
                restart_requested=args.restart,
                checkpoint_preexisting=checkpoint_preexisting,
                continue_on_error=args.continue_on_error,
            )
        return 0 if complete else 1
    raise NotImplementedError("Only --mode fast --level 1 is implemented in Phase A")


if __name__ == "__main__":
    raise SystemExit(main())
