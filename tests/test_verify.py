import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_ALL = REPO_ROOT / "reproducibility" / "run_all.py"
VERIFY = REPO_ROOT / "reproducibility" / "verify.py"


def _run_level1(output: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(RUN_ALL),
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


def _verify(reference: Path, generated: Path, *, exact_numeric: bool = False):
    cmd = [
        sys.executable,
        str(VERIFY),
        "--reference",
        str(reference),
        "--generated",
        str(generated),
    ]
    if exact_numeric:
        cmd.append("--exact-numeric")
    return subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)


def _pair(tmp_path: Path) -> tuple[Path, Path]:
    reference = tmp_path / "reference"
    generated = tmp_path / "generated"
    _run_level1(reference)
    _run_level1(generated)
    _write_reference_registry(reference)
    return reference, generated


def _write_csv(path: Path, df: pd.DataFrame) -> None:
    df.to_csv(path, index=False)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _write_reference_registry(reference: Path) -> None:
    manifest = json.loads((reference / "manifest.json").read_text(encoding="utf-8"))
    paths = set(manifest["outputs"]) | {
        "manifest.json",
        manifest["checkpoint_path"],
    }
    registry = {
        "pap_hash": manifest["pap_hash"],
        "checksums": {
            relative: f"sha256:{_sha256(reference / relative)}"
            for relative in sorted(paths)
        },
    }
    (reference / "reference_manifest.json").write_text(
        json.dumps(registry, indent=2), encoding="utf-8"
    )


def _register_e0_checkpoint(generated: Path, e0_path: Path, manifest_hash: str) -> None:
    from reproducibility.run_all import _block_input_fingerprint, _level1_blocks

    rel = "pilot/executability_budget_table.csv"
    actual_hash = f"sha256:{_sha256(e0_path)}"
    e0_spec = next(
        spec for spec in _level1_blocks("pilot") if spec.block_id == "pilot/e0_executability"
    )
    input_fingerprint = _block_input_fingerprint(e0_spec)
    checkpoint_path = generated / ".partial" / "checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint["blocks"]["pilot/e0_executability"] = {
        "status": "complete",
        "outputs": {rel: actual_hash},
        "duration_seconds": 0.0,
        "input_fingerprint": input_fingerprint,
    }
    checkpoint_path.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")

    manifest_path = generated / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["stage"] = "pilot"
    manifest["block_status"]["pilot/e0_executability"] = "complete"
    manifest["block_input_fingerprints"]["pilot/e0_executability"] = input_fingerprint
    manifest["outputs"][rel] = manifest_hash
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _register_reference_e0(
    reference: Path, e0_path: Path, *, set_pilot_stage: bool = True
) -> None:
    manifest_path = reference / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if set_pilot_stage:
        manifest["stage"] = "pilot"
    manifest["outputs"]["pilot/executability_budget_table.csv"] = (
        f"sha256:{_sha256(e0_path)}"
    )
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _write_reference_registry(reference)


def test_verify_clean_outputs_pass(tmp_path):
    reference, generated = _pair(tmp_path)
    result = _verify(reference, generated, exact_numeric=True)
    assert result.returncode == 0, result.stderr
    assert "VERIFY PASS" in result.stdout


def test_verify_rejects_reference_with_wrong_pap_hash(tmp_path):
    reference, generated = _pair(tmp_path)
    manifest_path = reference / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["pap_hash"] = "sha256:WRONG"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    result = _verify(reference, generated)
    assert result.returncode != 0
    assert "pap_hash" in result.stderr


def test_verify_rejects_corrupted_reference_checksum(tmp_path):
    reference, generated = _pair(tmp_path)
    path = reference / "level1" / "gate0_mini.csv"
    path.write_bytes(path.read_bytes() + b"\n")
    result = _verify(reference, generated)
    assert result.returncode != 0
    assert "reference output hash mismatch" in result.stderr


def test_verify_recomputes_current_input_fingerprints(tmp_path):
    reference, generated = _pair(tmp_path)
    fake = f"sha256:{'F' * 64}"
    checkpoint_path = generated / ".partial" / "checkpoint.json"
    manifest_path = generated / "manifest.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for block_id in manifest["block_status"]:
        checkpoint["blocks"][block_id]["input_fingerprint"] = fake
        manifest["block_input_fingerprints"][block_id] = fake
    checkpoint_path.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    result = _verify(reference, generated)
    assert result.returncode != 0
    assert "current input fingerprint mismatch" in result.stderr


