from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
import yaml
from qiskit import transpile
from qiskit_aer import AerSimulator

from daqem.candidates import assert_pilot_instance, pilot_maxcut_graph
from daqem.cdev import (
    aggregate_learned_rates,
    characterization_circuit,
    decay_expectation_from_counts,
    fit_depolarizing_rate,
    learned_depolarizing_noise_model,
    sparse_pl_basis,
    support_f1_score,
    weighted_relative_l1_error,
)
from daqem.gap_kernel import nearest_psd
from daqem.noise import ONE_QUBIT_DEPOLARIZING, TWO_QUBIT_DEPOLARIZING, depolarizing_noise_model
from daqem.rng import make_rng

from experiments.a3_pullback_frontier import (
    FROZEN_REL_DIR,
    _covariance,
    _primitive_objective_moments,
    _validate_raw,
)
from experiments.gate0_pilot_full_vs_diagonal import load_config as load_gate0_config
from experiments.gate0_pilot_full_vs_diagonal import raw_relpath


CONFIG_PATH = REPO_ROOT / "reproducibility" / "config" / "cdev_learning.yaml"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "results"
REPORT_REL = Path("pilot") / "cdev_learned_arm.md"
PULLBACK_REL = Path("pilot") / "pullback_frontier.csv"
GAUSSIANITY_REL = Path("pilot") / "a3_gaussianity.md"
SIGMAHAT_AUDIT_REL = Path("pilot") / "a3_sigmahat_audit.md"


def _sha256_bytes(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest().upper()}"


def load_config(profile: str = "smoke") -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    profiles = raw.get("profiles", {})
    if profile not in profiles:
        raise ValueError(f"unknown C_dev learning profile: {profile}")
    config = dict(raw.get("defaults", {}))
    config.update(profiles[profile])
    config["profile"] = profile
    gate0_config = load_gate0_config(str(config["gate0_profile"]))
    for instance_id in config["instance_ids"]:
        assert_pilot_instance(str(instance_id))
        if instance_id not in gate0_config["instance_ids"]:
            raise ValueError(f"{instance_id} is not present in Gate 0 profile")
    if not isinstance(config["shots_per_circuit"], int):
        raise ValueError("shots_per_circuit must be concrete for executable profiles")
    config["gate0_config"] = gate0_config
    return config


def build_generator_basis(config: dict):
    gate0 = config["gate0_config"]
    graph = pilot_maxcut_graph(
        str(config["basis_instance_id"]),
        num_qubits=int(gate0["qubits"]),
        degree=int(gate0["graph_degree"]),
    )
    return sparse_pl_basis(
        num_qubits=int(gate0["qubits"]),
        graph_edges=graph.edges(),
        include_one_qubit=bool(config["include_one_qubit_generators"]),
        include_graph_edges=bool(config["include_graph_edge_generators"]),
    )


def true_rate_vector(generators) -> np.ndarray:
    return np.asarray(
        [
            ONE_QUBIT_DEPOLARIZING if gen.kind == "one_qubit" else TWO_QUBIT_DEPOLARIZING
            for gen in generators
        ],
        dtype=float,
    )


