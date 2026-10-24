from __future__ import annotations

import hashlib
import json
import re
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
    runtime=manifest.get('runtime_contract',{})
    expected_runtime={'Dockerfile','requirements-lock.linux.txt','reproduce.py'}
    runtime_checks=runtime.get('checksums',{})
    if set(runtime_checks)!=expected_runtime:errors.append('Runtime freeze inventory mismatch')
    for name in expected_runtime:
        file=REPO_ROOT.parent/name
        if not file.is_file() or runtime_checks.get(name,'').upper()!='SHA256:'+sha256(file):
            errors.append(f'Runtime freeze mismatch: {name}')
    images=re.findall(r'^FROM\s+(\S+)',(REPO_ROOT.parent/'Dockerfile').read_text(),flags=re.MULTILINE)
    if images!=runtime.get('base_images') or not images or any('@sha256:' not in image for image in images):
        errors.append('Docker image digest mismatch')
    from scripts.build_freeze_manifest import freeze_file_list,freeze_hash_from_checksums
    expected_files={path.as_posix() for path in freeze_file_list()}
    if set(checksums)!=expected_files:
        errors.append('Freeze file inventory differs from the explicit release contract')
    if manifest.get('freeze_hash')!=freeze_hash_from_checksums(checksums):
        errors.append('Freeze summary hash does not match the ordered file hashes')
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
    if file_pap_hash.upper()!='SHA256:'+sha256(REPO_ROOT/'EXPERIMENTAL_PLAN_v13_PRXQ.md'):
        errors.append('PAP content does not match its immutable anchor')

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
