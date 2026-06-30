from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import time
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
import yaml
from qiskit import transpile
from qiskit_aer import AerSimulator
from sklearn.covariance import LedoitWolf

from daqem.candidates import (
    CONFIRMATORY_INSTANCE_IDS,
    landscape_for_instance,
    maxcut_graph_for_instance,
    maxcut_values_for_graph,
)
from daqem.gap_kernel import nearest_psd
from daqem.noise import ONE_QUBIT_DEPOLARIZING, TWO_QUBIT_DEPOLARIZING, depolarizing_noise_model
from daqem.qaoa import qaoa_maxcut_circuit
from daqem.qem_methods import accuracy_zne_coeffs, decision_optimal_zne_coeffs, richardson_constraints
from daqem.risk import gri_risk

from experiments.gate0_pilot_full_vs_diagonal import load_config as load_gate0_config
from experiments.gate0_pilot_full_vs_diagonal import confirmatory_raw_relpath
from experiments.gate0_pilot_full_vs_diagonal import raw_relpath


CONFIG_PATH = REPO_ROOT / "reproducibility" / "config" / "a3_pullback_frontier.yaml"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "results"
CSV_REL = Path("pilot") / "pullback_frontier.csv"
FROZEN_REL_DIR = Path("pilot") / "a3_frozen_prediction"
MEAN_CROSSCHECK_REL = Path("pilot") / "a3_mean_crosscheck.md"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest().upper()}"


def _frozen_rel_dir(config: dict) -> Path:
    return Path(str(config.get("output_namespace", "pilot"))) / "a3_frozen_prediction"


def _raw_relpath_for_config(instance_id: str, config: dict) -> Path:
    if str(config.get("output_namespace", "pilot")) == "confirmatory":
        return confirmatory_raw_relpath(instance_id)
    return raw_relpath(instance_id)