def learn_sparse_pl_channel(config: dict, generators) -> dict[str, object]:
    start = time.perf_counter()
    depths = [int(value) for value in config["characterization_depths"]]
    twirls = int(config["pauli_twirls"])
    shots = int(config["shots_per_circuit"])
    circuits = []
    metadata = []
    for gen_idx, generator in enumerate(generators):
        for depth in depths:
            circuit = characterization_circuit(generator, depth)
            for twirl_idx in range(twirls):
                circuits.append(circuit)
                metadata.append((gen_idx, depth, twirl_idx))

    rng = make_rng(
        instance_id=str(config["basis_instance_id"]),
        method="sparse_pl_characterization",
        budget=shots,
        replicate_id=0,
        stream=f"cdev_learning_{config['profile']}",
    )
    seed = int(rng.integers(1, 2**31 - 1))
    simulator = AerSimulator(
        noise_model=depolarizing_noise_model(),
        seed_simulator=seed,
    )
    transpiled = transpile(circuits, simulator, seed_transpiler=seed, optimization_level=0)
    result = simulator.run(transpiled, shots=shots).result()

    expectations = {idx: {depth: [] for depth in depths} for idx in range(len(generators))}
    for circuit_idx, (gen_idx, depth, _twirl_idx) in enumerate(metadata):
        counts = result.get_counts(circuit_idx)
        expectations[gen_idx][depth].append(
            decay_expectation_from_counts(counts, generators[gen_idx], depth)
        )

    learned_rates = np.empty(len(generators), dtype=float)
    mean_expectations = np.empty((len(generators), len(depths)), dtype=float)
    for gen_idx in range(len(generators)):
        y = np.asarray(
            [np.mean(expectations[gen_idx][depth]) for depth in depths],
            dtype=float,
        )
        mean_expectations[gen_idx] = y
        learned_rates[gen_idx] = fit_depolarizing_rate(np.asarray(depths), y)

    p1, p2 = aggregate_learned_rates(generators, learned_rates)
    return {
        "learned_rates": learned_rates,
        "mean_expectations": mean_expectations,
        "learned_p1": p1,
        "learned_p2": p2,
        "characterization_circuits": len(circuits),
        "characterization_shots": len(circuits) * shots,
        "duration_seconds": time.perf_counter() - start,
        "depths": depths,
        "twirls": twirls,
        "shots_per_circuit": shots,
        "seed": seed,
    }


def frozen_path(output_root: Path, instance_id: str) -> Path:
    return output_root / FROZEN_REL_DIR / f"{instance_id}.npz"


def _active_pullback_rows(output_root: Path, instance_id: str) -> pd.DataFrame:
    df = pd.read_csv(output_root / PULLBACK_REL)
    return df[(df["problem_cell"] == instance_id) & (df["active_pair"].astype(bool))]


def ranking_sensitivity_weights(
    *,
    output_root: Path,
    config: dict,
    generators,
) -> tuple[np.ndarray, str]:
    weights = np.zeros(len(generators), dtype=float)
    kind_indices = {
        "one_qubit": [idx for idx, gen in enumerate(generators) if gen.kind == "one_qubit"],
        "two_qubit": [idx for idx, gen in enumerate(generators) if gen.kind == "two_qubit"],
    }
    true_p = {
        "one_qubit": float(ONE_QUBIT_DEPOLARIZING),
        "two_qubit": float(TWO_QUBIT_DEPOLARIZING),
    }
    total_p = sum(true_p.values())
    for instance_id in config["instance_ids"]:
        frozen = np.load(frozen_path(output_root, instance_id), allow_pickle=False)
        active_rows = _active_pullback_rows(output_root, instance_id)
        budgets = [int(value) for value in frozen["budgets"]]
        method_names = [str(value) for value in frozen["method_names"]]
        gap_maps = np.asarray(frozen["gap_maps"], dtype=float)
        gradients = np.asarray(frozen["gradients"], dtype=float)
        cdev_diag = np.asarray(frozen["cdev_true_diag_unit"], dtype=float)
        for _, row in active_rows.iterrows():
            left, right = str(row["pair_id"]).split("_vs_")
            left_idx = method_names.index(left)
            right_idx = method_names.index(right)
            budget_idx = budgets.index(int(row["budget"]))
            budget = float(row["budget"])
            for kind, indices in kind_indices.items():
                if not indices:
                    continue
                fraction = true_p[kind] / total_p
                per_generator_diag_derivative = (
                    cdev_diag * fraction / max(true_p[kind], float(config["epsilon0"]))
                ) / float(len(indices))
                left_dsigma = (
                    gap_maps[left_idx] * per_generator_diag_derivative
                ) @ gap_maps[left_idx].T / budget
                right_dsigma = (
                    gap_maps[right_idx] * per_generator_diag_derivative
                ) @ gap_maps[right_idx].T / budget
                sensitivity = abs(
                    float(np.sum(gradients[left_idx, budget_idx] * left_dsigma))
                    - float(np.sum(gradients[right_idx, budget_idx] * right_dsigma))
                )
                for gen_idx in indices:
                    weights[gen_idx] += sensitivity
    if float(np.sum(weights)) <= 0.0:
        weights[:] = 1.0 / float(len(weights))
    else:
        weights /= float(np.sum(weights))
    payload = json.dumps(
        {
            "profile": config["profile"],
            "instance_ids": config["instance_ids"],
            "generator_names": [gen.name for gen in generators],
            "weights": [float(value) for value in weights],
            "freeze_weights_before_learning_results": True,
        },
        sort_keys=True,
    ).encode("utf-8")
    return weights, _sha256_bytes(payload)


