from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
from qiskit_aer.noise import NoiseModel
from qiskit_ibm_runtime.fake_provider import FakeKolkataV2
from scipy.stats import norm

from daqem.candidates import CONFIRMATORY_INSTANCE_IDS, maxcut_graph_for_instance
from daqem.rng import make_rng

from experiments.derisk_fakebackend import run as derisk


OUTPUT_DIR = REPO_ROOT / "results" / "derisk_fakebackend_tier1"
INSTANCE_DIR = OUTPUT_DIR / "instances"
MANIFEST_PATH = REPO_ROOT / "results" / "frozen" / "confirmatory_instance_manifest.csv"
UNIFORM_E1_PATH = (
    REPO_ROOT
    / "reproducibility"
    / "reference_confirmatory"
    / "e1"
    / "e1_static_decision_failure.csv"
)
INSTANCE_IDS = tuple(CONFIRMATORY_INSTANCE_IDS)
ALPHA = 0.05
PRACTICAL_THRESHOLD = 0.15
BOOTSTRAP_REPS = 10_000
SECONDARY_CORRECTION = "Holm"


def _relative_reduction(*, both_fail: int, b: int, c: int, paired_n: int) -> tuple[float, float, float]:
    failure_mse = (int(both_fail) + int(b)) / float(paired_n)
    failure_da = (int(both_fail) + int(c)) / float(paired_n)
    rel = (failure_mse - failure_da) / failure_mse if failure_mse > 0.0 else 0.0
    return float(failure_mse), float(failure_da), float(rel)


def _paired_z_p(*, b: int, c: int, paired_n: int) -> tuple[float, float, bool]:
    if int(paired_n) <= 1:
        return 0.0, 1.0, False
    values = np.concatenate(
        [
            np.ones(int(b), dtype=float),
            -np.ones(int(c), dtype=float),
            np.zeros(int(paired_n) - int(b) - int(c), dtype=float),
        ]
    )
    se = float(np.std(values, ddof=1) / np.sqrt(int(paired_n)))
    if se <= 0.0:
        z = float("inf") if int(b) > int(c) else 0.0
    else:
        z = float(np.mean(values) / se)
    p_value = float(1.0 - norm.cdf(z))
    return z, p_value, bool(p_value < ALPHA)


def _bootstrap_ci(
    *,
    both_fail: int,
    both_ok: int,
    b: int,
    c: int,
    paired_n: int,
    label: str,
) -> list[float]:
    counts = np.array([both_fail, both_ok, b, c], dtype=float)
    probs = counts / counts.sum()
    rng = make_rng(
        instance_id="FakeBackendTier1",
        method="bootstrap",
        budget=derisk.B_STAR,
        replicate_id=0,
        stream=f"tier1_{label}_relative_reduction",
    )
    draws = rng.multinomial(int(paired_n), probs, size=BOOTSTRAP_REPS)
    rels = np.zeros(BOOTSTRAP_REPS, dtype=float)
    for idx, draw in enumerate(draws):
        failure_mse, failure_da, rel = _relative_reduction(
            both_fail=int(draw[0]),
            b=int(draw[2]),
            c=int(draw[3]),
            paired_n=int(draw.sum()),
        )
        rels[idx] = rel if failure_mse > 0.0 or failure_da > 0.0 else 0.0
    return [float(np.quantile(rels, 0.025)), float(np.quantile(rels, 0.975))]


def _pooled_paired_summary(frame: pd.DataFrame, *, label: str) -> dict[str, object]:
    if frame.empty:
        return {
            "label": label,
            "instances": 0,
            "rows": 0,
            "paired_n": 0,
            "both_fail": 0,
            "both_ok": 0,
            "b_DA_better": 0,
            "c_DA_worse": 0,
            "failure_rate_MSE": float("nan"),
            "failure_rate_DA": float("nan"),
            "observed_rel_reduction": float("nan"),
            "mcnemar_z": 0.0,
            "mcnemar_one_sided_p": 1.0,
            "mcnemar_one_sided_reject": False,
            "relative_reduction_bootstrap_ci": [float("nan"), float("nan")],
        }
    both_fail = int(frame["both_fail"].sum())
    both_ok = int(frame["both_ok"].sum())
    b = int(frame["b_DA_better"].sum())
    c = int(frame["c_DA_worse"].sum())
    paired_n = int(frame["paired_n"].sum())
    failure_mse, failure_da, rel = _relative_reduction(
        both_fail=both_fail,
        b=b,
        c=c,
        paired_n=paired_n,
    )
    z, p_value, reject = _paired_z_p(b=b, c=c, paired_n=paired_n)
    return {
        "label": label,
        "instances": int(frame["cell"].nunique()),
        "rows": int(len(frame)),
        "paired_n": paired_n,
        "both_fail": both_fail,
        "both_ok": both_ok,
        "b_DA_better": b,
        "c_DA_worse": c,
        "failure_rate_MSE": failure_mse,
        "failure_rate_DA": failure_da,
        "observed_rel_reduction": rel,
        "mcnemar_z": z,
        "mcnemar_one_sided_p": p_value,
        "mcnemar_one_sided_reject": reject,
        "relative_reduction_bootstrap_ci": _bootstrap_ci(
            both_fail=both_fail,
            both_ok=both_ok,
            b=b,
            c=c,
            paired_n=paired_n,
            label=label,
        ),
    }


