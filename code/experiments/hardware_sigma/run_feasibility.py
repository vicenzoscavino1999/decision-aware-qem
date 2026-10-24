from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
from qiskit import QuantumCircuit, transpile

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from daqem.candidates import build_candidate_landscape_for_graph
from daqem.qaoa import maxcut_value, qaoa_maxcut_circuit


INSTANCE_ID = "HSMC001"
SHOTS = 4096
CIRCUIT_COUNT = 8
SEED_TRANSPILE = 260616
OPTIMIZATION_LEVEL = 1
API_KEY_JSON = Path(os.environ.get("IBM_TOKEN_PATH", r"D:\paper fisica cuantica\apikey (1).json"))
OUTPUT_JSON = Path(__file__).resolve().parent / "feasibility_result.json"
SCALES = (1.0, 3.0)
CHARACTERIZATION_CIRCUITS_TARGET = 200
TOTAL_QUANTUM_TIME_CAP_MINUTES = 50.0
R_CAP = 200
METHOD_REPETITION_CIRCUITS = {
    "Raw": 4,
    "Accuracy-ZNE": 12,
    "DA-ZNE": 12,
}


@dataclass(frozen=True)
class PathScore:
    path: tuple[int, int, int, int]
    score: float
    mean_readout_error: float
    mean_two_qubit_error: float
    edge_errors: tuple[float, float, float]
    readout_errors: tuple[float, float, float, float]


def _load_token(path: Path = API_KEY_JSON) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    for key in ("apikey", "api_key", "token", "key"):
        value = payload.get(key)
        if value:
            return str(value)
    raise RuntimeError(f"API key JSON has no supported token field: {path}")


def _connect_service(region: str = "us-east", instance: str | None = None):
    from qiskit_ibm_runtime import QiskitRuntimeService

    kwargs: dict[str, Any] = {
        "channel": "ibm_quantum_platform",
        "token": _load_token(),
        "region": region,
        "plans_preference": ["open"],
    }
    if instance:
        kwargs["instance"] = instance
    return QiskitRuntimeService(**kwargs)


def _extract_pub_counts(pub_result: Any) -> dict[str, int]:
    data = getattr(pub_result, "data", None)
    if data is None:
        raise RuntimeError("Sampler result does not expose a data field")
    for register_name in ("meas", "c"):
        register = getattr(data, register_name, None)
        if register is not None and hasattr(register, "get_counts"):
            return {str(key): int(value) for key, value in register.get_counts().items()}
    if hasattr(data, "items"):
        for _, register in data.items():
            if hasattr(register, "get_counts"):
                return {str(key): int(value) for key, value in register.get_counts().items()}
    for register_name in dir(data):
        if register_name.startswith("_"):
            continue
        register = getattr(data, register_name, None)
        if hasattr(register, "get_counts"):
            return {str(key): int(value) for key, value in register.get_counts().items()}
    raise RuntimeError("Sampler result does not contain counts")


def _target_instruction_error(backend: Any, names: tuple[str, ...], qubits: tuple[int, ...]) -> float | None:
    target = getattr(backend, "target", None)
    if target is None:
        return None
    candidates = [tuple(int(q) for q in qubits)]
    if len(qubits) == 2:
        candidates.append((int(qubits[1]), int(qubits[0])))
    for name in names:
        try:
            inst_map = target[name]
        except Exception:
            continue
        for qtuple in candidates:
            try:
                props = inst_map[qtuple]
            except Exception:
                continue
            error = getattr(props, "error", None)
            if error is not None:
                return float(error)
    return None


def _properties_readout_error(backend: Any, qubit: int) -> float | None:
    try:
        props = backend.properties()
    except Exception:
        return None
    for attr in ("readout_error",):
        method = getattr(props, attr, None)
        if callable(method):
            try:
                return float(method(int(qubit)))
            except Exception:
                pass
    return None


def _properties_two_qubit_error(backend: Any, edge: tuple[int, int]) -> float | None:
    try:
        props = backend.properties()
    except Exception:
        return None
    for gate_name in ("ecr", "cx", "cz", "rzz"):
        for qubits in (edge, (edge[1], edge[0])):
            try:
                return float(props.gate_error(gate_name, list(qubits)))
            except Exception:
                continue
    return None


