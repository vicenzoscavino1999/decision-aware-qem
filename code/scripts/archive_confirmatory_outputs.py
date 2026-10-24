from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import statistics
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO_ROOT / "results" / "confirmatory"
DEFAULT_ARCHIVE = REPO_ROOT / "reproducibility" / "reference_confirmatory"
EXPECTED_FREEZE_HASH = (
    "sha256:C25B4F0243F41C12F8AC685ADAF150E79E066D9910B4EEEF1707E0F9BA5A66EA"
)
LEVEL2_ABS_TOL = 1e-6
ONE_SIDED_ALPHA_005_Z = 1.6448536269514722


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest().upper()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _bool(value: str) -> bool:
    return str(value).strip().lower() == "true"


def _aggregate_paired(rows: list[dict[str, str]]) -> dict:
    both_fail = sum(int(r["both_fail"]) for r in rows)
    both_ok = sum(int(r["both_ok"]) for r in rows)
    b = sum(int(r["b"]) for r in rows)
    c = sum(int(r["c"]) for r in rows)
    paired_n = sum(int(r["paired_n"]) for r in rows)
    mse_fail = both_fail + b
    da_fail = both_fail + c
    failure_rate_mse = mse_fail / paired_n if paired_n else 0.0
    failure_rate_da = da_fail / paired_n if paired_n else 0.0
    observed_rel_reduction = (
        (failure_rate_mse - failure_rate_da) / failure_rate_mse
        if failure_rate_mse
        else 0.0
    )
    z = (b - c) / math.sqrt(b + c) if (b + c) else 0.0
    return {
        "both_fail": both_fail,
        "both_ok": both_ok,
        "b": b,
        "c": c,
        "paired_n": paired_n,
        "failure_rate_MSE": failure_rate_mse,
        "failure_rate_DA": failure_rate_da,
        "observed_rel_reduction": observed_rel_reduction,
        "mcnemar_z": z,
        "one_sided_reject": z > ONE_SIDED_ALPHA_005_Z,
    }


def derive_e1_summary(e1_csv: Path, budget: int = 512) -> dict:
    rows = _read_csv(e1_csv)
    budget_rows = [r for r in rows if int(r["budget"]) == budget]
    terciles = {}
    for tercile in ["easy", "medium", "hard"]:
        tercile_rows = [
            r for r in budget_rows if r.get("epsilon_opt_tercile") == tercile
        ]
        terciles[tercile] = _aggregate_paired(tercile_rows)
    return {
        "budget": budget,
        "aggregate": _aggregate_paired(budget_rows),
        "epsilon_opt_terciles": terciles,
    }


def derive_e3_summary(e3_csv: Path) -> dict:
    rows = _read_csv(e3_csv)
    active = [r for r in rows if _bool(r["active_pair"])]
    ordering_matches = sum(_bool(r["ordering_match"]) for r in active)
    active_pairs = len(active)
    return {
        "active_pairs": active_pairs,
        "ordering_matches": ordering_matches,
        "directional_match_fraction": (
            ordering_matches / active_pairs if active_pairs else 0.0
        ),
        "directionally_sensitive_pass": sum(
            r["pass_label"] == "directionally_sensitive_pass" for r in rows
        ),
        "fail": sum(r["pass_label"] == "fail" for r in rows),
    }


