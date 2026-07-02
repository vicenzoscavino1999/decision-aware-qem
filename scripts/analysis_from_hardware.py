from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from daqem.gap_kernel import contrast_matrix
from experiments.hardware_sigma import run_main as hsmc


ARCHIVE_ROOT = REPO_ROOT / "reproducibility" / "hardware"
REFERENCE_RESULT = REPO_ROOT / "results" / "hardware_sigma_attempt2" / "hsmc_result.json"
DEFAULT_OUTPUT = REPO_ROOT / "results" / "hardware_sigma_attempt2" / "level3_from_archived_counts.json"

ATTEMPT2_CHARACTERIZATION_JOB = "d92plml958jc73bs50f0"
ATTEMPT2_EPOCH_JOBS = [
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


def load_raw_counts(job_id: str) -> list[dict[str, int]]:
    path = ARCHIVE_ROOT / "raw_counts" / f"{job_id}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_counts = payload.get("raw_counts")
    if not isinstance(raw_counts, list):
        raise RuntimeError(f"{path} does not contain captured raw_counts")
    return [{str(k): int(v) for k, v in counts.items()} for counts in raw_counts]


def result_label(endpoint: dict[str, Any], secondary: dict[str, Any]) -> str:
    if endpoint["primary_pass"] and secondary["secondary_pass"]:
        return "Frobenius-conservative_pass"
    if endpoint["primary_pass"]:
        return "directionally-sensitive_pass"
    return "failed_or_inconclusive"


def arrays_close(lhs: Any, rhs: Any, *, atol: float) -> bool:
    return bool(np.allclose(np.asarray(lhs, dtype=float), np.asarray(rhs, dtype=float), atol=atol, rtol=0.0))


def compare_against_reference(recomputed: dict[str, Any], reference: dict[str, Any], *, atol: float) -> list[str]:
    failures: list[str] = []
    if recomputed["result_label"] != reference.get("result_label"):
        failures.append(f"label {recomputed['result_label']} != {reference.get('result_label')}")

    for method in hsmc.METHODS:
        if not arrays_close(recomputed["sigma_hat"][method], reference["sigma_hat"][method], atol=atol):
            failures.append(f"sigma_hat mismatch: {method}")
        if not arrays_close(recomputed["sigma_pred"][method], reference["sigma_pred"][method], atol=atol):
            failures.append(f"sigma_pred mismatch: {method}")

    ref_pairs = reference["primary_projected_ranking"]["pairs"]
    got_pairs = recomputed["primary_projected_ranking"]["pairs"]
    if len(ref_pairs) != len(got_pairs):
        failures.append(f"primary pair count {len(got_pairs)} != {len(ref_pairs)}")
    else:
        for got, ref in zip(got_pairs, ref_pairs, strict=True):
            if got["pair"] != ref["pair"]:
                failures.append(f"primary pair mismatch {got['pair']} != {ref['pair']}")
                continue
            for key in ("delta_pred", "delta_rank", "ucb95", "threshold"):
                if abs(float(got[key]) - float(ref[key])) > atol:
                    failures.append(f"{got['pair']} {key}: {got[key]} != {ref[key]}")
            if bool(got["passed"]) != bool(ref["passed"]):
                failures.append(f"{got['pair']} passed: {got['passed']} != {ref['passed']}")

    for method in hsmc.METHODS:
        got = recomputed["secondary_frobenius"]["methods"][method]
        ref = reference["secondary_frobenius"]["methods"][method]
        if abs(float(got["relative_frobenius_error"]) - float(ref["relative_frobenius_error"])) > atol:
            failures.append(f"frobenius mismatch: {method}")
        if bool(got["passed"]) != bool(ref["passed"]):
            failures.append(f"frobenius pass mismatch: {method}")
    return failures


def recompute_from_archive() -> dict[str, Any]:
    hsmc.set_active_physical_qubits(hsmc.AMENDMENT_V1_1_PHYSICAL_QUBITS)

    landscape = hsmc.microcell_landscape()
    contrast = contrast_matrix(4, ref=0)
    mu = contrast @ landscape.ideal_values
    effective_scales = hsmc.effective_scale_tuple()

    char_tasks = hsmc.build_characterization_tasks()
    char_counts = load_raw_counts(ATTEMPT2_CHARACTERIZATION_JOB)
    design = hsmc.characterization_design(char_tasks)
    observations = hsmc.characterization_observations_from_counts(char_tasks, char_counts)
    learned_model = hsmc.learn_sparse_pl_model(design, observations)
    gate_c1 = hsmc.gate_c1_metrics(design, observations, learned_model)
    if not gate_c1["passed"]:
        raise RuntimeError(f"archived attempt-2 characterization does not pass Gate C1: {gate_c1}")

    primitive_variance_unit = hsmc.primitive_variance_unit_from_rates(learned_model["rates"])
    da_coeffs = hsmc.decision_zne_coefficients_from_prediction(
        primitive_variance_unit,
        landscape.ideal_values,
        effective_scales,
    )
    maps = hsmc.method_maps(effective_scales, da_coeffs=da_coeffs)
    sigma_pred_by_method = {
        method: hsmc.sigma_pred_from_primitive_variances(primitive_variance_unit, method, maps[method], contrast)
        for method in hsmc.METHODS
    }

    epoch_vectors: list[dict[str, list[np.ndarray]]] = []
    for epoch, job_id in enumerate(ATTEMPT2_EPOCH_JOBS):
        tasks = hsmc.build_epoch_tasks(epoch, hsmc.AMENDMENT_V1_1_REPS_PER_EPOCH)
        counts = load_raw_counts(job_id)
        epoch_vectors.append(hsmc.gap_vectors_for_epoch(tasks, counts, maps, contrast))

    merged = {method: [] for method in hsmc.METHODS}
    for epoch_data in epoch_vectors:
        for method in hsmc.METHODS:
            merged[method].extend(epoch_data[method])
    sigma_hat_by_method = {method: hsmc.covariance_from_gap_vectors(merged[method]) for method in hsmc.METHODS}
    bootstrap = hsmc.bootstrap_sigma_by_epoch(epoch_vectors, repetitions=hsmc.BOOTSTRAP_REPETITIONS)
    endpoint = hsmc.endpoint_projected_ranking(
        mu=mu,
        sigma_pred_by_method=sigma_pred_by_method,
        sigma_hat_by_method=sigma_hat_by_method,
        bootstrap_sigmas=bootstrap,
    )
    secondary = hsmc.frobenius_secondary(sigma_pred_by_method, sigma_hat_by_method)

    return {
        "status": "complete",
        "source": "reproducibility/hardware/raw_counts",
        "backend_frozen": hsmc.BACKEND_NAME,
        "physical_qubits": list(hsmc.AMENDMENT_V1_1_PHYSICAL_QUBITS),
        "instance_id": hsmc.INSTANCE_ID,
        "completed_epochs": list(range(len(ATTEMPT2_EPOCH_JOBS))),
        "config": {
            "B_nominal": hsmc.B_NOMINAL,
            "R_final": hsmc.AMENDMENT_V1_1_R_FINAL,
            "epochs": hsmc.EPOCHS,
            "reps_per_epoch": hsmc.AMENDMENT_V1_1_REPS_PER_EPOCH,
            "methods": list(hsmc.METHODS),
            "effective_scales": list(effective_scales),
            "accuracy_zne_coefficients": hsmc.zne_coefficients_from_effective_scales(effective_scales).tolist(),
            "decision_zne_coefficients": da_coeffs.tolist(),
            "bootstrap_repetitions": hsmc.BOOTSTRAP_REPETITIONS,
        },
        "characterization": {
            "source": "archived_physical_characterization_counts",
            "circuit_count": len(char_tasks),
            "shots_per_circuit": hsmc.CHARACTERIZATION_SHOTS,
            "learned_rates": learned_model["rates"].tolist(),
            "learned_intercepts": learned_model["intercepts"].tolist(),
            "observations_minmax": [float(np.min(observations)), float(np.max(observations))],
        },
        "gate_c1": gate_c1,
        "sigma_pred": {method: sigma_pred_by_method[method].tolist() for method in hsmc.METHODS},
        "sigma_hat": {method: sigma_hat_by_method[method].tolist() for method in hsmc.METHODS},
        "primary_projected_ranking": endpoint,
        "secondary_frobenius": secondary,
        "result_label": result_label(endpoint, secondary),
        "forbidden_outputs_computed": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--reference", type=Path, default=REFERENCE_RESULT)
    parser.add_argument("--atol", type=float, default=1e-9)
    args = parser.parse_args()

    recomputed = recompute_from_archive()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(recomputed, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    failures = compare_against_reference(recomputed, reference, atol=float(args.atol))
    if failures:
        print("HARDWARE ANALYSIS FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "HARDWARE ANALYSIS PASS: "
        f"label={recomputed['result_label']} "
        f"epochs={len(recomputed['completed_epochs'])} "
        f"output={args.output.as_posix()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