def test_verify_missing_rows_fail(tmp_path):
    reference, generated = _pair(tmp_path)
    path = generated / "level1" / "gate0_mini.csv"
    df = pd.read_csv(path).iloc[:-1]
    _write_csv(path, df)
    result = _verify(reference, generated)
    assert result.returncode != 0
    assert "row key mismatch" in result.stderr


def test_verify_extra_columns_fail(tmp_path):
    reference, generated = _pair(tmp_path)
    path = generated / "level1" / "gate0_mini.csv"
    df = pd.read_csv(path)
    df["extra_column"] = 1
    _write_csv(path, df)
    result = _verify(reference, generated)
    assert result.returncode != 0
    assert "extra columns" in result.stderr


def test_verify_bad_manifest_output_hash_fails(tmp_path):
    reference, generated = _pair(tmp_path)
    manifest_path = generated / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outputs"]["level1/gate0_mini.csv"] = "sha256:BAD"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    result = _verify(reference, generated, exact_numeric=True)
    assert result.returncode != 0
    assert "hash mismatch" in result.stderr


def test_verify_incomplete_block_fails(tmp_path):
    reference, generated = _pair(tmp_path)
    manifest_path = generated / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["block_status"]["level1/gate0_mini"] = "incomplete"
    manifest["incomplete_blocks"] = ["level1/gate0_mini"]
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    result = _verify(reference, generated)
    assert result.returncode != 0
    assert "manifest contains incomplete blocks" in result.stderr


def test_verify_rejects_stale_manifest_when_checkpoint_is_incomplete(tmp_path):
    reference, generated = _pair(tmp_path)
    checkpoint_path = generated / ".partial" / "checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint["blocks"]["level1/gate0_mini"]["status"] = "incomplete"
    checkpoint_path.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")
    result = _verify(reference, generated)
    assert result.returncode != 0
    assert "checkpoint contains incomplete blocks" in result.stderr


def test_verify_rejects_incomplete_checkpoint_block_missing_from_manifest(tmp_path):
    reference, generated = _pair(tmp_path)
    checkpoint_path = generated / ".partial" / "checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint["blocks"]["pilot/e0_executability"] = {
        "status": "incomplete",
        "outputs": {},
        "duration_seconds": 1.0,
        "input_fingerprint": f"sha256:{'B' * 64}",
    }
    checkpoint_path.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")
    result = _verify(reference, generated)
    assert result.returncode != 0
    assert "checkpoint contains incomplete blocks" in result.stderr


def test_verify_requires_optional_output_declared_by_reference(tmp_path):
    reference, generated = _pair(tmp_path)
    ref_path = reference / "pilot" / "executability_budget_table.csv"
    ref_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "block": "E1_static",
                "primary_unit": "paired_decisions",
                "N_minimum": 1500,
                "estimated_shots": 921_600_000,
                "wall_hours": 1.0,
                "backend_or_resource": "sim/Aer",
                "risk": "within sim ceiling",
                "decision": "go",
            }
        ]
    ).to_csv(ref_path, index=False)
    _register_reference_e0(reference, ref_path, set_pilot_stage=False)
    result = _verify(reference, generated)
    assert result.returncode != 0
    assert "missing file" in result.stderr


def test_verify_bad_e0_warning_only_manifest_hash_fails(tmp_path):
    reference, generated = _pair(tmp_path)
    e0 = pd.DataFrame(
        [
            {
                "block": "E1_static",
                "primary_unit": "paired_decisions",
                "N_minimum": 1500,
                "estimated_shots": 921_600_000,
                "wall_hours": 1.0,
                "backend_or_resource": "sim/Aer",
                "risk": "within sim ceiling",
                "decision": "go",
            }
        ]
    )
    for root in [reference, generated]:
        path = root / "pilot" / "executability_budget_table.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        e0.to_csv(path, index=False)
    _register_reference_e0(
        reference, reference / "pilot" / "executability_budget_table.csv"
    )

    _register_e0_checkpoint(
        generated,
        generated / "pilot" / "executability_budget_table.csv",
        "sha256:BAD",
    )
    result = _verify(reference, generated)
    assert result.returncode != 0
    assert "hash mismatch" in result.stderr