def _result_rows(instances_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(instances_dir.glob("*_results.csv")):
        rows.extend(_read_csv(path))
    return rows


def derive_e2_summary(instances_dir: Path, threshold: float = 0.80) -> dict:
    rows = _result_rows(instances_dir)
    if not rows:
        raise FileNotFoundError(f"no E2 result rows found in {instances_dir}")
    budgets = sorted({int(r["budget"]) for r in rows})
    selectors = ["DA", "MSE"]

    aggregate: dict[str, dict[str, float]] = {selector: {} for selector in selectors}
    max_success: dict[str, float] = {}
    reaches: dict[str, bool] = {}
    for selector in selectors:
        values = []
        for budget in budgets:
            bucket = [
                r
                for r in rows
                if r["selector"] == selector and int(r["budget"]) == budget
            ]
            if not bucket:
                raise ValueError(f"missing E2 rows for {selector} budget={budget}")
            value = sum(_bool(r["success_decision"]) for r in bucket) / len(bucket)
            aggregate[selector][str(budget)] = value
            values.append(value)
        max_success[selector] = max(values)
        reaches[selector] = max_success[selector] >= threshold

    instances = sorted({r["instance"] for r in rows})
    reach_counts = {selector: 0 for selector in selectors}
    shot_ratios: list[float] = []
    per_instance: dict[str, dict] = {}
    for instance in instances:
        instance_crossing: dict[str, int | None] = {}
        for selector in selectors:
            crossing_cost: int | None = None
            for budget in budgets:
                bucket = [
                    r
                    for r in rows
                    if r["instance"] == instance
                    and r["selector"] == selector
                    and int(r["budget"]) == budget
                ]
                if not bucket:
                    raise ValueError(
                        f"missing E2 rows for {instance} {selector} budget={budget}"
                    )
                p_success = sum(_bool(r["success_decision"]) for r in bucket) / len(
                    bucket
                )
                if p_success >= threshold:
                    costs = sorted(
                        {int(float(r["cost_per_candidate_shots"])) for r in bucket}
                    )
                    crossing_cost = costs[0]
                    break
            instance_crossing[selector] = crossing_cost
            reach_counts[selector] += int(crossing_cost is not None)
        if (
            instance_crossing["DA"] is not None
            and instance_crossing["MSE"] is not None
        ):
            shot_ratios.append(
                instance_crossing["MSE"] / instance_crossing["DA"]  # type: ignore[operator]
            )
        per_instance[instance] = {
            "DA_B80_cost_per_candidate_shots": instance_crossing["DA"],
            "MSE_B80_cost_per_candidate_shots": instance_crossing["MSE"],
        }

    return {
        "threshold": threshold,
        "budgets": budgets,
        "aggregate_success_decision": aggregate,
        "max_success": {"DA": max_success["DA"], "MSE": max_success["MSE"]},
        "reaches_0.80": {"DA": reaches["DA"], "MSE": reaches["MSE"]},
        "per_instance_reach_counts": {
            "DA_reaches": reach_counts["DA"],
            "MSE_reaches": reach_counts["MSE"],
            "instances": len(instances),
        },
        "median_shot_ratio_MSE_over_DA_where_both_reach": (
            statistics.median(shot_ratios) if shot_ratios else None
        ),
        "per_instance_B80_cost_per_candidate_shots": per_instance,
    }


def derive_claims_summary(archive_root: Path) -> dict:
    return {
        "level2_abs_tolerance": LEVEL2_ABS_TOL,
        "result_neutral": True,
        "e1": derive_e1_summary(
            archive_root / "e1" / "e1_static_decision_failure.csv"
        ),
        "e3": derive_e3_summary(archive_root / "e3" / "e3_pullback_frontier.csv"),
        "e2": derive_e2_summary(archive_root / "e2" / "instances"),
    }


def _copy_file(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_confirmatory_outputs(source_root: Path, archive_root: Path) -> list[Path]:
    copied: list[Path] = []
    mappings = [
        ("e1_static_decision_failure.csv", "e1/e1_static_decision_failure.csv"),
        ("e1_static_selector_table.csv", "e1/e1_static_selector_table.csv"),
        ("e1_static_decision_failure.md", "e1/e1_static_decision_failure.md"),
        ("e3_pullback_frontier.csv", "e3/e3_pullback_frontier.csv"),
        ("e3_pullback_frontier.md", "e3/e3_pullback_frontier.md"),
        ("full/checkpoint.json", "e2/checkpoint.json"),
    ]
    for src_rel, dst_rel in mappings:
        dst = archive_root / dst_rel
        _copy_file(source_root / src_rel, dst)
        copied.append(dst)

    for pattern, dst_dir in [
        ("raw/*.npz", "raw"),
        ("a3_frozen_prediction/*.npz", "a3"),
        ("full/instances/C*_results.csv", "e2/instances"),
        ("full/instances/C*_trace.csv", "e2/instances"),
        ("full/instances/C*_cost.json", "e2/instances"),
    ]:
        paths = sorted(source_root.glob(pattern))
        if not paths:
            raise FileNotFoundError(f"no files matched {source_root / pattern}")
        for src in paths:
            dst = archive_root / dst_dir / src.name
            _copy_file(src, dst)
            copied.append(dst)
    return copied


def write_manifest(archive_root: Path, *, created_utc: str | None = None) -> dict:
    pap_hash = (REPO_ROOT / "PAP_HASH.txt").read_text(encoding="utf-8").strip()
    if created_utc is None:
        created_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    summary_path = archive_root / "confirmatory_claims_summary.json"
    summary = derive_claims_summary(archive_root)
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    checksum_paths = [
        p
        for p in archive_root.rglob("*")
        if p.is_file()
        and p.name not in {"confirmatory_manifest.json", "checksums.sha256"}
    ]
    checksums = {
        p.relative_to(archive_root).as_posix(): sha256(p) for p in sorted(checksum_paths)
    }
    manifest = {
        "pap_hash": pap_hash,
        "freeze_hash": EXPECTED_FREEZE_HASH,
        "created_utc": created_utc,
        "checksums": checksums,
    }
    (archive_root / "confirmatory_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    checksum_lines = []
    for rel, digest in sorted(checksums.items()):
        checksum_lines.append(f"{digest.removeprefix('sha256:')}  {rel}")
    (archive_root / "checksums.sha256").write_text(
        "\n".join(checksum_lines) + "\n", encoding="utf-8"
    )
    return manifest


def archive(source_root: Path, archive_root: Path) -> dict:
    archive_root.mkdir(parents=True, exist_ok=True)
    copy_confirmatory_outputs(source_root, archive_root)
    return write_manifest(archive_root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", default=str(DEFAULT_SOURCE))
    parser.add_argument("--archive-root", default=str(DEFAULT_ARCHIVE))
    args = parser.parse_args(argv)

    manifest = archive(Path(args.source_root), Path(args.archive_root))
    print(
        json.dumps(
            {
                "archive_root": str(Path(args.archive_root)),
                "files_hashed": len(manifest["checksums"]),
                "pap_hash": manifest["pap_hash"],
                "freeze_hash": manifest["freeze_hash"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