def readout_error(backend: Any, qubit: int) -> float:
    error = _target_instruction_error(backend, ("measure",), (int(qubit),))
    if error is None:
        error = _properties_readout_error(backend, int(qubit))
    if error is None:
        raise RuntimeError(f"missing readout error for qubit {qubit}")
    return float(error)


def two_qubit_error(backend: Any, edge: tuple[int, int]) -> float:
    error = _target_instruction_error(backend, ("ecr", "cx", "cz", "rzz"), edge)
    if error is None:
        error = _properties_two_qubit_error(backend, edge)
    if error is None:
        raise RuntimeError(f"missing two-qubit error for edge {edge}")
    return float(error)


def coupling_edges(backend: Any) -> set[tuple[int, int]]:
    cmap = getattr(backend, "coupling_map", None)
    raw = None
    if cmap is not None:
        try:
            raw = cmap.get_edges()
        except Exception:
            raw = list(cmap)
    if raw is None:
        target = getattr(backend, "target", None)
        raw = []
        if target is not None:
            for name in ("ecr", "cx", "cz", "rzz"):
                try:
                    raw.extend(tuple(q) for q in target[name])
                except Exception:
                    continue
    edges: set[tuple[int, int]] = set()
    for a, b in raw or []:
        a_i, b_i = int(a), int(b)
        if a_i != b_i:
            edges.add((min(a_i, b_i), max(a_i, b_i)))
    return edges


def _simple_paths_len4(edges: set[tuple[int, int]]) -> list[tuple[int, int, int, int]]:
    graph = nx.Graph()
    graph.add_edges_from(edges)
    paths: set[tuple[int, int, int, int]] = set()
    for start in graph.nodes:
        stack = [(int(start), [int(start)])]
        while stack:
            node, path = stack.pop()
            if len(path) == 4:
                paths.add(tuple(path))
                continue
            for nbr in sorted(graph.neighbors(node), reverse=True):
                nbr_i = int(nbr)
                if nbr_i not in path:
                    stack.append((nbr_i, [*path, nbr_i]))
    return sorted(paths)


def best_path_for_backend(backend: Any) -> PathScore:
    paths = _simple_paths_len4(coupling_edges(backend))
    if not paths:
        raise RuntimeError(f"backend {backend.name} has no connected four-qubit path")
    scored: list[PathScore] = []
    for path in paths:
        try:
            ro = tuple(readout_error(backend, q) for q in path)
            tq = tuple(two_qubit_error(backend, (path[i], path[i + 1])) for i in range(3))
        except RuntimeError:
            continue
        mean_ro = float(np.mean(ro))
        mean_tq = float(np.mean(tq))
        scored.append(
            PathScore(
                path=path,
                score=mean_ro + mean_tq,
                mean_readout_error=mean_ro,
                mean_two_qubit_error=mean_tq,
                edge_errors=tq,
                readout_errors=ro,
            )
        )
    if not scored:
        raise RuntimeError(f"backend {backend.name} has no scorable four-qubit path")
    return min(scored, key=lambda item: (item.score, item.path))


def select_backend_blind(service: Any, backend_name: str | None) -> tuple[Any, PathScore, list[dict[str, Any]]]:
    if backend_name:
        backend = service.backend(backend_name)
        score = best_path_for_backend(backend)
        return backend, score, []
    candidates = service.backends(min_num_qubits=4, operational=True, simulator=False)
    ranked: list[tuple[float, int, str, Any, PathScore]] = []
    audit: list[dict[str, Any]] = []
    for backend in candidates:
        try:
            score = best_path_for_backend(backend)
            pending = int(getattr(backend.status(), "pending_jobs", 10**9))
            ranked.append((score.score, pending, str(backend.name), backend, score))
            audit.append(
                {
                    "backend": str(backend.name),
                    "pending_jobs": pending,
                    "best_path": list(score.path),
                    "calibration_score": score.score,
                    "mean_readout_error": score.mean_readout_error,
                    "mean_two_qubit_error": score.mean_two_qubit_error,
                }
            )
        except Exception as exc:
            audit.append({"backend": str(getattr(backend, "name", "")), "excluded": str(exc)})
    if not ranked:
        raise RuntimeError("no operational real backend with a scorable four-qubit path")
    _, _, _, backend, score = min(ranked, key=lambda item: (item[0], item[1], item[2]))
    return backend, score, audit


