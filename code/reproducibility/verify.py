from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from daqem.budget import validate_ledger


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
PAP_PATH = REPO_ROOT / "EXPERIMENTAL_PLAN_v13_PRXQ.md"
PAP_HASH_PATH = REPO_ROOT / "PAP_HASH.txt"
SCHEMA_PATH = REPO_ROOT / "reproducibility" / "config" / "schemas.yaml"
TOLERANCE_PATH = REPO_ROOT / "reproducibility" / "config" / "tolerances.yaml"
CANONICAL_FILES = [
    Path("level1/gate0_mini.csv"),
    Path("pilot/gate0_full_vs_diagonal.csv"),
    Path("pilot/pullback_frontier.csv"),
    Path("frozen/budget_ledger.csv"),
]
OPTIONAL_FILES = [
    Path("pilot/gate0_full_vs_diagonal.csv"),
    Path("pilot/executability_budget_table.csv"),
]


class VerificationError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise VerificationError(f"missing file: {path}")
    return pd.read_csv(path)


def _is_integer_series(series: pd.Series) -> bool:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.notna().all() and (numeric % 1 == 0).all()


def _validate_schema(df: pd.DataFrame, name: str, schema: dict) -> None:
    columns = schema[name]["columns"]
    expected = list(columns.keys())
    actual = list(df.columns)
    missing = [col for col in expected if col not in df.columns]
    extra = [col for col in actual if col not in columns]
    if missing:
        raise VerificationError(f"{name}: missing columns {missing}")
    if extra:
        raise VerificationError(f"{name}: extra columns {extra}")

    for col, spec in columns.items():
        series = df[col]
        if series.isna().any():
            raise VerificationError(f"{name}: NaN in column {col}")
        typ = spec["type"]
        if typ == "string":
            if not all(isinstance(v, str) for v in series):
                raise VerificationError(f"{name}: column {col} must be string")
        elif typ == "int":
            if not _is_integer_series(series):
                raise VerificationError(f"{name}: column {col} must be int")
            numeric = pd.to_numeric(series, errors="coerce")
            if "min" in spec and (numeric < spec["min"]).any():
                raise VerificationError(f"{name}: column {col} below min {spec['min']}")
            if "max" in spec and (numeric > spec["max"]).any():
                raise VerificationError(f"{name}: column {col} above max {spec['max']}")
        elif typ == "float":
            numeric = pd.to_numeric(series, errors="coerce")
            if numeric.isna().any():
                raise VerificationError(f"{name}: column {col} must be float")
            if not all(math.isfinite(float(v)) for v in numeric):
                raise VerificationError(f"{name}: non-finite value in column {col}")
            if "min" in spec and (numeric < spec["min"]).any():
                raise VerificationError(f"{name}: column {col} below min {spec['min']}")
            if "max" in spec and (numeric > spec["max"]).any():
                raise VerificationError(f"{name}: column {col} above max {spec['max']}")
        elif typ == "bool":
            def is_bool_token(value) -> bool:
                if isinstance(value, (bool, np.bool_)):
                    return True
                return isinstance(value, str) and value in {"True", "False", "true", "false"}

            if not all(is_bool_token(v) for v in series):
                raise VerificationError(f"{name}: column {col} must be bool")
        else:
            raise VerificationError(f"{name}: unknown type {typ} for {col}")

        if "allowed" in spec:
            allowed = set(spec["allowed"])
            observed = set(series.astype(str))
            if not observed <= allowed:
                raise VerificationError(
                    f"{name}: column {col} has disallowed values {sorted(observed - allowed)}"
                )


def _schema_name(rel: Path) -> str:
    if rel.as_posix() == "level1/gate0_mini.csv":
        return "gate0_full_vs_diagonal.csv"
    return rel.name


def _canonical_files_for_stage(stage: str | None) -> list[Path]:
    return [
        Path("level1/gate0_mini.csv"),
        Path("pilot/pullback_frontier.csv"),
        Path("frozen/budget_ledger.csv"),
    ]