def learned_sigmas_for_cell(
    *,
    instance_id: str,
    output_root: Path,
    config: dict,
    learned_p1: float,
    learned_p2: float,
) -> tuple[np.ndarray, np.ndarray]:
    frozen = np.load(frozen_path(output_root, instance_id), allow_pickle=False)

    def factory(_scale_idx: int, scale: float):
        return learned_depolarizing_noise_model(p1=learned_p1, p2=learned_p2, scale=scale)

    _means, variances, _ideal, _x_star = _primitive_objective_moments(
        instance_id=instance_id,
        gate0_config=dict(config["gate0_config"]),
        noise_model_factory=factory,
    )
    cdev_learned = variances.reshape(-1)
    gap_maps = np.asarray(frozen["gap_maps"], dtype=float)
    budgets = np.asarray(frozen["budgets"], dtype=np.int64)
    sigmas = np.empty_like(np.asarray(frozen["sigma_pred"], dtype=float))
    for method_idx, gap_map in enumerate(gap_maps):
        sigma_unit = (gap_map * cdev_learned) @ gap_map.T
        for budget_idx, budget in enumerate(budgets):
            sigmas[method_idx, budget_idx] = nearest_psd(sigma_unit / float(budget))
    return sigmas, cdev_learned


def _method_sigma_hat_from_raw(output_root: Path, instance_id: str, config: dict) -> np.ndarray:
    frozen = np.load(frozen_path(output_root, instance_id), allow_pickle=False)
    raw = np.load(output_root / raw_relpath(instance_id), allow_pickle=False)
    gate0 = dict(config["gate0_config"])
    _validate_raw(raw, instance_id, gate0)
    estimates = np.asarray(raw["primitive_objective_estimates"], dtype=float)
    ideal_values = np.asarray(raw["ideal_values"], dtype=float)
    x_star = int(raw["x_star"])
    competitors = [idx for idx in range(len(ideal_values)) if idx != x_star]
    method_coeffs = np.asarray(frozen["method_coefficients"], dtype=float)
    method_names = [str(value) for value in frozen["method_names"]]
    budgets = [int(value) for value in frozen["budgets"]]
    out = []
    for budget_idx, _budget in enumerate(budgets):
        primitive_gaps = (
            estimates[:, :, competitors, budget_idx] - estimates[:, :, [x_star], budget_idx]
        )
        budget_sigmas = []
        for method_idx, _method in enumerate(method_names):
            samples = np.einsum("s,rsd->rd", method_coeffs[method_idx], primitive_gaps)
            budget_sigmas.append(_covariance(samples, shrinkage=bool(gate0["use_ledoit_wolf"])))
        out.append(np.stack(budget_sigmas, axis=0))
    return np.stack(out, axis=0)


def _parse_gaussianity_valid(output_root: Path) -> dict[tuple[str, str, int], bool]:
    path = output_root / GAUSSIANITY_REL
    if not path.exists():
        return {}
    valid: dict[tuple[str, str, int], bool] = {}
    in_section = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## GRI vs Empirical Failure"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section or not line.startswith("| ") or line.startswith("| cell") or line.startswith("|---"):
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        valid[(parts[0], parts[1], int(parts[2]))] = parts[-1] == "True"
    return valid


def _parse_sigmahat_verdict(output_root: Path) -> dict[tuple[str, int, str], str]:
    path = output_root / SIGMAHAT_AUDIT_REL
    if not path.exists():
        return {}
    verdicts: dict[tuple[str, int, str], str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ") or line.startswith("| cell") or line.startswith("|---"):
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) == 8 and parts[2] != "ordering":
            verdicts[(parts[0], int(parts[1]), parts[2])] = parts[-1]
    return verdicts