def _holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    finite = {
        key: float(value)
        for key, value in p_values.items()
        if value is not None and np.isfinite(float(value))
    }
    ordered = sorted(finite, key=finite.get)
    m = len(ordered)
    out: dict[str, float] = {}
    running = 0.0
    for rank, key in enumerate(ordered):
        adjusted = min(1.0, (m - rank) * finite[key])
        running = max(running, adjusted)
        out[key] = running
    return out


def _load_manifest() -> pd.DataFrame:
    manifest = pd.read_csv(MANIFEST_PATH)
    expected = set(INSTANCE_IDS)
    found = set(manifest["instance_id"])
    missing = sorted(expected - found)
    if missing:
        raise RuntimeError(f"missing confirmatory manifest rows: {missing}")
    return manifest[manifest["instance_id"].isin(INSTANCE_IDS)].copy()


def _uniform_in_band_at_bstar() -> dict[str, bool]:
    table = pd.read_csv(UNIFORM_E1_PATH)
    subset = table[table["budget"] == derisk.B_STAR].copy()
    return {
        str(row["cell"]): bool(row["in_band"])
        for row in subset.to_dict("records")
    }


def _augment_table(table: pd.DataFrame) -> pd.DataFrame:
    manifest = _load_manifest()[
        ["instance_id", "epsilon_opt_ideal", "difficulty_tercile"]
    ].rename(
        columns={
            "instance_id": "cell",
            "difficulty_tercile": "epsilon_opt_tercile",
        }
    )
    out = table.merge(manifest, on="cell", how="left", validate="many_to_one")
    if out["epsilon_opt_tercile"].isna().any():
        missing = sorted(out.loc[out["epsilon_opt_tercile"].isna(), "cell"].unique())
        raise RuntimeError(f"missing epsilon terciles for {missing}")
    uniform = _uniform_in_band_at_bstar()
    out["uniform_in_band_B_star"] = out["cell"].map(uniform).fillna(False).astype(bool)
    out["instance_id"] = out["cell"]
    return out


def _secondary_summaries(table: pd.DataFrame) -> dict[str, object]:
    bstar = table[table["budget"] == derisk.B_STAR].copy()
    inferential: dict[str, dict[str, object]] = {}
    inferential["in_band_uniform_frozen"] = _pooled_paired_summary(
        bstar[bstar["uniform_in_band_B_star"]],
        label="in_band_uniform_frozen",
    )
    for label in ("easy", "medium", "hard"):
        inferential[f"epsilon_tercile_{label}"] = _pooled_paired_summary(
            bstar[bstar["epsilon_opt_tercile"] == label],
            label=f"epsilon_tercile_{label}",
        )
    inferential["auc_budget_grid"] = _pooled_paired_summary(
        table,
        label="auc_budget_grid",
    )
    adjusted = _holm_adjust(
        {
            key: float(value["mcnemar_one_sided_p"])
            for key, value in inferential.items()
            if int(value["paired_n"]) > 0
        }
    )
    for key, value in inferential.items():
        value["holm_adjusted_p"] = adjusted.get(key, None)
        value["holm_reject"] = (
            bool(adjusted[key] < ALPHA) if key in adjusted else False
        )

    d1_count = int(table["selector_changed_full_vs_diagonal"].sum())
    raw_rem_count = int((table["DA_selected_method"] == "Raw+REM").sum())
    diagnostics = {
        "D1_full_vs_diagonal": {
            "selector_changed_rows": d1_count,
            "total_rows": int(len(table)),
            "frequency": float(d1_count / len(table)),
            "test": "pre-specified diagnostic frequency; no valid null-hypothesis p-value assigned",
        },
        "DA_selects_Raw_REM": {
            "rows": raw_rem_count,
            "total_rows": int(len(table)),
            "frequency": float(raw_rem_count / len(table)),
            "test": "pre-specified diagnostic frequency; no valid null-hypothesis p-value assigned",
        },
    }
    return {
        "multiplicity": (
            "Holm correction applied to secondary inferential paired tests; "
            "D1 and Raw+REM frequency are reported as pre-specified diagnostic frequencies."
        ),
        "inferential": inferential,
        "diagnostics": diagnostics,
    }