def _calibration_snapshot_id(backend: Any) -> str:
    for obj in (getattr(backend, "target", None),):
        value = getattr(obj, "last_update_date", None)
        if value is not None:
            return str(value)
    try:
        props = backend.properties()
        value = getattr(props, "last_update_date", None)
        if value is not None:
            return str(value)
    except Exception:
        pass
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _path_graph() -> nx.Graph:
    graph = nx.Graph()
    graph.add_nodes_from(range(4))
    graph.add_edges_from([(0, 1), (1, 2), (2, 3)])
    return graph


def _fold_global_scale3(circuit: QuantumCircuit) -> QuantumCircuit:
    base = circuit.remove_final_measurements(inplace=False)
    folded = QuantumCircuit(base.num_qubits)
    folded.compose(base, inplace=True)
    folded.compose(base.inverse(), inplace=True)
    folded.compose(base, inplace=True)
    folded.measure_all()
    return folded


def _build_feasibility_circuits() -> list[dict[str, Any]]:
    graph = _path_graph()
    landscape = build_candidate_landscape_for_graph(
        INSTANCE_ID,
        graph,
        candidate_count=4,
        depth=1,
        local_radius=0.16,
        search_radius=0.55,
        search_count=64,
    )
    circuits: list[dict[str, Any]] = []
    for candidate_idx, angles in enumerate(landscape.angles):
        base = qaoa_maxcut_circuit(
            graph,
            depth=1,
            gammas=np.asarray(angles[:1], dtype=float),
            betas=np.asarray(angles[1:], dtype=float),
            measure=True,
        )
        circuits.append(
            {
                "label": f"candidate_{candidate_idx}_lambda_1",
                "candidate_idx": int(candidate_idx),
                "scale": 1.0,
                "circuit": base,
            }
        )
        circuits.append(
            {
                "label": f"candidate_{candidate_idx}_lambda_3",
                "candidate_idx": int(candidate_idx),
                "scale": 3.0,
                "circuit": _fold_global_scale3(base),
            }
        )
    if len(circuits) != CIRCUIT_COUNT:
        raise RuntimeError(f"expected {CIRCUIT_COUNT} feasibility circuits, got {len(circuits)}")
    return circuits


def _transpile(circuits: list[dict[str, Any]], backend: Any, path: tuple[int, int, int, int]) -> list[Any]:
    return transpile(
        [item["circuit"] for item in circuits],
        backend=backend,
        initial_layout=list(path),
        optimization_level=OPTIMIZATION_LEVEL,
        seed_transpiler=SEED_TRANSPILE,
    )


def _single_reference_transpile(backend: Any, path: tuple[int, int, int, int]):
    reference = _build_feasibility_circuits()[0]["circuit"]
    return transpile(
        reference,
        backend=backend,
        initial_layout=list(path),
        optimization_level=OPTIMIZATION_LEVEL,
        seed_transpiler=SEED_TRANSPILE,
    )


def _swap_count(circuit: Any) -> int:
    return int(dict(circuit.count_ops()).get("swap", 0))


def _observable_stats(counts: dict[str, int]) -> dict[str, Any]:
    graph = _path_graph()
    shots = sum(int(value) for value in counts.values())
    if shots <= 0:
        raise RuntimeError("empty counts")
    values = []
    weighted_sum = 0.0
    weighted_sq = 0.0
    max_count = max(int(value) for value in counts.values())
    for bitstring, count in counts.items():
        value = float(maxcut_value(str(bitstring), graph))
        values.append(value)
        weighted_sum += value * int(count)
        weighted_sq += value * value * int(count)
    mean = weighted_sum / shots
    variance = max(0.0, weighted_sq / shots - mean * mean)
    return {
        "shots": int(shots),
        "unique_bitstrings": int(len(counts)),
        "max_bitstring_probability": float(max_count / shots),
        "observable_mean": float(mean),
        "observable_variance": float(variance),
        "not_saturated": bool(max_count < shots and variance > 0.0 and math.isfinite(variance)),
    }


