from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FREEZE_MANIFEST = REPO_ROOT / "results" / "frozen" / "freeze_manifest.json"
PAP_HASH_FILE = REPO_ROOT / "PAP_HASH.txt"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    if not FREEZE_MANIFEST.exists():
        print(f"FREEZE AUDIT FAIL: missing {FREEZE_MANIFEST}")
        return 1

    manifest = json.loads(FREEZE_MANIFEST.read_text(encoding="utf-8"))
    checksums = manifest.get("checksums")
    if not isinstance(checksums, dict):
        print("FREEZE AUDIT FAIL: manifest checksums must be a dictionary")
        return 1

    errors: list[str] = []
    for relpath, expected in sorted(checksums.items()):
        path = REPO_ROOT / relpath
        if not path.exists():
            errors.append(f"MISSING {relpath}")
            continue
        actual = "sha256:" + sha256(path)
        if actual.upper() != str(expected).upper():
            errors.append(f"DRIFT {relpath}: expected {expected}, actual {actual}")

    manifest_pap_hash = str(manifest.get("pap_hash", "")).strip()
    file_pap_hash = PAP_HASH_FILE.read_text(encoding="utf-8").strip()
    if manifest_pap_hash != file_pap_hash:
        errors.append(
            f"PAP_HASH mismatch: manifest={manifest_pap_hash} file={file_pap_hash}"
        )

    freeze_hash = str(manifest.get("freeze_hash", ""))
    if errors:
        print(f"FREEZE AUDIT FAIL: {len(errors)} discrepancy(s)")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        f"FREEZE AUDIT PASS: {len(checksums)}/{len(checksums)} intact, "
        f"freeze_hash={freeze_hash}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
