from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SOURCE_ROOT = REPO_ROOT / "results"
REFERENCE_ROOT = REPO_ROOT / "reproducibility" / "reference"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures"
CANONICAL_FILES = [
    Path("level1/gate0_mini.csv"),
    Path("pilot/gate0_full_vs_diagonal.csv"),
    Path("pilot/pullback_frontier.csv"),
    Path("frozen/budget_ledger.csv"),
    Path("manifest.json"),
]
OPTIONAL_FILES = [
    Path("pilot/executability_budget_table.csv"),
    Path("pilot/executability_budget_table.md"),
]
CHECKPOINT_FILE = Path(".partial/checkpoint.json")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def git_value(args: list[str]) -> str | None:
    try:
        return subprocess.check_output(args, cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def _build_reference(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    checksums: dict[str, str] = {}
    source_manifest = json.loads((SOURCE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    declared_outputs = {Path(rel) for rel in source_manifest["outputs"]}
    files = sorted(declared_outputs | {Path("manifest.json")}, key=lambda item: item.as_posix())
    files += [rel for rel in OPTIONAL_FILES if rel in declared_outputs and rel not in files]
    files.append(CHECKPOINT_FILE)
    for rel in files:
        src = SOURCE_ROOT / rel
        dst = destination / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        checksums[str(rel.as_posix())] = sha256(dst)

    pap_hash = (REPO_ROOT / "PAP_HASH.txt").read_text(encoding="utf-8").strip()
    reference_manifest = {
        "git_tag": git_value(["git", "describe", "--tags", "--always"]),
        "git_commit_sha": git_value(["git", "rev-parse", "HEAD"]),
        "pap_hash": pap_hash,
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "checksums": {path: f"sha256:{digest}" for path, digest in checksums.items()},
    }
    (destination / "reference_manifest.json").write_text(
        json.dumps(reference_manifest, indent=2), encoding="utf-8"
    )
    with (destination / "checksums.sha256").open("w", encoding="ascii") as f:
        for path, digest in checksums.items():
            f.write(f"{digest}  {path}\n")


def _update_fixtures() -> None:
    FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)
    gate_ref = REFERENCE_ROOT / "level1" / "gate0_mini.csv"
    a3_ref = REFERENCE_ROOT / "pilot" / "pullback_frontier.csv"
    for source, name in [
        (gate_ref, "mini_gate0_reference.csv"),
        (a3_ref, "mini_a3_reference.csv"),
    ]:
        destination = FIXTURE_ROOT / name
        tmp = destination.with_name(f"{destination.name}.tmp")
        shutil.copy2(source, tmp)
        os.replace(tmp, destination)
    gate = pd.read_csv(gate_ref)
    selector = gate[
        ["problem_cell", "method", "budget", "selector_full", "selector_diagonal"]
    ]
    destination = FIXTURE_ROOT / "mini_selector_reference.csv"
    tmp = destination.with_name(f"{destination.name}.tmp")
    selector.to_csv(tmp, index=False)
    os.replace(tmp, destination)


def main() -> int:
    from reproducibility.run_all import RunLock
    from reproducibility.verify import (
        _validate_current_input_fingerprints,
        _validate_manifest_completion,
        _validate_manifest_output_hashes,
        _validate_pap_hash,
    )

    staging = REFERENCE_ROOT.with_name(f"{REFERENCE_ROOT.name}.staging")
    backup = REFERENCE_ROOT.with_name(f"{REFERENCE_ROOT.name}.backup")
    with RunLock(SOURCE_ROOT):
        _validate_pap_hash(SOURCE_ROOT)
        _validate_manifest_completion(SOURCE_ROOT)
        manifest = json.loads((SOURCE_ROOT / "manifest.json").read_text(encoding="utf-8"))
        _validate_current_input_fingerprints(manifest)
        _validate_manifest_output_hashes(SOURCE_ROOT)

        if not REFERENCE_ROOT.exists() and backup.exists():
            os.replace(backup, REFERENCE_ROOT)
        shutil.rmtree(staging, ignore_errors=True)
        if backup.exists():
            shutil.rmtree(backup)
        _build_reference(staging)
        if REFERENCE_ROOT.exists():
            os.replace(REFERENCE_ROOT, backup)
        try:
            os.replace(staging, REFERENCE_ROOT)
        except Exception:
            if backup.exists() and not REFERENCE_ROOT.exists():
                os.replace(backup, REFERENCE_ROOT)
            raise
        shutil.rmtree(backup, ignore_errors=True)

    _update_fixtures()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