def _usage_summary(service: Any) -> dict[str, Any]:
    try:
        usage = service.usage()
    except Exception as exc:
        return {"available": False, "error": str(exc)}
    period = usage.get("usage_period") or {}
    return {
        "available": True,
        "consumed_seconds": usage.get("usage_consumed_seconds"),
        "remaining_seconds": usage.get("usage_remaining_seconds"),
        "limit_seconds": usage.get("usage_limit_seconds"),
        "limit_reached": usage.get("usage_limit_reached"),
        "period_start": period.get("start_time"),
        "period_end": period.get("end_time"),
    }


def _usage_delta_minutes(before: dict[str, Any], after: dict[str, Any], fallback_seconds: float) -> float:
    try:
        if before.get("available") and after.get("available"):
            b = before.get("consumed_seconds")
            a = after.get("consumed_seconds")
            if b is not None and a is not None and float(a) >= float(b):
                return float(a - b) / 60.0
    except Exception:
        pass
    return float(fallback_seconds) / 60.0


def _job_metadata(job: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {"job_id": job.job_id()}
    for attr in ("creation_date", "running", "done", "status"):
        value = getattr(job, attr, None)
        if callable(value):
            try:
                metadata[attr] = str(value())
            except Exception:
                pass
    for method in ("metrics", "usage_estimation"):
        value = getattr(job, method, None)
        if callable(value):
            try:
                metadata[method] = value()
            except Exception as exc:
                metadata[f"{method}_error"] = str(exc)
    return metadata


def _runtime_sizing(feasibility_minutes: float) -> dict[str, Any]:
    time_per_circuit = float(feasibility_minutes) / CIRCUIT_COUNT
    projected_c_noiselearn = time_per_circuit * CHARACTERIZATION_CIRCUITS_TARGET
    repetition_circuits = sum(METHOD_REPETITION_CIRCUITS.values())
    time_per_repetition = time_per_circuit * repetition_circuits
    remaining = TOTAL_QUANTUM_TIME_CAP_MINUTES - projected_c_noiselearn
    if remaining <= 0.0 or time_per_repetition <= 0.0:
        r_final = 0
        status = "stop_infeasible"
    else:
        raw_r = min(R_CAP, math.floor(remaining / time_per_repetition))
        r_final = int(raw_r - (raw_r % 10))
        status = "feasible" if r_final > 0 else "stop_infeasible"
    return {
        "time_per_feasibility_circuit_minutes": time_per_circuit,
        "projected_C_noiselearn_time_minutes": projected_c_noiselearn,
        "projected_time_per_interleaved_repetition_minutes": time_per_repetition,
        "method_repetition_circuits": METHOD_REPETITION_CIRCUITS,
        "R_final": r_final,
        "status": status,
    }


def run_feasibility(*, backend_name: str | None, region: str, instance: str | None) -> dict[str, Any]:
    service = _connect_service(region=region, instance=instance)
    usage_before = _usage_summary(service)
    backend, path_score, backend_audit = select_backend_blind(service, backend_name)
    reference_transpiled = _single_reference_transpile(backend, path_score.path)
    circuits = _build_feasibility_circuits()
    transpiled = _transpile(circuits, backend, path_score.path)

    from qiskit_ibm_runtime import SamplerV2 as Sampler

    sampler = Sampler(mode=backend)
    submitted_at = datetime.now(timezone.utc)
    wall_start = time.perf_counter()
    job = sampler.run(transpiled, shots=SHOTS)
    print(f"submitted_feasibility_job_id: {job.job_id()}", flush=True)
    result = job.result()
    wall_seconds = time.perf_counter() - wall_start
    completed_at = datetime.now(timezone.utc)
    usage_after = _usage_summary(service)

    count_rows = []
    captured_counts = []
    saturation_passed = True
    for item, pub in zip(circuits, result, strict=True):
        counts = _extract_pub_counts(pub)
        stats = _observable_stats(counts)
        if stats['shots'] != SHOTS:
            raise ValueError(f'Unexpected feasibility shot total: {stats["shots"]}')
        captured_counts.append(counts)
        saturation_passed = saturation_passed and bool(stats["not_saturated"])
        count_rows.append(
            {
                "label": item["label"],
                "candidate_idx": item["candidate_idx"],
                "scale": item["scale"],
                **stats,
            }
        )

    feasibility_minutes = _usage_delta_minutes(usage_before, usage_after, wall_seconds)
    sizing = _runtime_sizing(feasibility_minutes)
    target = getattr(backend, "target", None)
    result_payload = {
        "raw_counts": captured_counts,
        "created_utc": completed_at.isoformat(timespec="seconds"),
        "submitted_utc": submitted_at.isoformat(timespec="seconds"),
        "design": {
            "preregistered_document": "HARDWARE_SIGMA_MICROCELL_v1.md",
            "instance_id": INSTANCE_ID,
            "circuit_count": CIRCUIT_COUNT,
            "shots_per_circuit": SHOTS,
            "forbidden_outputs_computed": [],
        },
        "backend": {
            "name": str(backend.name),
            "num_qubits": int(getattr(backend, "num_qubits", 0)),
            "calibration_snapshot_id": _calibration_snapshot_id(backend),
            "operation_names": sorted(str(name) for name in getattr(backend, "operation_names", [])),
            "coupling_edges": [list(edge) for edge in sorted(coupling_edges(backend))],
            "basis_gates": sorted(str(gate) for gate in getattr(target, "operation_names", [])) if target is not None else [],
        },
        "backend_selection_audit": backend_audit,
        "physical_mapping": {
            "rule": "minimum_calibration_score_connected_four_qubit_path",
            "physical_qubits": list(path_score.path),
            "calibration_score": path_score.score,
            "mean_readout_error": path_score.mean_readout_error,
            "mean_two_qubit_error": path_score.mean_two_qubit_error,
            "readout_errors": list(path_score.readout_errors),
            "edge_errors": list(path_score.edge_errors),
            "transpiled_depth": int(reference_transpiled.depth() or 0),
            "swap_count": _swap_count(reference_transpiled),
        },
        "feasibility": {
            "job_ids": [job.job_id()],
            "job_metadata": _job_metadata(job),
            "usage_before": usage_before,
            "usage_after": usage_after,
            "wall_clock_minutes": wall_seconds / 60.0,
            "feasibility_quantum_time_minutes": feasibility_minutes,
            "counts_summary": count_rows,
            "observable_not_saturated_all_circuits": bool(saturation_passed),
        },
        "runtime_sizing": sizing,
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(result_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Hardware-Sigma feasibility mini-job only.")
    parser.add_argument("--run-feasibility", action="store_true", help="Submit the 8-circuit feasibility job.")
    parser.add_argument("--backend", default=None, help="Optional backend override; default uses blind calibration score.")
    parser.add_argument("--region", default="us-east")
    parser.add_argument("--instance", default=os.environ.get("QISKIT_IBM_INSTANCE") or None)
    args = parser.parse_args()
    if not args.run_feasibility:
        raise SystemExit("Refusing to run implicitly; pass --run-feasibility for the mini-job.")
    payload = run_feasibility(
        backend_name=args.backend,
        region=str(args.region),
        instance=args.instance,
    )
    backend = payload["backend"]
    mapping = payload["physical_mapping"]
    feasibility = payload["feasibility"]
    sizing = payload["runtime_sizing"]
    print("HARDWARE_SIGMA_FEASIBILITY_COMPLETE")
    print(f"backend={backend['name']}")
    print(f"physical_qubits={mapping['physical_qubits']}")
    print(f"calibration_score={mapping['calibration_score']:.8g}")
    print(f"transpiled_depth={mapping['transpiled_depth']}")
    print(f"swap_count={mapping['swap_count']}")
    print(f"job_ids={feasibility['job_ids']}")
    print(f"feasibility_quantum_time_minutes={feasibility['feasibility_quantum_time_minutes']:.6g}")
    print(f"observable_not_saturated_all_circuits={feasibility['observable_not_saturated_all_circuits']}")
    print(f"projected_C_noiselearn_time_minutes={sizing['projected_C_noiselearn_time_minutes']:.6g}")
    print(f"projected_time_per_interleaved_repetition={sizing['projected_time_per_interleaved_repetition_minutes']:.6g}")
    print(f"R_final={sizing['R_final']}")
    print(f"status={sizing['status']}")
    print(f"result_json={OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
