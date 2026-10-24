from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ROOT = REPO_ROOT / "reproducibility" / "hardware"
MANIFEST = ARCHIVE_ROOT / "hardware_manifest.json"

EXPECTED_RAW_COUNT_JOBS = [
    "d92mef8oamcc73db82v0",
    "d92pbgfd07jc73dvkveg",
    "d92plml958jc73bs50f0",
    "d92pnjnd07jc73dvld50",
    "d92poffd07jc73dvle10",
    "d92pp60oamcc73dbcdm0",
    "d92ppsooamcc73dbcec0",
    "d92pqji47v0s73814ppg",
    "d92prad958jc73bs56p0",
    "d92ps1247v0s73814r4g",
    "d92psnvd07jc73dvli70",
    "d92ptevd07jc73dvlj00",
    "d92pu5goamcc73dbcii0",
]

EXPECTED_FILES = [
    *(f"raw_counts/{job_id}.json" for job_id in EXPECTED_RAW_COUNT_JOBS),
    "calibration_snapshots/snapshot_2026-06-30_feasibility_record.json",
    "calibration_snapshots/snapshot_2026-07-01_1710_mapping_audit_v1_1.json",
    "job_metadata.json",
    "claim_status.json",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest().upper()


def main() -> int:
    if not MANIFEST.exists():
        print(f"HARDWARE ARCHIVE VERIFY FAIL: missing {MANIFEST}")
        return 1
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    checksums = manifest.get("checksums", {})
    failures: list[str] = []

    for relpath in EXPECTED_FILES:
        path = ARCHIVE_ROOT / relpath
        if not path.exists():
            failures.append(f"missing expected archive file: {relpath}")
        if relpath not in checksums:
            failures.append(f"missing checksum entry: {relpath}")

    for relpath, expected in sorted(checksums.items()):
        path = ARCHIVE_ROOT / relpath
        if not path.exists():
            failures.append(f"missing checksummed file: {relpath}")
            continue
        observed = sha256(path)
        if observed != expected:
            failures.append(f"checksum mismatch {relpath}: {observed} != {expected}")

    claim_path = ARCHIVE_ROOT / "claim_status.json"
    if claim_path.exists():
        claim_status = json.loads(claim_path.read_text(encoding="utf-8"))
        status = claim_status.get("hardware_sigma_microcell", {})
        if status.get("result_label") != "failed_or_inconclusive":
            failures.append("claim_status result_label is not failed_or_inconclusive")
        if status.get("device_level_language_allowed") is not False:
            failures.append("claim_status does not forbid device-level language")

    if failures:
        print("HARDWARE ARCHIVE VERIFY FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "HARDWARE ARCHIVE VERIFY PASS: "
        f"files={len(checksums)} raw_count_jobs={len(EXPECTED_RAW_COUNT_JOBS)} "
        "device_level_language_allowed=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
