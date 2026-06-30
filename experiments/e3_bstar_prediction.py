from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

from experiments.a3_pullback_frontier import (
    _sha256,
    analyze_cell_from_frozen_prediction,
    load_config as load_a3_config,
)
from experiments.gate0_pilot_full_vs_diagonal import load_config as load_gate0_config


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "results"
E3_CSV_REL = Path("confirmatory") / "e3_pullback_frontier.csv"
E3_REPORT_REL = Path("confirmatory") / "e3_pullback_frontier.md"


def _profile_config(profile: str) -> dict:
    if profile == "confirmatory_e3_smoke":
        config = load_a3_config("confirmatory_smoke")
        config["profile"] = profile
        config["allow_budget_subset"] = True
        return config
    if profile in {"full", "confirmatory_full"}:
        config = load_a3_config("confirmatory_full")
        config["profile"] = profile
        config["gate0_config"] = load_gate0_config("confirmatory_full")
        config["allow_budget_subset"] = False
        return config
    raise ValueError(f"unknown E3 profile: {profile}")


def _frozen_path(output_root: Path, instance_id: str) -> Path:
    return output_root / "confirmatory" / "a3_frozen_prediction" / f"{instance_id}.npz"


def analyze_confirmatory_instance(
    *,
    output_root: Path,
    instance_id: str,
    config: dict,
) -> pd.DataFrame:
    frozen_path = _frozen_path(output_root, instance_id)
    if not frozen_path.exists():
        raise FileNotFoundError(f"missing confirmatory A3 frozen prediction: {frozen_path}")
    return analyze_cell_from_frozen_prediction(
        instance_id=instance_id,
        frozen_path=frozen_path,
        frozen_hash=_sha256(frozen_path),
        output_root=output_root,
        config=config,
    )


def directional_summary(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    active = df[df["active_pair"]].copy()
    by_instance_rows = []
    for instance_id, group in active.groupby("problem_cell", sort=True):
        total = int(len(group))
        matches = int(group["ordering_match"].sum())
        by_instance_rows.append(
            {
                "problem_cell": str(instance_id),
                "active_pairs": total,
                "ordering_matches": matches,
                "directional_match_fraction": matches / float(total) if total else float("nan"),
                "directionally_sensitive_pass": int(
                    (group["pass_label"] == "directionally_sensitive_pass").sum()
                ),
                "frobenius_proxy_only": int(
                    (group["pass_label"] == "frobenius_proxy_only").sum()
                ),
                "fail": int((group["a3_status"] == "fail").sum()),
            }
        )
    by_instance = pd.DataFrame(by_instance_rows)
    total_active = int(len(active))
    total_matches = int(active["ordering_match"].sum()) if total_active else 0
    aggregate = {
        "instances": int(df["problem_cell"].nunique()),
        "active_pairs": total_active,
        "ordering_matches": total_matches,
        "directional_match_fraction": (
            total_matches / float(total_active) if total_active else None
        ),
        "directionally_sensitive_pass": int(
            (active["pass_label"] == "directionally_sensitive_pass").sum()
        )
        if total_active
        else 0,
        "frobenius_proxy_only": int((active["pass_label"] == "frobenius_proxy_only").sum())
        if total_active
        else 0,
        "fail": int((active["a3_status"] == "fail").sum()) if total_active else 0,
    }
    return by_instance, aggregate


def write_report(
    *,
    output_root: Path,
    profile: str,
    rows: pd.DataFrame,
    by_instance: pd.DataFrame,
    aggregate: dict[str, object],
) -> Path:
    out = output_root / E3_REPORT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    fraction = aggregate["directional_match_fraction"]
    fraction_text = "NA" if fraction is None else f"{float(fraction):.6g}"
    lines = [
        "# E3 Pullback Frontier Directional Validation",
        "",
        "Confirmatory runner for Claim 3B. Reuses `a3_pullback_frontier.analyze_cell_from_frozen_prediction`; outputs are under results/confirmatory.",
        "",
        "## Endpoint",
        "",
        "- venue: 3B-directional",
        "- endpoint: fraction of active pairs with `predicted_order == empirical_order`.",
        "- not_a_literal_Bstar_crossing: true",
        f"- profile: {profile}",
        "",
        "## Aggregate Directional Metric",
        "",
        "| instances | active_pairs | ordering_matches | directional_match_fraction | directionally_sensitive_pass | frobenius_proxy_only | fail |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        "| {instances} | {active_pairs} | {ordering_matches} | "
        f"{fraction_text} | "
        "{directionally_sensitive_pass} | {frobenius_proxy_only} | {fail} |".format(
            **aggregate
        ),
        "",
        "## By Instance",
        "",
        "| problem_cell | active_pairs | ordering_matches | directional_match_fraction | directionally_sensitive_pass | frobenius_proxy_only | fail |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    if by_instance.empty:
        lines.append("| none | 0 | 0 | NA | 0 | 0 | 0 |")
    else:
        for row in by_instance.to_dict("records"):
            lines.append(
                "| {problem_cell} | {active_pairs} | {ordering_matches} | "
                "{directional_match_fraction:.6g} | {directionally_sensitive_pass} | "
                "{frobenius_proxy_only} | {fail} |".format(**row)
            )
    lines.extend(
        [
            "",
            "## Frontier Rows",
            "",
            "| problem_cell | pair_id | budget | active_pair | predicted_order | empirical_order | ordering_match | a3_status | pass_label |",
            "|---|---|---:|---|---|---|---|---|---|",
        ]
    )
    for row in rows.sort_values(["problem_cell", "budget", "pair_id"]).to_dict("records"):
        lines.append(
            "| {problem_cell} | {pair_id} | {budget} | {active_pair} | "
            "{predicted_order} | {empirical_order} | {ordering_match} | "
            "{a3_status} | {pass_label} |".format(**row)
        )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def run(
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    *,
    profile: str = "confirmatory_e3_smoke",
) -> dict[str, object]:
    config = _profile_config(profile)
    frames = [
        analyze_confirmatory_instance(
            output_root=output_root,
            instance_id=str(instance_id),
            config=config,
        )
        for instance_id in config["instance_ids"]
    ]
    rows = pd.concat(frames, ignore_index=True).drop(columns=["_frozen_hash"])
    out = output_root / E3_CSV_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(out, index=False)
    by_instance, aggregate = directional_summary(rows)
    report = write_report(
        output_root=output_root,
        profile=profile,
        rows=rows,
        by_instance=by_instance,
        aggregate=aggregate,
    )
    payload = {
        "profile": profile,
        "output": E3_CSV_REL.as_posix(),
        "report": E3_REPORT_REL.as_posix(),
        "rows": int(len(rows)),
        "aggregate": aggregate,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--profile", default="confirmatory_e3_smoke")
    args = parser.parse_args(argv)
    run(Path(args.output).resolve(), profile=args.profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