def _normalize_for_key(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    if df.duplicated(subset=keys).any():
        raise VerificationError(f"duplicate row keys for {keys}")
    return df.sort_values(keys).set_index(keys, drop=False)


def _compare_dataframes(ref: pd.DataFrame, gen: pd.DataFrame, name: str, schema: dict, atol: float) -> None:
    keys = schema[name]["row_matching_key"]
    ref_idx = _normalize_for_key(ref, keys)
    gen_idx = _normalize_for_key(gen, keys)
    if set(ref_idx.index) != set(gen_idx.index):
        missing = sorted(set(ref_idx.index) - set(gen_idx.index))
        extra = sorted(set(gen_idx.index) - set(ref_idx.index))
        raise VerificationError(f"{name}: row key mismatch missing={missing} extra={extra}")

    columns = schema[name]["columns"]
    for key in ref_idx.index:
        for col, spec in columns.items():
            rv = ref_idx.loc[key, col]
            gv = gen_idx.loc[key, col]
            if spec.get("warning_only"):
                continue
            if spec["type"] in {"float", "int"}:
                if abs(float(rv) - float(gv)) > atol:
                    raise VerificationError(
                        f"{name}: numeric mismatch at {key} column {col}: {rv} vs {gv}"
                    )
            else:
                if str(rv) != str(gv):
                    raise VerificationError(
                        f"{name}: value mismatch at {key} column {col}: {rv} vs {gv}"
                    )


def _validate_budget(df: pd.DataFrame) -> None:
    errors = validate_ledger(df)
    if errors:
        raise VerificationError("; ".join(errors))


def _validate_pap_hash(generated_root: Path) -> None:
    if not PAP_HASH_PATH.exists():
        raise VerificationError("PAP_HASH.txt is missing")
    pap_hash = PAP_HASH_PATH.read_text(encoding="utf-8").strip()
    actual = f"sha256:{_sha256(PAP_PATH)}"
    if pap_hash.upper() != actual.upper():
        raise VerificationError(f"PAP_HASH.txt mismatch: {pap_hash} != {actual}")

    manifest_path = generated_root / "manifest.json"
    if not manifest_path.exists():
        raise VerificationError(f"manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("pap_hash", "").upper() != pap_hash.upper():
        raise VerificationError("manifest pap_hash does not match PAP_HASH.txt")


def _validate_manifest_output_hashes(generated_root: Path) -> None:
    manifest_path = generated_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise VerificationError("manifest outputs must be a dictionary")
    expected = {
        rel.as_posix()
        for rel in _canonical_files_for_stage(str(manifest.get("stage", "")))
    }
    missing = sorted(expected - set(outputs))
    if missing:
        raise VerificationError(f"manifest outputs missing canonical files {missing}")
    for output_name, expected_hash in outputs.items():
        rel = Path(output_name)
        if rel.is_absolute() or ".." in rel.parts:
            raise VerificationError(f"manifest output path is not canonical: {output_name}")
        output_path = generated_root / rel
        if not output_path.exists():
            raise VerificationError(f"manifest output missing: {output_name}")
        actual_hash = f"sha256:{_sha256(output_path)}"
        if str(expected_hash).upper() != actual_hash.upper():
            raise VerificationError(
                f"manifest output hash mismatch for {output_name}: {expected_hash} != {actual_hash}"
            )


def _validate_manifest_completion(generated_root: Path) -> None:
    manifest_path = generated_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    block_status = manifest.get("block_status")
    incomplete = manifest.get("incomplete_blocks")
    if not isinstance(block_status, dict):
        raise VerificationError("manifest block_status must be a dictionary")
    if not isinstance(incomplete, list):
        raise VerificationError("manifest incomplete_blocks must be a list")
    non_complete = sorted(
        block_id for block_id, status in block_status.items() if status != "complete"
    )
    declared = sorted(str(block_id) for block_id in incomplete)
    if declared != non_complete:
        raise VerificationError(
            f"manifest incomplete_blocks inconsistent with block_status: {declared} != {non_complete}"
        )
    if incomplete:
        raise VerificationError(f"manifest contains incomplete blocks: {incomplete}")

    checkpoint_value = manifest.get("checkpoint_path")
    if not isinstance(checkpoint_value, str) or not checkpoint_value:
        raise VerificationError("manifest checkpoint_path must be a non-empty string")
    checkpoint_rel = Path(checkpoint_value)
    if checkpoint_rel.is_absolute() or ".." in checkpoint_rel.parts:
        raise VerificationError(f"manifest checkpoint path is not canonical: {checkpoint_value}")
    checkpoint_path = generated_root / checkpoint_rel
    if not checkpoint_path.exists():
        raise VerificationError(f"checkpoint missing: {checkpoint_path}")
    try:
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid checkpoint: {checkpoint_path}") from exc
    checkpoint_blocks = checkpoint.get("blocks")
    if not isinstance(checkpoint_blocks, dict):
        raise VerificationError("checkpoint blocks must be a dictionary")
    checkpoint_incomplete = sorted(
        block_id
        for block_id, entry in checkpoint_blocks.items()
        if not isinstance(entry, dict) or entry.get("status") != "complete"
    )
    if checkpoint_incomplete:
        raise VerificationError(
            f"checkpoint contains incomplete blocks: {checkpoint_incomplete}"
        )

    manifest_outputs = manifest.get("outputs")
    if not isinstance(manifest_outputs, dict):
        raise VerificationError("manifest outputs must be a dictionary")
    checkpoint_outputs: dict[str, str] = {}
    manifest_fingerprints = manifest.get("block_input_fingerprints")
    if not isinstance(manifest_fingerprints, dict):
        raise VerificationError("manifest block_input_fingerprints must be a dictionary")
    for block_id, manifest_status in block_status.items():
        entry = checkpoint_blocks.get(block_id)
        if not isinstance(entry, dict):
            raise VerificationError(f"checkpoint missing manifest block: {block_id}")
        checkpoint_status = entry.get("status")
        if checkpoint_status != manifest_status:
            raise VerificationError(
                f"checkpoint/manifest status mismatch for {block_id}: "
                f"{checkpoint_status} != {manifest_status}"
            )
        input_fingerprint = entry.get("input_fingerprint")
        if not isinstance(input_fingerprint, str) or not input_fingerprint.startswith("sha256:"):
            raise VerificationError(f"checkpoint input fingerprint missing for {block_id}")
        if manifest_fingerprints.get(block_id) != input_fingerprint:
            raise VerificationError(
                f"manifest/checkpoint input fingerprint mismatch for {block_id}"
            )
        recorded_outputs = entry.get("outputs")
        if not isinstance(recorded_outputs, dict):
            raise VerificationError(f"checkpoint outputs missing for block: {block_id}")
        for output_name, expected_hash in recorded_outputs.items():
            rel = Path(output_name)
            if rel.is_absolute() or ".." in rel.parts:
                raise VerificationError(f"checkpoint output path is not canonical: {output_name}")
            output_path = generated_root / rel
            if not output_path.exists():
                raise VerificationError(f"checkpoint output missing: {output_name}")
            actual_hash = f"sha256:{_sha256(output_path)}"
            if str(expected_hash).upper() != actual_hash.upper():
                raise VerificationError(
                    f"checkpoint output hash mismatch for {output_name}: "
                    f"{expected_hash} != {actual_hash}"
                )
            checkpoint_outputs[output_name] = str(expected_hash)

    if set(manifest_outputs) != set(checkpoint_outputs):
        missing_outputs = sorted(set(checkpoint_outputs) - set(manifest_outputs))
        stale_outputs = sorted(set(manifest_outputs) - set(checkpoint_outputs))
        raise VerificationError(
            f"manifest/checkpoint output mismatch missing={missing_outputs} stale={stale_outputs}"
        )
    for output_name, checkpoint_hash in checkpoint_outputs.items():
        if str(manifest_outputs[output_name]).upper() != checkpoint_hash.upper():
            raise VerificationError(
                f"manifest/checkpoint hash mismatch for {output_name}: "
                f"{manifest_outputs[output_name]} != {checkpoint_hash}"
            )


def _load_reference_manifest(reference_root: Path) -> dict:
    path = reference_root / "manifest.json"
    if not path.exists():
        raise VerificationError(f"reference manifest missing: {path}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid reference manifest: {path}") from exc
    if not isinstance(manifest, dict):
        raise VerificationError("reference manifest must be a dictionary")
    return manifest


def _validate_reference_scope(reference_manifest: dict, generated_manifest: dict) -> None:
    for field in ["level", "stage", "pap_hash"]:
        if reference_manifest.get(field) != generated_manifest.get(field):
            raise VerificationError(
                f"reference/generated {field} mismatch: "
                f"{reference_manifest.get(field)} != {generated_manifest.get(field)}"
            )
    if not isinstance(reference_manifest.get("outputs"), dict):
        raise VerificationError("reference manifest outputs must be a dictionary")


def _validate_reference_integrity(reference_root: Path, reference_manifest: dict) -> None:
    pap_hash = PAP_HASH_PATH.read_text(encoding="utf-8").strip()
    if str(reference_manifest.get("pap_hash", "")).upper() != pap_hash.upper():
        raise VerificationError("reference manifest pap_hash does not match PAP_HASH.txt")
    for output_name, expected_hash in reference_manifest["outputs"].items():
        path = reference_root / Path(output_name)
        if not path.exists():
            raise VerificationError(f"reference output missing: {output_name}")
        actual_hash = f"sha256:{_sha256(path)}"
        if str(expected_hash).upper() != actual_hash.upper():
            raise VerificationError(
                f"reference output hash mismatch for {output_name}: "
                f"{expected_hash} != {actual_hash}"
            )

    registry_path = reference_root / "reference_manifest.json"
    if not registry_path.exists():
        raise VerificationError(f"reference registry missing: {registry_path}")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if str(registry.get("pap_hash", "")).upper() != pap_hash.upper():
        raise VerificationError("reference registry pap_hash does not match PAP_HASH.txt")
    checksums = registry.get("checksums")
    if not isinstance(checksums, dict):
        raise VerificationError("reference registry checksums must be a dictionary")
    required = set(reference_manifest["outputs"]) | {
        "manifest.json",
        str(reference_manifest.get("checkpoint_path", ".partial/checkpoint.json")),
    }
    missing = sorted(required - set(checksums))
    if missing:
        raise VerificationError(f"reference registry missing checksums: {missing}")
    for relative, expected_hash in checksums.items():
        path = reference_root / Path(relative)
        if not path.exists():
            raise VerificationError(f"reference checksum file missing: {relative}")
        actual_hash = f"sha256:{_sha256(path)}"
        if str(expected_hash).upper() != actual_hash.upper():
            raise VerificationError(
                f"reference checksum mismatch for {relative}: {expected_hash} != {actual_hash}"
            )


def _validate_current_input_fingerprints(manifest: dict) -> None:
    from reproducibility.run_all import _block_input_fingerprint, _level1_blocks

    stage = manifest.get("stage")
    profile = str(manifest.get("profile", "smoke"))
    specs = {
        spec.block_id: spec
        for spec in _level1_blocks(
            "pilot" if stage == "pilot" else None,
            profile=profile,
            output_root=Path(manifest.get("_generated_root", REPO_ROOT / "results")),
        )
    }
    observed = manifest.get("block_input_fingerprints")
    if not isinstance(observed, dict):
        raise VerificationError("manifest block_input_fingerprints must be a dictionary")
    unknown = sorted(set(observed) - set(specs))
    if unknown:
        raise VerificationError(f"manifest contains unknown block ids: {unknown}")
    for block_id in observed:
        try:
            expected_fingerprint = _block_input_fingerprint(specs[block_id])
        except RuntimeError as exc:
            raise VerificationError(str(exc)) from exc
        if observed.get(block_id) != expected_fingerprint:
            raise VerificationError(f"current input fingerprint mismatch for {block_id}")


def _claim_language_hook() -> None:
    return None


def _hardware_carveout_hook() -> None:
    return None


def verify(reference: Path, generated: Path, exact_numeric: bool = False) -> None:
    schema = _load_yaml(SCHEMA_PATH)
    tolerances = _load_yaml(TOLERANCE_PATH)
    atol = 0.0 if exact_numeric else float(tolerances["level1"]["numeric_abs"]["value"])

    _validate_pap_hash(generated)
    manifest = json.loads((generated / "manifest.json").read_text(encoding="utf-8"))
    manifest["_generated_root"] = generated
    manifest_outputs = manifest.get("outputs")
    if not isinstance(manifest_outputs, dict):
        raise VerificationError("manifest outputs must be a dictionary")
    reference_manifest = _load_reference_manifest(reference)
    _validate_reference_scope(reference_manifest, manifest)
    _validate_reference_integrity(reference, reference_manifest)
    _validate_current_input_fingerprints(manifest)
    reference_outputs = reference_manifest["outputs"]
    files = _canonical_files_for_stage(str(manifest.get("stage", "")))
    for rel in OPTIONAL_FILES:
        if rel.as_posix() in reference_outputs or rel.as_posix() in manifest_outputs:
            files.append(rel)
    for rel in files:
        name = _schema_name(rel)
        ref_df = _read_csv(reference / rel)
        gen_df = _read_csv(generated / rel)
        _validate_schema(ref_df, name, schema)
        _validate_schema(gen_df, name, schema)
        _compare_dataframes(ref_df, gen_df, name, schema, atol)
        if name == "budget_ledger.csv":
            _validate_budget(gen_df)

    _validate_manifest_completion(generated)
    _validate_manifest_output_hashes(generated)
    _claim_language_hook()
    _hardware_carveout_hook()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--generated", default="results")
    parser.add_argument("--exact-numeric", action="store_true")
    args = parser.parse_args(argv)

    try:
        verify(
            reference=(REPO_ROOT / args.reference).resolve(),
            generated=(REPO_ROOT / args.generated).resolve(),
            exact_numeric=args.exact_numeric,
        )
    except VerificationError as exc:
        print(f"VERIFY FAIL: {exc}", file=sys.stderr)
        return 1
    print("VERIFY PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
