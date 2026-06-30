from __future__ import annotations

import filecmp
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
FINAL_PASS = (
    "REPRODUCE_ALL_PASS: Level 1 exact, determinism, tests, freeze audit, "
    "confirmatory verification, extension verification, and figures completed"
)


class StepError(RuntimeError):
    pass


def run_command(step: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    print(f"[{step}] $ {' '.join(args)}", flush=True)
    proc = subprocess.run(
        args,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if proc.stdout:
        print(proc.stdout, end="", flush=True)
    if proc.returncode != 0:
        raise StepError(f"{step}: command failed with exit {proc.returncode}")
    return proc


def require_output(step: str, proc: subprocess.CompletedProcess[str], marker: str) -> None:
    if marker not in proc.stdout:
        raise StepError(f"{step}: expected marker not found: {marker}")


def run_level1_exact() -> None:
    temp_root = Path(tempfile.mkdtemp(prefix="daqem_level1_exact_"))
    try:
        generated = temp_root / "generated"
        run_command(
            "level1-run",
            [
                PYTHON,
                "reproducibility/run_all.py",
                "--mode",
                "fast",
                "--level",
                "1",
                "--output",
                str(generated),
            ],
        )
        proc = run_command(
            "level1-verify",
            [
                PYTHON,
                "reproducibility/verify.py",
                "--reference",
                "reproducibility/reference_level1/",
                "--generated",
                str(generated),
            ],
        )
        require_output("level1-verify", proc, "VERIFY PASS")
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def output_files_from_manifest(output_root: Path) -> list[Path]:
    manifest_path = output_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise StepError(f"determinism: invalid outputs in {manifest_path}")
    return sorted(Path(relpath) for relpath in outputs)


def compare_canonical_outputs(lhs: Path, rhs: Path) -> list[str]:
    relpaths = output_files_from_manifest(lhs)
    rhs_relpaths = output_files_from_manifest(rhs)
    if relpaths != rhs_relpaths:
        return [f"manifest output set differs: {relpaths} != {rhs_relpaths}"]

    mismatches = []
    for relpath in relpaths:
        left = lhs / relpath
        right = rhs / relpath
        if not left.exists() or not right.exists():
            mismatches.append(f"missing {relpath}")
            continue
        if not filecmp.cmp(left, right, shallow=False):
            mismatches.append(relpath.as_posix())
    return mismatches


def run_determinism() -> None:
    temp_root = Path(tempfile.mkdtemp(prefix="daqem_level1_determinism_"))
    try:
        first = temp_root / "run_a"
        second = temp_root / "run_b"
        third = temp_root / "run_c"
        run_command(
            "determinism-run-a",
            [
                PYTHON,
                "reproducibility/run_all.py",
                "--mode",
                "fast",
                "--level",
                "1",
                "--output",
                str(first),
            ],
        )
        run_command(
            "determinism-run-b",
            [
                PYTHON,
                "reproducibility/run_all.py",
                "--mode",
                "fast",
                "--level",
                "1",
                "--output",
                str(second),
            ],
        )
        run_command(
            "determinism-run-c",
            [
                PYTHON,
                "reproducibility/run_all.py",
                "--mode",
                "fast",
                "--level",
                "1",
                "--output",
                str(third),
            ],
        )
        mismatches_ab = compare_canonical_outputs(first, second)
        mismatches_ac = compare_canonical_outputs(first, third)
        mismatches = [f"run_a vs run_b: {item}" for item in mismatches_ab]
        mismatches.extend(f"run_a vs run_c: {item}" for item in mismatches_ac)
        print(
            f"DETERMINISM CHECK: files={len(output_files_from_manifest(first))} "
            f"runs=3 comparisons=2 mismatches={len(mismatches)}",
            flush=True,
        )
        if mismatches:
            raise StepError("determinism: " + ", ".join(mismatches))
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def run_pytest() -> None:
    run_command("tests", [PYTHON, "-m", "pytest", "tests/", "-q"])


def run_freeze_audit() -> None:
    proc = run_command("freeze-audit", [PYTHON, "scripts/verify_freeze.py"])
    require_output("freeze-audit", proc, "FREEZE AUDIT PASS")


def run_confirmatory() -> None:
    proc = run_command("confirmatory", [PYTHON, "scripts/verify_confirmatory.py"])
    require_output("confirmatory", proc, "CONFIRMATORY VERIFY PASS")


def run_extension() -> None:
    proc = run_command("extension", [PYTHON, "scripts/verify_extension.py"])
    require_output("extension", proc, "EXTENSION VERIFY PASS")


def run_figures() -> None:
    proc = run_command("figures", [PYTHON, "scripts/generate_all_figures.py"])
    require_output("figures", proc, "FIGURES PASS")


def main() -> int:
    steps = [
        ("Level 1 exact", run_level1_exact),
        ("determinism", run_determinism),
        ("tests", run_pytest),
        ("freeze audit", run_freeze_audit),
        ("confirmatory verification", run_confirmatory),
        ("extension verification", run_extension),
        ("figures", run_figures),
    ]
    for label, func in steps:
        try:
            func()
        except Exception as exc:
            print(f"REPRODUCE_ALL_FAIL: {label}")
            print(str(exc))
            return 1
    print(FINAL_PASS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
