from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import archive_confirmatory_outputs as archive  # noqa: E402


DEFAULT_ARCHIVE = (
    Path(__file__).resolve().parents[1] / "reproducibility" / "reference_confirmatory"
)
FLOAT_TOL = 1e-6


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _compare(expected, actual, path: str = "root") -> list[str]:
    errors: list[str] = []
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: expected dict, got {type(actual).__name__}"]
        for key in expected:
            if key not in actual:
                errors.append(f"{path}.{key}: missing")
            else:
                errors.extend(_compare(expected[key], actual[key], f"{path}.{key}"))
        for key in actual:
            if key not in expected:
                errors.append(f"{path}.{key}: unexpected")
        return errors
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            return [f"{path}: list mismatch"]
        for idx, (lhs, rhs) in enumerate(zip(expected, actual, strict=True)):
            errors.extend(_compare(lhs, rhs, f"{path}[{idx}]"))
        return errors
    if isinstance(expected, bool):
        if actual is not expected:
            errors.append(f"{path}: verdict flip expected={expected} actual={actual}")
        return errors
    if isinstance(expected, int) and not isinstance(expected, bool):
        if actual != expected:
            errors.append(f"{path}: integer mismatch expected={expected} actual={actual}")
        return errors
    if isinstance(expected, float):
        if not isinstance(actual, (int, float)) or not math.isfinite(float(actual)):
            errors.append(f"{path}: expected finite float, got {actual!r}")
        elif abs(float(actual) - expected) > FLOAT_TOL:
            errors.append(
                f"{path}: float mismatch expected={expected} actual={actual}"
            )
        return errors
    if actual != expected:
        errors.append(f"{path}: mismatch expected={expected!r} actual={actual!r}")
    return errors


def check_integrity(archive_root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = archive_root / "confirmatory_manifest.json"
    if not manifest_path.exists():
        return [f"missing manifest: {manifest_path}"]
    manifest = _load_json(manifest_path)
    checksums = manifest.get("checksums")
    if not isinstance(checksums, dict):
        return ["manifest checksums must be a dictionary"]
    for rel, expected in sorted(checksums.items()):
        path = archive_root / rel
        if not path.exists():
            errors.append(f"missing archived file: {rel}")
            continue
        actual = archive.sha256(path)
        if actual != expected:
            errors.append(f"checksum mismatch: {rel} expected={expected} actual={actual}")
    return errors


def check_completeness(archive_root: Path) -> list[str]:
    errors: list[str] = []

    def expect_count(pattern: str, expected: int, label: str) -> None:
        actual = len(list(archive_root.glob(pattern)))
        if actual != expected:
            errors.append(f"{label}: expected {expected}, found {actual}")

    expect_count("raw/*.npz", 48, "raw npz")
    expect_count("a3/*.npz", 48, "A3 prediction npz")
    expect_count("e2/instances/C*_results.csv", 32, "E2 results csv")
    expect_count("e2/instances/C*_trace.csv", 32, "E2 trace csv")
    expect_count("e2/instances/C*_cost.json", 32, "E2 cost json")

    required = [
        "e1/e1_static_decision_failure.csv",
        "e1/e1_static_selector_table.csv",
        "e3/e3_pullback_frontier.csv",
        "e2/checkpoint.json",
        "confirmatory_claims_summary.json",
    ]
    for rel in required:
        if not (archive_root / rel).exists():
            errors.append(f"missing required file: {rel}")
    return errors


def check_claims_summary(archive_root: Path) -> list[str]:
    stored = _load_json(archive_root / "confirmatory_claims_summary.json")
    derived = archive.derive_claims_summary(archive_root)
    return _compare(stored, derived, "confirmatory_claims_summary")


def verify(archive_root: Path) -> tuple[bool, list[str], dict]:
    errors = []
    errors.extend(check_integrity(archive_root))
    errors.extend(check_completeness(archive_root))
    if not errors:
        errors.extend(check_claims_summary(archive_root))
    summary = {}
    summary_path = archive_root / "confirmatory_claims_summary.json"
    if summary_path.exists():
        summary = _load_json(summary_path)
    return not errors, errors, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-root", default=str(DEFAULT_ARCHIVE))
    args = parser.parse_args(argv)
    archive_root = Path(args.archive_root)

    ok, errors, summary = verify(archive_root)
    if ok:
        print("CONFIRMATORY VERIFY PASS")
        e1 = summary["e1"]["aggregate"]
        e2 = summary["e2"]
        e3 = summary["e3"]
        print(
            "E1@512 paired_n={paired_n} b={b} c={c} "
            "failure_rate_MSE={failure_rate_MSE:.6f} "
            "failure_rate_DA={failure_rate_DA:.6f}".format(**e1)
        )
        print(
            "E3 active_pairs={active_pairs} ordering_matches={ordering_matches} "
            "directional_match_fraction={directional_match_fraction:.6f}".format(
                **e3
            )
        )
        print(
            "E2 reaches_0.80 DA={da} MSE={mse} "
            "DA_instances={da_n} MSE_instances={mse_n}".format(
                da=e2["reaches_0.80"]["DA"],
                mse=e2["reaches_0.80"]["MSE"],
                da_n=e2["per_instance_reach_counts"]["DA_reaches"],
                mse_n=e2["per_instance_reach_counts"]["MSE_reaches"],
            )
        )
        return 0

    print("CONFIRMATORY VERIFY FAIL")
    for error in errors:
        print(f"- {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