def _mapping_rows(mappings: dict[str, object]) -> list[dict[str, object]]:
    rows = []
    for instance_id in sorted(mappings):
        mapping = mappings[instance_id]
        rows.append(
            {
                "instance_id": instance_id,
                "virtual_to_physical": json.dumps(mapping["virtual_to_physical"]),
                "final_measured_physical_by_logical": json.dumps(
                    mapping["final_measured_physical_by_logical"]
                ),
                "used_physical_qubits": json.dumps(mapping["used_physical_qubits"]),
                "transpiled_depth": int(mapping["transpiled_depth"]),
                "transpiled_size": int(mapping["transpiled_size"]),
                "swap_count": int(mapping["swap_count"]),
                "transpiled_ops": json.dumps(mapping["transpiled_ops"], sort_keys=True),
            }
        )
    return rows


def _checkpoint_paths(instance_id: str) -> dict[str, Path]:
    return {
        "rows": INSTANCE_DIR / f"{instance_id}_rows.csv",
        "mapping": INSTANCE_DIR / f"{instance_id}_mapping.json",
        "ordering": INSTANCE_DIR / f"{instance_id}_ordering.json",
        "metadata": INSTANCE_DIR / f"{instance_id}_metadata.json",
    }


def _load_checkpoint(instance_id: str) -> tuple[list[dict[str, object]], dict[str, object], dict[str, object], dict[str, object]] | None:
    paths = _checkpoint_paths(instance_id)
    if not all(path.exists() for path in paths.values()):
        return None
    rows = pd.read_csv(paths["rows"]).to_dict("records")
    mapping = json.loads(paths["mapping"].read_text(encoding="utf-8"))
    ordering = json.loads(paths["ordering"].read_text(encoding="utf-8"))
    metadata = json.loads(paths["metadata"].read_text(encoding="utf-8"))
    return rows, mapping, ordering, metadata


def _write_checkpoint(
    *,
    instance_id: str,
    rows: list[dict[str, object]],
    mapping: dict[str, object],
    ordering: dict[str, object],
    metadata: dict[str, object],
) -> None:
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    paths = _checkpoint_paths(instance_id)
    pd.DataFrame(rows).to_csv(paths["rows"], index=False)
    paths["mapping"].write_text(json.dumps(mapping, indent=2, sort_keys=True), encoding="utf-8")
    paths["ordering"].write_text(json.dumps(ordering, indent=2, sort_keys=True), encoding="utf-8")
    paths["metadata"].write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")