def c2_c3_rows_for_cell(
    *,
    instance_id: str,
    output_root: Path,
    config: dict,
    sigma_learned: np.ndarray,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    frozen = np.load(frozen_path(output_root, instance_id), allow_pickle=False)
    pullback = pd.read_csv(output_root / PULLBACK_REL)
    pullback = pullback[pullback["problem_cell"] == instance_id]
    gaussianity_valid = _parse_gaussianity_valid(output_root)
    sigmahat_verdict = _parse_sigmahat_verdict(output_root)
    sigma_hat = _method_sigma_hat_from_raw(output_root, instance_id, config)
    method_names = [str(value) for value in frozen["method_names"]]
    budgets = [int(value) for value in frozen["budgets"]]
    sigma_true = np.asarray(frozen["sigma_pred"], dtype=float)
    gradients = np.asarray(frozen["gradients"], dtype=float)
    delta_pred = np.asarray(frozen["delta_pred"], dtype=float)
    pair_names = [str(value) for value in frozen["pair_names"]]
    rows_c2: list[dict[str, object]] = []
    rows_c3: list[dict[str, object]] = []
    for pair_idx, pair_id in enumerate(pair_names):
        left, right = pair_id.split("_vs_")
        left_idx = method_names.index(left)
        right_idx = method_names.index(right)
        for budget_idx, budget in enumerate(budgets):
            active_pair = bool(
                pullback[
                    (pullback["pair_id"] == pair_id) & (pullback["budget"] == budget)
                ]["active_pair"].iloc[0]
            )
            e_left = sigma_learned[left_idx, budget_idx] - sigma_true[left_idx, budget_idx]
            e_right = sigma_learned[right_idx, budget_idx] - sigma_true[right_idx, budget_idx]
            delta_rank = abs(
                float(np.sum(gradients[left_idx, budget_idx] * e_left))
                - float(np.sum(gradients[right_idx, budget_idx] * e_right))
            )
            tau_c = float(config["rho_C"]) * abs(float(delta_pred[pair_idx, budget_idx]))
            ratio = delta_rank / max(tau_c, float(config["epsilon0"]))
            frob_num = float(np.linalg.norm(e_left, ord="fro") + np.linalg.norm(e_right, ord="fro"))
            frob_den = float(
                np.linalg.norm(sigma_true[left_idx, budget_idx], ord="fro")
                + np.linalg.norm(sigma_true[right_idx, budget_idx], ord="fro")
            )
            frob_rel = frob_num / (frob_den + float(config["epsilon0"]))
            rows_c2.append(
                {
                    "cell": instance_id,
                    "pair_id": pair_id,
                    "budget": budget,
                    "active_pair": active_pair,
                    "delta_rank_C": delta_rank,
                    "tau_C": tau_c,
                    "projected_error_over_tolerance": ratio,
                    "relative_frobenius_error": frob_rel,
                    "c2_status": "pass" if ratio < 1.0 else "fail",
                    "frob_secondary": "pass"
                    if frob_rel < float(config["secondary_relative_frobenius_error_max"])
                    else "fail",
                }
            )

            h_left = sigma_hat[budget_idx, left_idx] - sigma_learned[left_idx, budget_idx]
            h_right = sigma_hat[budget_idx, right_idx] - sigma_learned[right_idx, budget_idx]
            learned_hat_delta = abs(
                float(np.sum(gradients[left_idx, budget_idx] * h_left))
                - float(np.sum(gradients[right_idx, budget_idx] * h_right))
            )
            learned_hat_ratio = learned_hat_delta / max(tau_c, float(config["epsilon0"]))
            a3_row = pullback[(pullback["pair_id"] == pair_id) & (pullback["budget"] == budget)].iloc[0]
            true_matches = str(a3_row["a3_status"]) == "pass"
            learned_matches = learned_hat_ratio < 1.0
            valid_left = gaussianity_valid.get((instance_id, left, budget), True)
            valid_right = gaussianity_valid.get((instance_id, right, budget), True)
            audit_verdict = sigmahat_verdict.get((instance_id, budget, pair_id), "not_reported")
            if not (valid_left and valid_right):
                interpretation = "empirical_fallback_only"
            elif "sampling_sensitive" in audit_verdict:
                interpretation = "inconclusive"
            elif true_matches and not learned_matches:
                interpretation = "noise_learning_failure"
            elif not true_matches:
                interpretation = "theory_or_model_limited"
            else:
                interpretation = "no_failure_detected"
            rows_c3.append(
                {
                    "cell": instance_id,
                    "pair_id": pair_id,
                    "budget": budget,
                    "active_pair": active_pair,
                    "true_vs_sigmahat_status": str(a3_row["a3_status"]),
                    "learned_vs_sigmahat_ratio": learned_hat_ratio,
                    "gaussianity_valid_pair": bool(valid_left and valid_right),
                    "sigmahat_audit_verdict": audit_verdict,
                    "c3_interpretation": interpretation,
                }
            )
    return rows_c2, rows_c3


def render_report(
    *,
    output_root: Path,
    config: dict,
    generators,
    weights_hash: str,
    weights: np.ndarray,
    learning: dict[str, object],
    c1: dict[str, object],
    c2_rows: list[dict[str, object]],
    c3_rows: list[dict[str, object]],
    cdev_learned_diag: np.ndarray,
    duration_seconds: float,
) -> None:
    out = output_root / REPORT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    profile_label = "Full" if str(config["profile"]) == "full" else "Smoke"
    lines = [
        f"# C_dev Learned Arm ({profile_label})",
        "",
        "Diagnostic only: not canonical, not part of verify/reference.",
        "",
        "## Alcance (honesto)",
        "",
        "- El canal de ruido en simulación es depolarizing UNIFORME: el mismo p1 en todos los qubits y el mismo p2 en todas las aristas.",
        "- Los circuitos de caracterización NO son qubit-específicos; por eso los 25 generadores colapsan a 2 mediciones distintas. Esto es ESTIMACIÓN DE 2 PARÁMETROS GLOBALES (p1, p2) por caracterización finito-shot, NO sparse Pauli-Lindblad espacialmente resuelto.",
        "- support_F1 es trivial por construcción, porque todos los generadores verdaderos son activos.",
        "- El valor real del sparse PL para ruido heterogéneo/dispositivo queda diferido: ver DECISION_DIFERIDA_F1cB_canal_heterogeneo.md.",
        "",
        "## Method",
        "",
        "- Sparse PL basis: 1q generators plus weight-2 generators on graph edges.",
        "- C1 weights are computed from frozen A3 gradients and active pairs before learning results.",
        "- Learned p1/p2 are injected into the same A3 primitive moment function, then propagated through frozen gap_maps.",
        "",
        "## Cost",
        "",
        "| characterization_circuits | shots_per_circuit | total_shots | learning_seconds | total_seconds |",
        "|---:|---:|---:|---:|---:|",
        "| {characterization_circuits} | {shots_per_circuit} | {characterization_shots} | {duration_seconds:.6g} | ".format(
            **learning
        )
        + f"{duration_seconds:.6g} |",
        "",
        "## C1 Channel Recovery",
        "",
        f"- weights_sha256: {weights_hash}",
        f"- generators: {len(generators)}",
        f"- learned_p1: {learning['learned_p1']:.9g}",
        f"- learned_p2: {learning['learned_p2']:.9g}",
        f"- cdev_learned_diag_sha256: {_sha256_bytes(np.asarray(cdev_learned_diag, dtype=float).tobytes())}",
        "",
        "| e_C | threshold | precision | recall | support_F1 | support_F1_min | c1_status |",
        "|---:|---:|---:|---:|---:|---:|---|",
        "| {e_C:.6g} | {e_C_threshold:.6g} | {precision:.6g} | {recall:.6g} | {support_F1:.6g} | {support_F1_min:.6g} | {c1_status} |".format(
            **c1
        ),
        "",
        "## C2 Propagation",
        "",
        "| cell | pair_id | B | active_pair | delta_rank_C | tau_C | ratio | rel_frob | c2_status | frob_secondary |",
        "|---|---|---:|---|---:|---:|---:|---:|---|---|",
    ]
    for row in c2_rows:
        lines.append(
            "| {cell} | {pair_id} | {budget} | {active_pair} | {delta_rank_C:.6g} | "
            "{tau_C:.6g} | {projected_error_over_tolerance:.6g} | "
            "{relative_frobenius_error:.6g} | {c2_status} | {frob_secondary} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## C3 Interpretation",
            "",
            "| cell | pair_id | B | active_pair | true_vs_sigmahat | learned_vs_sigmahat_ratio | gaussianity_valid_pair | sigmahat_audit | c3_interpretation |",
            "|---|---|---:|---|---|---:|---|---|---|",
        ]
    )
    for row in c3_rows:
        lines.append(
            "| {cell} | {pair_id} | {budget} | {active_pair} | {true_vs_sigmahat_status} | "
            "{learned_vs_sigmahat_ratio:.6g} | {gaussianity_valid_pair} | "
            "{sigmahat_audit_verdict} | {c3_interpretation} |".format(**row)
        )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(output_root: Path = DEFAULT_OUTPUT_ROOT, *, profile: str = "smoke") -> dict[str, object]:
    start = time.perf_counter()
    config = load_config(profile)
    generators = build_generator_basis(config)
    weights, weights_hash = ranking_sensitivity_weights(
        output_root=output_root,
        config=config,
        generators=generators,
    )
    learning = learn_sparse_pl_channel(config, generators)
    learned_rates = np.asarray(learning["learned_rates"], dtype=float)
    true_rates = true_rate_vector(generators)
    precision, recall, f1 = support_f1_score(
        true_rates,
        learned_rates,
        threshold=float(config["support_threshold"]),
    )
    e_c = weighted_relative_l1_error(
        learned_rates,
        true_rates,
        weights,
        eps0=float(config["epsilon0"]),
    )
    c1 = {
        "e_C": e_c,
        "e_C_threshold": float(config["relative_weighted_generator_error_max"]),
        "precision": precision,
        "recall": recall,
        "support_F1": f1,
        "support_F1_min": float(config["support_F1_min"]),
        "c1_status": "pass"
        if e_c <= float(config["relative_weighted_generator_error_max"])
        and f1 >= float(config["support_F1_min"])
        else "smoke_diagnostic_not_targeted",
    }
    c2_rows: list[dict[str, object]] = []
    c3_rows: list[dict[str, object]] = []
    learned_diag_last = np.array([], dtype=float)
    propagation_start = time.perf_counter()
    for instance_id in config["instance_ids"]:
        sigma_learned, learned_diag = learned_sigmas_for_cell(
            instance_id=str(instance_id),
            output_root=output_root,
            config=config,
            learned_p1=float(learning["learned_p1"]),
            learned_p2=float(learning["learned_p2"]),
        )
        learned_diag_last = learned_diag
        rows_c2, rows_c3 = c2_c3_rows_for_cell(
            instance_id=str(instance_id),
            output_root=output_root,
            config=config,
            sigma_learned=sigma_learned,
        )
        c2_rows.extend(rows_c2)
        c3_rows.extend(rows_c3)
    learning["propagation_seconds"] = time.perf_counter() - propagation_start
    elapsed = time.perf_counter() - start
    render_report(
        output_root=output_root,
        config=config,
        generators=generators,
        weights_hash=weights_hash,
        weights=weights,
        learning=learning,
        c1=c1,
        c2_rows=c2_rows,
        c3_rows=c3_rows,
        cdev_learned_diag=learned_diag_last,
        duration_seconds=elapsed,
    )
    result = {
        "profile": profile,
        "instances": config["instance_ids"],
        "generators": len(generators),
        "weights_sha256": weights_hash,
        "learned_p1": float(learning["learned_p1"]),
        "learned_p2": float(learning["learned_p2"]),
        "e_C": float(e_c),
        "support_F1": float(f1),
        "characterization_circuits": int(learning["characterization_circuits"]),
        "characterization_shots": int(learning["characterization_shots"]),
        "duration_seconds": float(elapsed),
        "output": REPORT_REL.as_posix(),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="smoke")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()
    run(Path(args.output).resolve(), profile=args.profile)


if __name__ == "__main__":
    main()
