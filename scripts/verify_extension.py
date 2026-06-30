from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

REFERENCE_ROOT = REPO_ROOT / "reproducibility" / "reference_extension"
MANIFEST_NAME = "extension_manifest.json"
LEVEL2_FLOAT_ATOL = 1e-6

EXPECTED_OUTPUTS = [
    "proof_of_mechanism/result.json",
    "proof_of_mechanism/coexistence_by_instance.csv",
    "proof_of_mechanism/result.md",
    "r1_full/epsilon_opt_manifest.json",
    "r1_full/r1_full_result.json",
    "r1_full/r1_full_result.md",
    "r1_derisk/derisk_result.json",
    "r1_derisk/derisk_result.md",
    "het_pec_derisk/derisk_result.json",
    "het_pec_derisk/derisk_result.md",
    "cdr/p0_validity_evidence.json",
    "cdr/p0_validity_evidence.md",
    "cdr/cdr_decision_invariance_note.md",
    "phase_diagram/grid.csv",
]

EXPECTED_COEXIST_COUNTS = {
    768: 5,
    1536: 7,
    3072: 7,
    6144: 7,
}

FLOAT_COLUMNS = ["mse_raw", "mse_pec", "gri_raw", "gri_pec"]
DECISION_COLUMNS = ["mse_better", "decision_worse", "coexist"]


class VerificationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise VerificationError(f"invalid boolean value: {value!r}")


def load_manifest(reference_root: Path) -> dict:
    path = reference_root / MANIFEST_NAME
    if not path.exists():
        raise VerificationError(f"extension manifest missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerificationError(f"invalid extension manifest JSON: {exc}") from exc


def verify_manifest(reference_root: Path, manifest: dict) -> None:
    checksums = manifest.get("checksums")
    if not isinstance(checksums, dict):
        raise VerificationError("manifest checksums must be a dictionary")

    expected = set(EXPECTED_OUTPUTS)
    observed = set(checksums)
    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    if missing:
        raise VerificationError(f"missing extension outputs: {missing}")
    if extra:
        raise VerificationError(f"unexpected extension outputs: {extra}")

    mismatches = []
    for rel, expected_hash in sorted(checksums.items()):
        path = reference_root / rel
        if not path.exists():
            mismatches.append(f"MISSING {rel}")
            continue
        actual = "sha256:" + sha256(path)
        if actual.upper() != str(expected_hash).upper():
            mismatches.append(f"{rel}: expected {expected_hash}, actual {actual}")
    if mismatches:
        raise VerificationError("extension checksum mismatches:\n" + "\n".join(mismatches))


def load_archived_coexistence(reference_root: Path) -> list[dict]:
    path = reference_root / "proof_of_mechanism" / "coexistence_by_instance.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_derived_row(row: dict) -> dict:
    return {
        "instance_id": str(row["instance_id"]),
        "budget": int(row["budget"]),
        "mse_raw": float(row["mse_raw"]),
        "mse_pec": float(row["mse_pec"]),
        "gri_raw": float(row["gri_raw"]),
        "gri_pec": float(row["gri_pec"]),
        "mse_better": bool(row["mse_better"]),
        "decision_worse": bool(row["decision_worse"]),
        "coexist": bool(row["coexist"]),
    }


def normalize_archived_row(row: dict) -> dict:
    return {
        "instance_id": str(row["instance_id"]),
        "budget": int(row["budget"]),
        "mse_raw": float(row["mse_raw"]),
        "mse_pec": float(row["mse_pec"]),
        "gri_raw": float(row["gri_raw"]),
        "gri_pec": float(row["gri_pec"]),
        "mse_better": parse_bool(row["mse_better"]),
        "decision_worse": parse_bool(row["decision_worse"]),
        "coexist": parse_bool(row["coexist"]),
    }


def verify_coexistence_table(reference_root: Path) -> None:
    from experiments import proof_of_mechanism_coexistence_table as table

    derived_rows = [normalize_derived_row(row) for row in table.build_rows()]
    summary = table.summarize(derived_rows)
    table.self_check(summary)

    archived_rows = [normalize_archived_row(row) for row in load_archived_coexistence(reference_root)]
    derived_keyed = {
        (row["instance_id"], row["budget"]): row
        for row in derived_rows
    }
    archived_keyed = {
        (row["instance_id"], row["budget"]): row
        for row in archived_rows
    }
    if set(derived_keyed) != set(archived_keyed):
        missing = sorted(set(derived_keyed) - set(archived_keyed))
        extra = sorted(set(archived_keyed) - set(derived_keyed))
        raise VerificationError(f"coexistence row keys differ: missing={missing} extra={extra}")

    diffs = []
    for key in sorted(derived_keyed):
        derived = derived_keyed[key]
        archived = archived_keyed[key]
        for column in DECISION_COLUMNS:
            if derived[column] != archived[column]:
                diffs.append(f"{key} {column}: derived={derived[column]} archived={archived[column]}")
        for column in FLOAT_COLUMNS:
            delta = abs(float(derived[column]) - float(archived[column]))
            if delta > LEVEL2_FLOAT_ATOL:
                diffs.append(
                    f"{key} {column}: derived={derived[column]:.17g} "
                    f"archived={archived[column]:.17g} delta={delta:.3g}"
                )
    if diffs:
        raise VerificationError("coexistence table differs:\n" + "\n".join(diffs))

    archived_counts = {}
    for budget in sorted(EXPECTED_COEXIST_COUNTS):
        rows = [row for row in archived_rows if int(row["budget"]) == budget]
        archived_counts[budget] = sum(bool(row["coexist"]) for row in rows)
    for budget, expected in EXPECTED_COEXIST_COUNTS.items():
        actual = archived_counts.get(budget)
        if actual != expected:
            raise VerificationError(f"coexist count mismatch budget={budget}: {actual} != {expected}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", default=str(REFERENCE_ROOT))
    args = parser.parse_args(argv)

    reference_root = Path(args.reference)
    manifest = load_manifest(reference_root)
    verify_manifest(reference_root, manifest)
    verify_coexistence_table(reference_root)

    print("EXTENSION VERIFY PASS")
    print(f"outputs={len(EXPECTED_OUTPUTS)}")
    for budget, count in EXPECTED_COEXIST_COUNTS.items():
        print(f"proof_of_mechanism budget={budget} coexist={count}/8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
