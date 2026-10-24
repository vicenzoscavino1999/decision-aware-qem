"""Regenerate the isolated CDR P0 validity evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from daqem.cdr import load_cdr_config, run_cdr, smoke_validity_checks
from daqem.noise import depolarizing_noise_model
from daqem.qaoa import default_angles, maxcut_graph


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "results" / "cdr"
P0_GRAPH_SEEDS = [260616, 260617, 260618, 260619, 260620, 260621]


def _row_for_seed(seed: int, index: int, config: dict) -> dict:
    depth = 2
    gammas, betas = default_angles(depth)
    instance_id = f"CDR_P0_VALIDITY_S{index:03d}"
    result = run_cdr(
        maxcut_graph(num_qubits=10, degree=3, seed=seed),
        depth=depth,
        gammas=gammas,
        betas=betas,
        instance_id=instance_id,
        config=config,
        noise_model=depolarizing_noise_model(),
    )
    noisy_error = abs(result.target_noisy - result.target_exact)
    mitigated_error = abs(result.target_mitigated - result.target_exact)
    return {
        "instance_id": instance_id,
        "graph_seed": int(seed),
        "training_exact_min": float(np.min(result.training_exact)),
        "training_exact_max": float(np.max(result.training_exact)),
        "training_exact_std": float(np.std(result.training_exact)),
        "target_exact": float(result.target_exact),
        "target_noisy": float(result.target_noisy),
        "target_mitigated": float(result.target_mitigated),
        "fit_a": float(result.fit.a),
        "fit_b": float(result.fit.b),
        "training_noisy": result.training_noisy.tolist(),
        "training_exact": result.training_exact.tolist(),
        "C_train": result.c_train,
        "abs_slope": abs(float(result.fit.a)),
        "error_noisy": float(noisy_error),
        "error_mitigated": float(mitigated_error),
        "error_ratio_mitigated_over_noisy": float(mitigated_error / noisy_error)
        if noisy_error
        else None,
        "validity_checks": smoke_validity_checks(result, config),
    }


def build_evidence() -> dict:
    config = load_cdr_config()
    rows = [_row_for_seed(seed, index, config) for index, seed in enumerate(P0_GRAPH_SEEDS, 1)]
    for row in rows:
        row["validity_pass"] = bool(all(row["validity_checks"].values()))
    return {
        "summary": {
            "protocol_date": "2026-06-24",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "profile": "P0 validity evidence; non-confirmatory graph seeds; no pipeline/C-ids",
            "num_instances": len(rows),
            "instances_improved": sum(
                1 for row in rows if row["error_mitigated"] < row["error_noisy"]
            ),
            "instances_passed_all_validity_checks": sum(
                1 for row in rows if row["validity_pass"]
            ),
            "training_exact_std_range": [
                min(row["training_exact_std"] for row in rows),
                max(row["training_exact_std"] for row in rows),
            ],
            "abs_slope_range": [
                min(row["abs_slope"] for row in rows),
                max(row["abs_slope"] for row in rows),
            ],
            "error_ratio_mitigated_over_noisy_range": [
                min(row["error_ratio_mitigated_over_noisy"] for row in rows),
                max(row["error_ratio_mitigated_over_noisy"] for row in rows),
            ],
            "all_improved": all(row["error_mitigated"] < row["error_noisy"] for row in rows),
            "all_passed_validity_bar": all(row["validity_pass"] for row in rows),
        },
        "instances": rows,
    }


def evidence_markdown(evidence: dict) -> str:
    summary = evidence["summary"]
    rows = evidence["instances"]
    lines = [
        "# CDR P0 Validity Evidence",
        "",
        f"Generated: {summary['generated_at_utc']}",
        "",
        "Scope: non-confirmatory graph seeds only; no C-ids, no pipeline run, no freeze update.",
        "",
        "## Summary",
        "",
        "| metric | value |",
        "|---|---:|",
        f"| instances | {summary['num_instances']} |",
        f"| instances improved | {summary['instances_improved']} |",
        f"| instances passed all validity checks | {summary['instances_passed_all_validity_checks']} |",
        f"| training_exact_std range | {summary['training_exact_std_range']} |",
        f"| abs(slope) range | {summary['abs_slope_range']} |",
        f"| error_mitigated/error_noisy range | {summary['error_ratio_mitigated_over_noisy_range']} |",
        "",
        "## Instance Evidence",
        "",
        "| instance | graph_seed | training_exact_std | target_bracketed | abs_slope | error_noisy | error_mitigated | ratio | pass |",
        "|---|---:|---:|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| {instance_id} | {graph_seed} | {training_exact_std} | {target_bracketed} | "
            "{abs_slope} | {error_noisy} | {error_mitigated} | {ratio} | {validity_pass} |".format(
                instance_id=row["instance_id"],
                graph_seed=row["graph_seed"],
                training_exact_std=row["training_exact_std"],
                target_bracketed=str(row["validity_checks"]["target_bracketed"]).lower(),
                abs_slope=row["abs_slope"],
                error_noisy=row["error_noisy"],
                error_mitigated=row["error_mitigated"],
                ratio=row["error_ratio_mitigated_over_noisy"],
                validity_pass=str(row["validity_pass"]).lower(),
            )
        )
    lines.extend(
        [
            "",
            f"{summary['instances_passed_all_validity_checks']}/{summary['num_instances']} instances pass the P0 validity bar; {summary['instances_improved']}/{summary['num_instances']} improve the target estimate.",
            "",
        ]
    )
    return "\n".join(lines)


def write_evidence(output_dir: Path) -> tuple[Path, Path, dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence = build_evidence()
    json_path = output_dir / "p0_validity_evidence.json"
    md_path = output_dir / "p0_validity_evidence.md"
    json_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(evidence_markdown(evidence), encoding="utf-8")
    return json_path, md_path, evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    json_path, md_path, evidence = write_evidence(args.output_dir)
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print(json.dumps(evidence["summary"], indent=2, sort_keys=True))
    return 0 if evidence["summary"]["all_passed_validity_bar"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