def _load_determinism() -> dict[str, object] | None:
    path = OUTPUT_DIR / "determinism_check.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_determinism(determinism: dict[str, object]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "determinism_check.json").write_text(
        json.dumps(determinism, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _markdown_table(frame: pd.DataFrame) -> str:
    return derisk._markdown_table(frame)


def _write_outputs(
    *,
    table: pd.DataFrame,
    mappings: dict[str, object],
    ordering_gates: list[dict[str, object]],
    determinism: dict[str, object],
    metadata: dict[str, object],
    duration_seconds: float,
) -> dict[str, object]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    table = _augment_table(table.sort_values(["cell", "budget"]).reset_index(drop=True))
    primary = _pooled_paired_summary(
        table[table["budget"] == derisk.B_STAR],
        label="primary_pooled_B_star_all_C_ids",
    )
    primary["practical_threshold"] = PRACTICAL_THRESHOLD
    primary["practical_pass"] = bool(
        float(primary["observed_rel_reduction"]) >= PRACTICAL_THRESHOLD
    )
    secondaries = _secondary_summaries(table)
    confirmed = bool(primary["mcnemar_one_sided_reject"])
    raw_at_bstar = table[table["budget"] == derisk.B_STAR]["failure_rate_Raw"]
    saturation = {
        "raw_failure_mean_at_B_star": float(raw_at_bstar.mean()),
        "raw_failure_rows_ge_0_95_at_B_star": int((raw_at_bstar >= 0.95).sum()),
        "total_rows_at_B_star": int(raw_at_bstar.shape[0]),
        "inconclusive_saturation_flag": bool((raw_at_bstar >= 0.95).all()),
    }
    decision = (
        "INCONCLUSIVE_SATURATED"
        if saturation["inconclusive_saturation_flag"]
        else ("CONFIRMED" if confirmed else "NULL")
    )
    result = {
        "status": "completed",
        "scope": "calibrated device-noise stress test, NOT hardware evidence",
        "pre_registration": {
            "file": "DERISK_FAKEBACKEND_TIER1_v1.md",
            "sha256": "AA029CA5D491E9140CD0874611A4B621847E3C4E7598EF5D7F2BDE4E17C875CE",
        },
        "backend": "FakeKolkataV2",
        "instances": list(INSTANCE_IDS),
        "budgets": list(derisk.BUDGETS),
        "B_star": derisk.B_STAR,
        "replicates": derisk.REPLICATES,
        "method_menu": list(derisk.METHODS),
        "primary": primary,
        "secondary": secondaries,
        "decision": decision,
        "null_framing": "no significant benefit under this backend/menu/budget regime",
        "saturation": saturation,
        "ordering_gates": ordering_gates,
        "determinism_check": determinism,
        "metadata": metadata,
        "duration_seconds": float(duration_seconds),
    }

    table.to_csv(OUTPUT_DIR / "per_instance_budget_table.csv", index=False)
    pd.DataFrame(_mapping_rows(mappings)).to_csv(
        OUTPUT_DIR / "mapping_manifest.csv",
        index=False,
    )
    (OUTPUT_DIR / "tier1_result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    bstar = table[table["budget"] == derisk.B_STAR].copy()
    lines = [
        "# FakeBackend tier-chico result",
        "",
        "**Scope:** calibrated device-noise stress test, NOT hardware evidence.",
        "",
        "## Pre-registration",
        "",
        "- source: `DERISK_FAKEBACKEND_TIER1_v1.md`",
        "- sealed hash: `AA029CA5D491E9140CD0874611A4B621847E3C4E7598EF5D7F2BDE4E17C875CE`",
        "- pool: C001-C048 complete; no Kolkata in-band filtering",
        "",
        "## Ordering gate",
    ]
    for gate in ordering_gates:
        lines.append(
            f"- {gate['instance_id']}: PASS, abs_error={gate['abs_error']:.3e}, "
            f"tol={gate['tolerance']:.1e}"
        )
    lines += [
        "",
        "## Determinism",
        (
            f"- {determinism['cell']} B={determinism['budget']}: "
            f"raw={determinism['raw_equal']}, primitive={determinism['primitive_equal']}, "
            f"rem={determinism['rem_equal']}"
        ),
        "",
        "## Primary endpoint",
        "",
        (
            f"Pooled over 48 C-ids at B*=512: failure_DA={primary['failure_rate_DA']:.6g}, "
            f"failure_MSE={primary['failure_rate_MSE']:.6g}, "
            f"rel_reduction={primary['observed_rel_reduction']:.6g}, "
            f"CI={primary['relative_reduction_bootstrap_ci']}, "
            f"b={primary['b_DA_better']}, c={primary['c_DA_worse']}, "
            f"paired_n={primary['paired_n']}, z={primary['mcnemar_z']:.6g}, "
            f"p={primary['mcnemar_one_sided_p']:.6g}, "
            f"reject={primary['mcnemar_one_sided_reject']}."
        ),
        f"- practical_threshold_0.15_pass: {primary['practical_pass']}",
        "",
        "## Decision",
        "",
        f"- decision: {decision}",
        f"- framing: {'inconclusive, regime too hard' if decision == 'INCONCLUSIVE_SATURATED' else (result['null_framing'] if decision == 'NULL' else 'primary pooled benefit significant at alpha=0.05')}",
        "",
        "## Secondary endpoints",
        "",
        f"- multiplicity: {secondaries['multiplicity']}",
        "",
        "| endpoint | instances | rows | paired_n | failure_MSE | failure_DA | rel_reduction | p | Holm p | Holm reject |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    secondary_lines = []
    for key, row in secondaries["inferential"].items():
        holm = row["holm_adjusted_p"]
        holm_text = "NA" if holm is None else f"{holm:.6g}"
        secondary_lines.append(
            f"| {key} | {row['instances']} | {row['rows']} | {row['paired_n']} | "
            f"{row['failure_rate_MSE']:.6g} | {row['failure_rate_DA']:.6g} | "
            f"{row['observed_rel_reduction']:.6g} | {row['mcnemar_one_sided_p']:.6g} | "
            f"{holm_text} | {row['holm_reject']} |"
        )
    lines.extend(secondary_lines)
    lines += [
        "",
        "## D1 and Raw+REM frequency",
        "",
        (
            f"- D1 full-Sigma vs diagonal flips: "
            f"{secondaries['diagnostics']['D1_full_vs_diagonal']['selector_changed_rows']}/"
            f"{secondaries['diagnostics']['D1_full_vs_diagonal']['total_rows']} "
            f"({secondaries['diagnostics']['D1_full_vs_diagonal']['frequency']:.6g})."
        ),
        (
            f"- DA selects Raw+REM: "
            f"{secondaries['diagnostics']['DA_selects_Raw_REM']['rows']}/"
            f"{secondaries['diagnostics']['DA_selects_Raw_REM']['total_rows']} "
            f"({secondaries['diagnostics']['DA_selects_Raw_REM']['frequency']:.6g})."
        ),
        "",
        "## Panel at B*",
        "",
        _markdown_table(
            bstar[
                [
                    "cell",
                    "epsilon_opt_tercile",
                    "uniform_in_band_B_star",
                    "DA_selected_method",
                    "MSE_selected_method",
                    "failure_rate_DA",
                    "failure_rate_MSE",
                    "failure_rate_Raw",
                    "observed_rel_reduction",
                    "b_DA_better",
                    "c_DA_worse",
                ]
            ]
        ),
        "",
        "## Saturation check",
        "",
        (
            f"- Raw failure mean at B*: {saturation['raw_failure_mean_at_B_star']:.6g}; "
            f"rows >=0.95: {saturation['raw_failure_rows_ge_0_95_at_B_star']}/"
            f"{saturation['total_rows_at_B_star']}."
        ),
        "",
        "## Outputs",
        "",
        "- `results/derisk_fakebackend_tier1/tier1_result.json`",
        "- `results/derisk_fakebackend_tier1/per_instance_budget_table.csv`",
        "- `results/derisk_fakebackend_tier1/mapping_manifest.csv`",
        "",
        f"Duration seconds: {duration_seconds:.1f}",
    ]
    report = "\n".join(lines) + "\n"
    (OUTPUT_DIR / "tier1_result.md").write_text(report, encoding="utf-8")
    return result


def run() -> dict[str, object]:
    start = time.perf_counter()
    backend = FakeKolkataV2()
    full_noise_model = NoiseModel.from_backend(backend)
    ordering_gates: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []
    mappings: dict[str, object] = {}
    metadata: dict[str, object] = {}
    determinism = _load_determinism()

    for idx, instance_id in enumerate(INSTANCE_IDS, start=1):
        checkpoint = _load_checkpoint(instance_id)
        if checkpoint is not None:
            cell_rows, mapping, gate, cell_meta = checkpoint
            print(f"{instance_id}: checkpoint loaded ({idx}/{len(INSTANCE_IDS)})", flush=True)
            ordering_gates.append(gate)
            rows.extend(cell_rows)
            mappings[instance_id] = mapping
            metadata[instance_id] = cell_meta
            continue

        print(f"{instance_id}: ordering gate ({idx}/{len(INSTANCE_IDS)})", flush=True)
        graph = maxcut_graph_for_instance(instance_id, num_qubits=10, degree=3)
        gate = derisk._ordering_gate(
            instance_id,
            tuple((int(u), int(v)) for u, v in sorted(graph.edges())),
        )
        ordering_gates.append(gate)
        print(f"{instance_id}: probabilities", flush=True)
        data = derisk._probability_array_for_cell(instance_id, backend, full_noise_model)
        mappings[instance_id] = data.mappings
        print(f"{instance_id}: samples/selectors", flush=True)
        cell_rows, cell_meta = derisk._analyze_cell(data, derisk.BUDGETS)
        rows.extend(cell_rows)
        metadata[instance_id] = cell_meta
        if determinism is None:
            determinism = derisk._determinism_check(data)
            _write_determinism(determinism)
        _write_checkpoint(
            instance_id=instance_id,
            rows=cell_rows,
            mapping=data.mappings,
            ordering=gate,
            metadata=cell_meta,
        )

    if determinism is None:
        raise RuntimeError("determinism check was not produced")
    table = pd.DataFrame(rows)
    return _write_outputs(
        table=table,
        mappings=mappings,
        ordering_gates=ordering_gates,
        determinism=determinism,
        metadata=metadata,
        duration_seconds=time.perf_counter() - start,
    )


def main() -> None:
    raise RuntimeError("Historical pooled in-sample inference is disabled in v20. Use run_fakekolkata_v20.py and its instance-cluster summary.")
    parser = argparse.ArgumentParser()
    parser.parse_args()
    result = run()
    print("FAKEBACKEND TIER1 COMPLETE")
    print(f"primary={result['primary']}")
    print(f"decision={result['decision']}")
    print(f"secondary={result['secondary']}")
    print(f"outputs={OUTPUT_DIR}")


if __name__ == "__main__":
    main()
