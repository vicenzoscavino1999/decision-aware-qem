import subprocess
import sys
import json
import hashlib
from pathlib import Path

import numpy as np

from daqem.rng import BIT_GENERATOR, ROOT_SEED, make_rng


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_reference_registry(reference: Path) -> None:
    manifest = json.loads((reference / "manifest.json").read_text(encoding="utf-8"))
    paths = set(manifest["outputs"]) | {"manifest.json", manifest["checkpoint_path"]}
    checksums = {}
    for relative in paths:
        digest = hashlib.sha256((reference / relative).read_bytes()).hexdigest().upper()
        checksums[relative] = f"sha256:{digest}"
    (reference / "reference_manifest.json").write_text(
        json.dumps({"pap_hash": manifest["pap_hash"], "checksums": checksums}, indent=2),
        encoding="utf-8",
    )


def test_make_rng_same_identifiers_same_sequence():
    assert ROOT_SEED == 260616
    assert BIT_GENERATOR == "PCG64DXSM"
    rng_a = make_rng(
        instance_id="i1", method="Raw", budget=256, replicate_id=3, stream="gaps"
    )
    rng_b = make_rng(
        instance_id="i1", method="Raw", budget=256, replicate_id=3, stream="gaps"
    )
    assert np.allclose(rng_a.standard_normal(8), rng_b.standard_normal(8))


def test_make_rng_different_identifiers_different_sequence():
    rng_a = make_rng(instance_id="i1", method="Raw", budget=256, stream="gaps")
    rng_b = make_rng(instance_id="i1", method="ZNE", budget=256, stream="gaps")
    assert not np.allclose(rng_a.standard_normal(8), rng_b.standard_normal(8))


def test_run_all_level1_outputs_are_exactly_reproducible(tmp_path):
    run_all = REPO_ROOT / "reproducibility" / "run_all.py"
    verify = REPO_ROOT / "reproducibility" / "verify.py"
    det1 = tmp_path / "det1"
    det2 = tmp_path / "det2"
    for output in [det1, det2]:
        subprocess.run(
            [
                sys.executable,
                str(run_all),
                "--mode",
                "fast",
                "--level",
                "1",
                "--output",
                str(output),
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    manifest = json.loads((det1 / "manifest.json").read_text(encoding="utf-8"))
    _write_reference_registry(det1)
    assert set(manifest["outputs"]) == {
        "level1/gate0_mini.csv",
        "pilot/pullback_frontier.csv",
        "frozen/budget_ledger.csv",
    }
    result = subprocess.run(
        [
            sys.executable,
            str(verify),
            "--reference",
            str(det1),
            "--generated",
            str(det2),
            "--exact-numeric",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