def _write_deterministic_npz(path: Path, **arrays) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    with zipfile.ZipFile(tmp, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(arrays):
            buffer = io.BytesIO()
            np.lib.format.write_array(buffer, np.asarray(arrays[name]), allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy")
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, buffer.getvalue())
    tmp.replace(path)


def load_config(profile: str = "smoke") -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    profiles = raw.get("profiles", {})
    if profile not in profiles:
        raise ValueError(f"unknown A3 profile: {profile}")
    config = dict(raw.get("defaults", {}))
    config.update(profiles[profile])
    config["profile"] = profile
    gate0_config = load_gate0_config(str(config["gate0_profile"]))
    prediction_only = bool(config.get("prediction_only", False))
    for instance_id in config["instance_ids"]:
        is_confirmatory = instance_id in CONFIRMATORY_INSTANCE_IDS
        if instance_id in gate0_config["instance_ids"]:
            continue
        if prediction_only and is_confirmatory:
            if str(config.get("output_namespace", "")) != "confirmatory":
                raise ValueError("confirmatory A3 profiles must write to output_namespace: confirmatory")
            continue
        if is_confirmatory:
            raise ValueError(
                "confirmatory A3 profiles must set prediction_only: true "
                "and output_namespace: confirmatory"
            )
        if instance_id not in gate0_config["instance_ids"]:
            raise ValueError(
                f"A3 instance {instance_id} is not present in Gate 0 profile "
                f"{config['gate0_profile']}"
            )
    config["gate0_config"] = gate0_config
    return config


def _state_index(key) -> int:
    if isinstance(key, (int, np.integer)):
        return int(key)
    clean = str(key).replace(" ", "")
    if clean.startswith("0x"):
        return int(clean, 16)
    return int(clean, 2)


def _primitive_objective_moments(
    *,
    instance_id: str,
    gate0_config: dict,
    noise_model_factory=None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    landscape = landscape_for_instance(
        instance_id,
        candidate_count=int(gate0_config["candidate_count"]),
        depth=int(gate0_config["depth"]),
        num_qubits=int(gate0_config["qubits"]),
        graph_degree=int(gate0_config["graph_degree"]),
        local_radius=float(gate0_config["local_radius"]),
        search_radius=float(gate0_config["search_radius"]),
        search_count=int(gate0_config["search_count"]),
    )
    graph = maxcut_graph_for_instance(
        instance_id,
        num_qubits=int(gate0_config["qubits"]),
        degree=int(gate0_config["graph_degree"]),
    )
    values_by_state = -maxcut_values_for_graph(graph)
    scales = np.asarray(gate0_config["zne_lambdas"], dtype=float)
    means = np.empty((len(scales), landscape.angles.shape[0]), dtype=float)
    variances = np.empty_like(means)

    for scale_idx, scale in enumerate(scales):
        p1 = min(float(ONE_QUBIT_DEPOLARIZING) * float(scale), 0.95)
        p2 = min(float(TWO_QUBIT_DEPOLARIZING) * float(scale), 0.95)
        noise_model = (
            depolarizing_noise_model(p1=p1, p2=p2)
            if noise_model_factory is None
            else noise_model_factory(scale_idx, float(scale))
        )
        simulator = AerSimulator(
            method="density_matrix",
            noise_model=noise_model,
        )
        circuits = []
        for angles in landscape.angles:
            circuit = qaoa_maxcut_circuit(
                graph,
                depth=int(gate0_config["depth"]),
                gammas=angles[: int(gate0_config["depth"])],
                betas=angles[int(gate0_config["depth"]) :],
                measure=False,
            )
            circuit.save_probabilities_dict()
            circuits.append(circuit)
        transpiled = transpile(circuits, simulator, seed_transpiler=260616 + scale_idx)
        result = simulator.run(transpiled).result()
        for candidate_idx in range(landscape.angles.shape[0]):
            probabilities = result.data(candidate_idx)["probabilities"]
            mean = 0.0
            second = 0.0
            for key, probability in probabilities.items():
                value = float(values_by_state[_state_index(key)])
                prob = float(probability)
                mean += prob * value
                second += prob * value * value
            means[scale_idx, candidate_idx] = mean
            variances[scale_idx, candidate_idx] = max(second - mean * mean, 0.0)
    return means, variances, landscape.ideal_values, np.asarray(landscape.x_star)


def _gap_map(coefficients: np.ndarray, candidate_count: int, x_star: int) -> np.ndarray:
    coeffs = np.asarray(coefficients, dtype=float)
    competitors = [idx for idx in range(candidate_count) if idx != int(x_star)]
    primitive_count = coeffs.size * candidate_count
    matrix = np.zeros((len(competitors), primitive_count), dtype=float)
    for row, candidate_idx in enumerate(competitors):
        for scale_idx, coeff in enumerate(coeffs):
            matrix[row, scale_idx * candidate_count + candidate_idx] += coeff
            matrix[row, scale_idx * candidate_count + int(x_star)] -= coeff
    return matrix


def method_coefficients_from_true_cdev(
    *,
    primitive_variance_unit: np.ndarray,
    ideal_values: np.ndarray,
    x_star: int,
    gate0_config: dict,
) -> dict[str, np.ndarray]:
    scales = np.asarray(gate0_config["zne_lambdas"], dtype=float)
    order = int(gate0_config["zne_order"])
    raw = np.zeros(scales.size, dtype=float)
    raw[0] = 1.0
    accuracy = accuracy_zne_coeffs(scales, p=order)
    competitors = [idx for idx in range(len(ideal_values)) if idx != int(x_star)]
    true_mu = np.asarray(ideal_values, dtype=float)[competitors] - float(ideal_values[int(x_star)])
    mu_lower = np.maximum(true_mu, float(gate0_config["decision_zne_mu_floor"]))
    q_list = []
    for candidate_idx in competitors:
        q = np.diag(
            primitive_variance_unit[:, candidate_idx]
            + primitive_variance_unit[:, int(x_star)]
        )
        q_list.append(q)
    A, rho = richardson_constraints(scales, p=order)
    decision = decision_optimal_zne_coeffs(q_list, mu_lower, A, rho)
    return {
        "Raw": raw,
        "Accuracy-ZNE": accuracy,
        "Decision-ZNE": decision,
    }


def _method_gap_maps(
    method_coeffs: dict[str, np.ndarray],
    *,
    method_names: list[str],
    candidate_count: int,
    x_star: int,
) -> np.ndarray:
    return np.stack(
        [
            _gap_map(method_coeffs[name], candidate_count=candidate_count, x_star=x_star)
            for name in method_names
        ],
        axis=0,
    )


def _active_gap_mask(mu: np.ndarray, sigma: np.ndarray, config: dict) -> np.ndarray:
    diag = np.diag(np.asarray(sigma, dtype=float))
    scores = np.full(mu.shape, np.inf, dtype=float)
    positive = diag > 0.0
    scores[positive] = np.asarray(mu, dtype=float)[positive] / np.sqrt(diag[positive])
    order = np.argsort(scores, kind="mergesort")
    min_count = min(int(config["min_active_gaps"]), len(mu))
    max_count = min(int(config["max_active_gaps"]), len(mu))
    threshold = scores[order[0]] + float(config["active_z_slack"])
    selected = [idx for idx in order if scores[idx] <= threshold]
    selected = selected[:max_count]
    if len(selected) < min_count:
        selected = list(order[:min_count])
    mask = np.zeros(len(mu), dtype=bool)
    mask[np.asarray(selected, dtype=int)] = True
    return mask


def risk_gradient_central(
    mu: np.ndarray,
    sigma: np.ndarray,
    active_mask: np.ndarray,
    *,
    perturbation_relative: float,
    perturbation_floor: float,
    stability_relative: float,
    stability_absolute: float,
) -> tuple[np.ndarray, bool, float]:
    sigma = nearest_psd(sigma)
    active = np.flatnonzero(np.asarray(active_mask, dtype=bool))
    if active.size == 0:
        raise ValueError("active_mask must select at least one coordinate")
    positive_diag = np.diag(sigma)[np.diag(sigma) > 0.0]
    median_diag = float(np.median(positive_diag)) if positive_diag.size else 0.0
    step = max(float(perturbation_relative) * median_diag, float(perturbation_floor))

    def one_scale(scale: float) -> np.ndarray:
        grad = np.zeros_like(sigma, dtype=float)
        eps = step * float(scale)
        for pos, i in enumerate(active):
            for j in active[pos:]:
                basis = np.zeros_like(sigma, dtype=float)
                basis[i, j] = 1.0
                basis[j, i] = 1.0
                plus = nearest_psd(sigma + eps * basis)
                minus = nearest_psd(sigma - eps * basis)
                derivative = (gri_risk(mu, plus, B=1.0) - gri_risk(mu, minus, B=1.0)) / (
                    2.0 * eps
                )
                if i == j:
                    grad[i, i] = derivative
                else:
                    grad[i, j] = derivative / 2.0
                    grad[j, i] = derivative / 2.0
        return grad

    grad = one_scale(1.0)
    grad_wide = one_scale(2.0)
    diff = float(np.linalg.norm(grad - grad_wide, ord="fro"))
    scale = max(float(np.linalg.norm(grad_wide, ord="fro")), 1.0)
    unstable = (not np.isfinite(diff)) or diff > float(stability_absolute) + float(
        stability_relative
    ) * scale
    return grad, bool(unstable), step


def _order_label(method_a: str, risk_a: float, method_b: str, risk_b: float) -> str:
    if risk_a <= risk_b:
        return f"{method_a}<{method_b}"
    return f"{method_b}<{method_a}"


def _status_and_label(
    *,
    ambiguous: bool,
    projected_ratio: float,
    frob_ratio: float,
    ordering_match: bool,
) -> tuple[str, str]:
    if ambiguous:
        return "ambiguous", "ambiguous"
    if projected_ratio < 1.0 and ordering_match:
        if frob_ratio < 1.0:
            return "pass", "frobenius_proxy_only"
        return "pass", "directionally_sensitive_pass"
    return "fail", "fail"


def build_frozen_prediction_for_cell(
    *,
    instance_id: str,
    output_root: Path,
    config: dict,
) -> Path:
    gate0_config = dict(config["gate0_config"])
    means_unit, variance_unit, ideal_values, x_star_arr = _primitive_objective_moments(
        instance_id=instance_id,
        gate0_config=gate0_config,
    )
    x_star = int(x_star_arr)
    candidate_count = len(ideal_values)
    competitors = [idx for idx in range(candidate_count) if idx != x_star]
    mu = np.asarray(ideal_values, dtype=float)[competitors] - float(ideal_values[x_star])
    method_names = list(gate0_config["method_menu_core"])
    coeffs = method_coefficients_from_true_cdev(
        primitive_variance_unit=variance_unit,
        ideal_values=np.asarray(ideal_values, dtype=float),
        x_star=x_star,
        gate0_config=gate0_config,
    )
    maps = _method_gap_maps(
        coeffs,
        method_names=method_names,
        candidate_count=candidate_count,
        x_star=x_star,
    )
    cdev_diag_unit = variance_unit.reshape(-1)
    budgets = np.asarray(gate0_config["budget_grid"], dtype=np.int64)
    sigma_pred = np.empty((len(method_names), len(budgets), len(mu), len(mu)), dtype=float)
    risks = np.empty((len(method_names), len(budgets)), dtype=float)
    gradients = np.empty_like(sigma_pred)
    active_masks = np.zeros((len(method_names), len(budgets), len(mu)), dtype=bool)
    gradient_unstable = np.zeros((len(method_names), len(budgets)), dtype=bool)
    gradient_steps = np.empty((len(method_names), len(budgets)), dtype=float)
    for method_idx, gap_map in enumerate(maps):
        sigma_unit = (gap_map * cdev_diag_unit) @ gap_map.T
        for budget_idx, budget in enumerate(budgets):
            sigma = nearest_psd(sigma_unit / float(budget))
            sigma_pred[method_idx, budget_idx] = sigma
            risks[method_idx, budget_idx] = gri_risk(mu, sigma, B=1.0)
            active_mask = _active_gap_mask(mu, sigma, config)
            active_masks[method_idx, budget_idx] = active_mask
            grad, unstable, step = risk_gradient_central(
                mu,
                sigma,
                active_mask,
                perturbation_relative=float(config["perturbation_relative"]),
                perturbation_floor=float(config["perturbation_floor"]),
                stability_relative=float(config["gradient_stability_relative"]),
                stability_absolute=float(config["gradient_stability_absolute"]),
            )
            gradients[method_idx, budget_idx] = grad
            gradient_unstable[method_idx, budget_idx] = unstable
            gradient_steps[method_idx, budget_idx] = step

    pair_names = ["_vs_".join(pair) for pair in config["method_pairs"]]
    delta_pred = np.empty((len(pair_names), len(budgets)), dtype=float)
    tau = np.empty_like(delta_pred)
    predicted_order = np.empty((len(pair_names), len(budgets)), dtype=f"<U64")
    for pair_idx, (left, right) in enumerate(config["method_pairs"]):
        left_idx = method_names.index(left)
        right_idx = method_names.index(right)
        for budget_idx in range(len(budgets)):
            delta = risks[left_idx, budget_idx] - risks[right_idx, budget_idx]
            delta_pred[pair_idx, budget_idx] = delta
            tau[pair_idx, budget_idx] = float(config["rho_flip"]) * abs(delta)
            predicted_order[pair_idx, budget_idx] = _order_label(
                left,
                risks[left_idx, budget_idx],
                right,
                risks[right_idx, budget_idx],
            )

    metadata = {
        "instance_id": instance_id,
        "profile": config["profile"],
        "gate0_profile": config["gate0_profile"],
        "freeze_before_Sigma_hat": True,
        "cdev_true": "independent primitive shot-noise diagonal from exact depolarizing channel",
        "cdev_scaling": "primitive variances are per-unit and divided by budget",
        "gradient": "central finite differences on active symmetric Sigma basis",
        "rho_flip": float(config["rho_flip"]),
        "mde_absolute": float(config["mde_absolute"]),
    }
    out = output_root / _frozen_rel_dir(config) / f"{instance_id}.npz"
    _write_deterministic_npz(
        out,
        metadata_json=np.array(json.dumps(metadata, sort_keys=True)),
        budgets=budgets,
        method_names=np.asarray(method_names),
        pair_names=np.asarray(pair_names),
        method_coefficients=np.stack([coeffs[name] for name in method_names], axis=0),
        primitive_mean_unit=means_unit,
        primitive_variance_unit=variance_unit,
        cdev_true_diag_unit=cdev_diag_unit,
        gap_maps=maps,
        ideal_values=np.asarray(ideal_values, dtype=float),
        x_star=np.asarray(x_star, dtype=np.int64),
        mu=mu,
        sigma_pred=sigma_pred,
        risks_pred=risks,
        gradients=gradients,
        active_masks=active_masks,
        gradient_unstable=gradient_unstable,
        gradient_steps=gradient_steps,
        delta_pred=delta_pred,
        tau_flip_projected=tau,
        predicted_order=predicted_order,
    )
    return out


def _metadata_dict(raw) -> dict:
    return json.loads(str(raw["metadata_json"].item()))


def _validate_raw(raw, instance_id: str, gate0_config: dict, *, strict: bool = True) -> None:
    metadata = _metadata_dict(raw)
    if metadata.get("instance_id") != instance_id:
        raise ValueError(f"raw instance mismatch: {metadata.get('instance_id')} != {instance_id}")
    if not strict:
        expected_candidate_count = int(gate0_config["candidate_count"])
        if int(metadata.get("candidate_count", -1)) != expected_candidate_count:
            raise ValueError("raw candidate_count mismatch")
        return
    if metadata.get("profile") != gate0_config["profile"]:
        raise ValueError(
            f"raw profile mismatch: {metadata.get('profile')} != {gate0_config['profile']}"
        )
    if int(metadata.get("candidate_count", -1)) != int(gate0_config["candidate_count"]):
        raise ValueError("raw candidate_count mismatch")
    if [int(v) for v in metadata.get("budget_grid", [])] != [
        int(v) for v in gate0_config["budget_grid"]
    ]:
        raise ValueError("raw budget_grid mismatch")


def _covariance(samples: np.ndarray, *, shrinkage: bool) -> np.ndarray:
    arr = np.asarray(samples, dtype=float)
    if arr.ndim != 2:
        raise ValueError("samples must be two-dimensional")
    if arr.shape[0] < 2:
        raise ValueError("at least two samples are required")
    if arr.shape[1] == 1:
        return np.array([[float(np.var(arr[:, 0], ddof=1))]])
    if shrinkage and arr.shape[0] > arr.shape[1]:
        return nearest_psd(LedoitWolf().fit(arr).covariance_)
    return nearest_psd(np.cov(arr, rowvar=False, ddof=1))


def _method_samples_from_raw(
    raw,
    *,
    budget_idx: int,
    method_names: list[str],
    method_coefficients: np.ndarray,
) -> dict[str, np.ndarray]:
    estimates = np.asarray(raw["primitive_objective_estimates"], dtype=float)
    ideal_values = np.asarray(raw["ideal_values"], dtype=float)
    x_star = int(raw["x_star"])
    competitors = [idx for idx in range(len(ideal_values)) if idx != x_star]
    primitive_gaps = (
        estimates[:, :, competitors, budget_idx] - estimates[:, :, [x_star], budget_idx]
    )
    return {
        method: np.einsum("s,rsd->rd", method_coefficients[idx], primitive_gaps)
        for idx, method in enumerate(method_names)
    }


def mean_crosscheck_from_frozen_raw(
    *,
    instance_id: str,
    frozen,
    raw,
) -> dict[str, object]:
    primitive_means = np.asarray(frozen["primitive_mean_unit"], dtype=float)
    variances = np.asarray(frozen["cdev_true_diag_unit"], dtype=float).reshape(
        primitive_means.shape
    )
    estimates = np.asarray(raw["primitive_objective_estimates"], dtype=float)
    budgets = np.asarray(raw["budgets"], dtype=np.int64)
    b_max_idx = int(np.argmax(budgets))
    b_max = int(budgets[b_max_idx])
    empirical = np.mean(estimates[:, :, :, b_max_idx], axis=0)
    replicates = int(estimates.shape[0])
    stderr = np.sqrt(np.maximum(variances, 0.0) / float(b_max * replicates))
    diff = np.abs(empirical - primitive_means)
    z = np.divide(diff, stderr, out=np.zeros_like(diff), where=stderr > 0.0)
    max_diff_index = np.unravel_index(int(np.argmax(diff)), diff.shape)
    max_z_index = np.unravel_index(int(np.argmax(z)), z.shape)
    return {
        "problem_cell": instance_id,
        "B_max": b_max,
        "replicates": replicates,
        "max_abs_empirical_minus_analytic": float(diff[max_diff_index]),
        "max_abs_diff_scale_index": int(max_diff_index[0]),
        "max_abs_diff_candidate_index": int(max_diff_index[1]),
        "max_z_score": float(z[max_z_index]),
        "max_z_scale_index": int(max_z_index[0]),
        "max_z_candidate_index": int(max_z_index[1]),
        "means_ok": bool(float(z[max_z_index]) < 6.0),
    }


def write_mean_crosscheck_report(output_root: Path, rows: list[dict[str, object]]) -> None:
    out = output_root / MEAN_CROSSCHECK_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# A3 Mean Cross-Check",
        "",
        "Diagnostic only: not canonical, not part of verify/reference.",
        "",
        "| problem_cell | B_max | replicates | max_abs_empirical_minus_analytic | max_abs_diff_primitive | max_z_score | max_z_primitive | means_ok |",
        "|---|---:|---:|---:|---|---:|---|---|",
    ]
    for row in rows:
        diff_primitive = (
            f"s{row['max_abs_diff_scale_index']}:c{row['max_abs_diff_candidate_index']}"
        )
        z_primitive = f"s{row['max_z_scale_index']}:c{row['max_z_candidate_index']}"
        lines.append(
            "| {problem_cell} | {B_max} | {replicates} | "
            "{max_abs_empirical_minus_analytic:.9g} | "
            f"{diff_primitive} | "
            "{max_z_score:.6g} | "
            f"{z_primitive} | "
            "{means_ok} |".format(**row)
        )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyze_cell_from_frozen_prediction(
    *,
    instance_id: str,
    frozen_path: Path,
    frozen_hash: str,
    output_root: Path,
    config: dict,
) -> pd.DataFrame:
    frozen = np.load(frozen_path, allow_pickle=False)
    gate0_config = dict(config["gate0_config"])
    raw = np.load(output_root / _raw_relpath_for_config(instance_id, config), allow_pickle=False)
    allow_budget_subset = bool(config.get("allow_budget_subset", False))
    _validate_raw(raw, instance_id, gate0_config, strict=not allow_budget_subset)
    crosscheck = mean_crosscheck_from_frozen_raw(
        instance_id=instance_id,
        frozen=frozen,
        raw=raw,
    )
    budgets = [int(value) for value in frozen["budgets"]]
    raw_budgets = [int(value) for value in raw["budgets"]]
    if allow_budget_subset:
        raw_budget_to_idx = {budget: idx for idx, budget in enumerate(raw_budgets)}
        budget_pairs = [
            (frozen_idx, raw_budget_to_idx[budget], budget)
            for frozen_idx, budget in enumerate(budgets)
            if budget in raw_budget_to_idx
        ]
        if not budget_pairs:
            raise ValueError(
                f"raw budgets {raw_budgets} do not overlap frozen budgets {budgets}"
            )
    else:
        budget_pairs = [(idx, idx, budget) for idx, budget in enumerate(budgets)]
    method_names = [str(value) for value in frozen["method_names"]]
    method_coefficients = np.asarray(frozen["method_coefficients"], dtype=float)
    pair_names = [str(value) for value in frozen["pair_names"]]
    mu = np.asarray(frozen["mu"], dtype=float)
    sigma_pred = np.asarray(frozen["sigma_pred"], dtype=float)
    gradients = np.asarray(frozen["gradients"], dtype=float)
    risks_pred = np.asarray(frozen["risks_pred"], dtype=float)
    delta_pred = np.asarray(frozen["delta_pred"], dtype=float)
    tau = np.asarray(frozen["tau_flip_projected"], dtype=float)
    predicted_order = np.asarray(frozen["predicted_order"]).astype(str)
    gradient_unstable = np.asarray(frozen["gradient_unstable"], dtype=bool)

    rows = []
    for frozen_budget_idx, raw_budget_idx, budget in budget_pairs:
        samples_by_method = _method_samples_from_raw(
            raw,
            budget_idx=raw_budget_idx,
            method_names=method_names,
            method_coefficients=method_coefficients,
        )
        sigma_hat = []
        risks_empirical = []
        for method in method_names:
            sigma = _covariance(
                samples_by_method[method],
                shrinkage=bool(gate0_config["use_ledoit_wolf"]),
            )
            sigma_hat.append(sigma)
            risks_empirical.append(gri_risk(mu, sigma, B=1.0))
        sigma_hat_arr = np.stack(sigma_hat, axis=0)
        risks_empirical_arr = np.asarray(risks_empirical, dtype=float)
        best_method_idx = int(np.argmin(risks_pred[:, frozen_budget_idx]))
        for pair_idx, (left, right) in enumerate(config["method_pairs"]):
            left_idx = method_names.index(left)
            right_idx = method_names.index(right)
            e_left = sigma_hat_arr[left_idx] - sigma_pred[left_idx, frozen_budget_idx]
            e_right = sigma_hat_arr[right_idx] - sigma_pred[right_idx, frozen_budget_idx]
            projected = abs(
                float(np.sum(gradients[left_idx, frozen_budget_idx] * e_left))
                - float(np.sum(gradients[right_idx, frozen_budget_idx] * e_right))
            )
            tolerance = float(tau[pair_idx, frozen_budget_idx])
            tolerance_for_ratio = max(tolerance, float(config["epsilon0"]))
            ratio = projected / tolerance_for_ratio
            grad_norm = float(
                np.linalg.norm(gradients[left_idx, frozen_budget_idx], ord="fro")
                + np.linalg.norm(gradients[right_idx, frozen_budget_idx], ord="fro")
            )
            frob_tolerance = tolerance_for_ratio / (grad_norm + float(config["epsilon0"]))
            frob_error = float(np.linalg.norm(e_left, ord="fro") + np.linalg.norm(e_right, ord="fro"))
            frob_ratio = frob_error / max(frob_tolerance, float(config["epsilon0"]))
            empirical_order = _order_label(
                left,
                risks_empirical_arr[left_idx],
                right,
                risks_empirical_arr[right_idx],
            )
            ordering_match = empirical_order == predicted_order[pair_idx, frozen_budget_idx]
            ambiguous = (
                abs(float(delta_pred[pair_idx, frozen_budget_idx])) < float(config["mde_absolute"])
                or bool(gradient_unstable[left_idx, frozen_budget_idx])
                or bool(gradient_unstable[right_idx, frozen_budget_idx])
            )
            active_pair = (not ambiguous) and (
                left_idx == best_method_idx
                or right_idx == best_method_idx
                or abs(float(delta_pred[pair_idx, frozen_budget_idx])) * float(budget)
                >= float(gate0_config["bstar_gain_threshold"])
            )
            status, label = _status_and_label(
                ambiguous=ambiguous,
                projected_ratio=ratio,
                frob_ratio=frob_ratio,
                ordering_match=ordering_match,
            )
            rows.append(
                {
                    "problem_cell": instance_id,
                    "pair_id": pair_names[pair_idx],
                    "budget": budget,
                    "active_pair": bool(active_pair),
                    "delta_rank_projected": projected,
                    "tau_flip_projected": tolerance,
                    "projected_error_over_tolerance": ratio,
                    "frobenius_error_over_tolerance": frob_ratio,
                    "predicted_order": str(predicted_order[pair_idx, frozen_budget_idx]),
                    "empirical_order": empirical_order,
                    "ordering_match": bool(ordering_match),
                    "a3_status": status,
                    "pass_label": label,
                    "_frozen_hash": frozen_hash,
                }
            )
    df = pd.DataFrame(rows)
    df.attrs["mean_crosscheck"] = crosscheck
    return df


def sync_full_pullback_manifest(output_root: Path, *, duration_seconds: float) -> None:
    manifest_path = output_root / "manifest.json"
    checkpoint_path = output_root / ".partial" / "checkpoint.json"
    csv_path = output_root / CSV_REL
    if not manifest_path.exists() or not checkpoint_path.exists():
        return
    csv_hash = _sha256(csv_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    manifest.setdefault("outputs", {})[CSV_REL.as_posix()] = csv_hash
    if "level1/pullback_mini" in manifest.get("block_status", {}):
        manifest["block_status"]["level1/pullback_mini"] = "complete"
    incomplete = manifest.get("incomplete_blocks")
    if isinstance(incomplete, list):
        manifest["incomplete_blocks"] = [
            block for block in incomplete if block != "level1/pullback_mini"
        ]
    block = checkpoint.setdefault("blocks", {}).setdefault("level1/pullback_mini", {})
    block["status"] = "complete"
    block.setdefault("outputs", {})[CSV_REL.as_posix()] = csv_hash
    block["duration_seconds"] = float(duration_seconds)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    checkpoint_path.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")


def run(
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    *,
    profile: str = "smoke",
) -> pd.DataFrame:
    start = time.perf_counter()
    config = load_config(profile)
    frames = []
    frozen_hashes = {}
    crosscheck_rows = []
    frozen_paths = {}
    for instance_id in config["instance_ids"]:
        frozen_path = build_frozen_prediction_for_cell(
            instance_id=instance_id,
            output_root=output_root,
            config=config,
        )
        frozen_hash = _sha256(frozen_path)
        frozen_hashes[instance_id] = frozen_hash
        frozen_paths[instance_id] = str(frozen_path.relative_to(output_root))
        if bool(config.get("prediction_only", False)):
            continue
        # Firewall boundary: Sigma_hat/raw loading starts only after this hash exists.
        frame = analyze_cell_from_frozen_prediction(
            instance_id=instance_id,
            frozen_path=frozen_path,
            frozen_hash=frozen_hash,
            output_root=output_root,
            config=config,
        )
        frames.append(frame)
        crosscheck_rows.append(dict(frame.attrs["mean_crosscheck"]))
    elapsed = time.perf_counter() - start
    if bool(config.get("prediction_only", False)):
        print(
            json.dumps(
                {
                    "profile": profile,
                    "instances": config["instance_ids"],
                    "frozen_hashes": frozen_hashes,
                    "frozen_paths": frozen_paths,
                    "prediction_only": True,
                    "uses_aer_density_matrix": True,
                    "uses_shot_sampling": False,
                    "duration_seconds": elapsed,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    out = output_root / CSV_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    public = df.drop(columns=["_frozen_hash"])
    public.to_csv(out, index=False)
    write_mean_crosscheck_report(output_root, crosscheck_rows)
    if profile == "full":
        sync_full_pullback_manifest(output_root, duration_seconds=elapsed)
    print(
        json.dumps(
            {
                "profile": profile,
                "instances": config["instance_ids"],
                "frozen_hashes": frozen_hashes,
                "mean_crosscheck": crosscheck_rows,
                "output": CSV_REL.as_posix(),
                "rows": int(len(public)),
                "duration_seconds": elapsed,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return public


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--profile", default="smoke")
    args = parser.parse_args(argv)
    run(Path(args.output).resolve(), profile=args.profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