def test_verify_allows_environment_dependent_e0_diagnostics(tmp_path):
    reference, generated = _pair(tmp_path)
    base = {
        "block": "E1_static",
        "primary_unit": "paired_decisions",
        "N_minimum": 1500,
        "estimated_shots": 921_600_000,
        "backend_or_resource": "sim/Aer",
    }
    ref_e0 = pd.DataFrame(
        [{**base, "wall_hours": 60.0, "risk": "sim wall clock exceeds ceiling", "decision": "no-go"}]
    )
    gen_e0 = pd.DataFrame(
        [{**base, "wall_hours": 6.0, "risk": "within sim ceiling", "decision": "go"}]
    )
    ref_path = reference / "pilot" / "executability_budget_table.csv"
    gen_path = generated / "pilot" / "executability_budget_table.csv"
    ref_path.parent.mkdir(parents=True, exist_ok=True)
    gen_path.parent.mkdir(parents=True, exist_ok=True)
    ref_e0.to_csv(ref_path, index=False)
    gen_e0.to_csv(gen_path, index=False)
    _register_reference_e0(reference, ref_path)

    _register_e0_checkpoint(generated, gen_path, f"sha256:{_sha256(gen_path)}")
    result = _verify(reference, generated)
    assert result.returncode == 0, result.stderr
    assert "VERIFY PASS" in result.stdout


def test_verify_missing_columns_fail(tmp_path):
    reference, generated = _pair(tmp_path)
    path = generated / "level1" / "gate0_mini.csv"
    df = pd.read_csv(path).drop(columns=["method"])
    _write_csv(path, df)
    result = _verify(reference, generated)
    assert result.returncode != 0
    assert "missing columns" in result.stderr


def test_verify_nan_and_inf_fail(tmp_path):
    for bad_value in [np.nan, np.inf]:
        reference, generated = _pair(tmp_path / str(bad_value).replace(".", "_"))
        path = generated / "level1" / "gate0_mini.csv"
        df = pd.read_csv(path)
        df.loc[0, "gri_full"] = bad_value
        _write_csv(path, df)
        result = _verify(reference, generated)
        assert result.returncode != 0
        assert "NaN" in result.stderr or "non-finite" in result.stderr


def test_verify_type_mismatch_fails(tmp_path):
    reference, generated = _pair(tmp_path)
    path = generated / "level1" / "gate0_mini.csv"
    df = pd.read_csv(path)
    df["budget"] = df["budget"].astype(object)
    df.loc[0, "budget"] = "not_an_int"
    _write_csv(path, df)
    result = _verify(reference, generated)
    assert result.returncode != 0
    assert "must be int" in result.stderr


def test_verify_integer_minimum_fails(tmp_path):
    reference, generated = _pair(tmp_path)
    path = generated / "level1" / "gate0_mini.csv"
    df = pd.read_csv(path)
    df.loc[0, "budget"] = 0
    _write_csv(path, df)
    result = _verify(reference, generated)
    assert result.returncode != 0
    assert "below min" in result.stderr


def test_verify_bool_rejects_integer_tokens(tmp_path):
    reference, generated = _pair(tmp_path)
    path = generated / "level1" / "gate0_mini.csv"
    df = pd.read_csv(path)
    df["selector_changed"] = df["selector_changed"].astype(object)
    df.loc[0, "selector_changed"] = 1
    _write_csv(path, df)
    result = _verify(reference, generated)
    assert result.returncode != 0
    assert "must be bool" in result.stderr


def test_verify_bad_budget_arithmetic_fails(tmp_path):
    reference, generated = _pair(tmp_path)
    path = generated / "frozen" / "budget_ledger.csv"
    df = pd.read_csv(path)
    df.loc[0, "C_total"] = float(df.loc[0, "C_total"]) + 1.0
    _write_csv(path, df)
    result = _verify(reference, generated)
    assert result.returncode != 0
    assert "C_total" in result.stderr


def test_verify_missing_pap_hash_fails(tmp_path):
    reference, generated = _pair(tmp_path)
    manifest_path = generated / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("pap_hash", None)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    result = _verify(reference, generated)
    assert result.returncode != 0
    assert "pap_hash" in result.stderr
