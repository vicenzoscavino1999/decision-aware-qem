from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for path in [REPO_ROOT, SRC_ROOT]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments import gate0_pilot_full_vs_diagonal as gate0  # noqa: E402


INSTANCE_ID = "C001"
PROFILE = "confirmatory_full"
LEVEL2_ABS_TOL = 1e-6
ARCHIVED_RAW = REPO_ROOT / "reproducibility" / "reference_confirmatory" / "raw" / f"{INSTANCE_ID}.npz"
RESULTS_ROOT = (REPO_ROOT / "results").resolve()


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _compare_arrays(key: str, actual: np.ndarray, expected: np.ndarray) -> tuple[bool, str]:
    if actual.shape != expected.shape:
        return False, f"shape mismatch actual={actual.shape} expected={expected.shape}"

    if np.issubdtype(actual.dtype, np.floating) or np.issubdtype(expected.dtype, np.floating):
        actual_f = np.asarray(actual, dtype=float)
        expected_f = np.asarray(expected, dtype=float)
        diff = np.abs(actual_f - expected_f)
        max_abs = float(np.max(diff)) if diff.size else float(abs(actual_f - expected_f))
        ok = bool(np.all(diff <= LEVEL2_ABS_TOL))
        return ok, f"float max_abs={max_abs:.12g} tol={LEVEL2_ABS_TOL:g}"

    ok = bool(np.array_equal(actual, expected))
    if ok:
        return True, f"exact dtype={actual.dtype}"
    return False, f"exact mismatch dtype actual={actual.dtype} expected={expected.dtype}"


def compare_npz(regenerated: Path, archived: Path) -> tuple[bool, list[str]]:
    lines: list[str] = []
    with np.load(regenerated, allow_pickle=False) as got, np.load(archived, allow_pickle=False) as exp:
        got_keys = set(got.files)
        exp_keys = set(exp.files)
        if got_keys != exp_keys:
            missing = sorted(exp_keys - got_keys)
            extra = sorted(got_keys - exp_keys)
            lines.append(f"KEYS FAIL missing={missing} extra={extra}")
            return False, lines
        ok_all = True
        for key in sorted(exp.files):
            ok, detail = _compare_arrays(key, got[key], exp[key])
            ok_all = ok_all and ok
            status = "PASS" if ok else "FAIL"
            lines.append(f"{key}: {status} {detail}")
        return ok_all, lines


def run_check() -> int:
    if not ARCHIVED_RAW.exists():
        print(f"DETERMINISM FAIL archived raw missing: {ARCHIVED_RAW}")
        return 1

    scratch = Path(tempfile.mkdtemp(prefix="daqem_confirmatory_det_")).resolve()
    if _is_under(scratch, RESULTS_ROOT):
        shutil.rmtree(scratch, ignore_errors=True)
        print(f"DETERMINISM FAIL scratch is under results/: {scratch}")
        return 1

    started = time.perf_counter()
    try:
        config = gate0.load_config(PROFILE)
        if INSTANCE_ID not in config["instance_ids"]:
            raise RuntimeError(f"{INSTANCE_ID} is not present in {PROFILE}")
        print(f"scratch={scratch}")
        print(f"profile={PROFILE}; declared_instances={len(config['instance_ids'])}; generating_only={INSTANCE_ID}")

        gate0.generate_instance_raw(scratch, INSTANCE_ID, config)
        produced = sorted(scratch.glob(f"**/{INSTANCE_ID}.npz"))
        if len(produced) != 1:
            print(f"DETERMINISM FAIL expected one regenerated npz, found {len(produced)}: {produced}")
            return 1
        regenerated = produced[0]
        ok, lines = compare_npz(regenerated, ARCHIVED_RAW)
        for line in lines:
            print(line)
        elapsed = time.perf_counter() - started
        if ok:
            print(f"DETERMINISM PASS instance={INSTANCE_ID} elapsed_seconds={elapsed:.3f}")
            return 0
        print(f"DETERMINISM FAIL instance={INSTANCE_ID} elapsed_seconds={elapsed:.3f}")
        return 1
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        print(f"scratch_cleaned={scratch}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--instance-id",
        default=INSTANCE_ID,
        choices=[INSTANCE_ID],
        help="Safety guard: this check is intentionally limited to C001.",
    )
    parser.parse_args(argv)
    return run_check()


if __name__ == "__main__":
    raise SystemExit(main())
