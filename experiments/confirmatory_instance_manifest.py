from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from daqem.candidates import (  # noqa: E402
    CONFIRMATORY_E2_INSTANCE_IDS,
    CONFIRMATORY_INSTANCE_IDS,
    PILOT_INSTANCE_IDS,
    graph_seed_for_instance,
    landscape_for_instance,
    maxcut_graph_for_instance,
)
from daqem.dynamic import epsilon_opt_from_ideal_values  # noqa: E402


GRAPH_FAMILY = "random_regular"
N_QUBITS = 10
DEGREE = 3
DEPTH = 2
CANDIDATE_COUNT = 25
LOCAL_RADIUS = 0.16
SEARCH_RADIUS = 0.55
SEARCH_COUNT = 64
EPSILON_QUANTILE = 0.01
BUDGET_GRID = (256, 512, 1024, 2048, 4096, 8192)
B_STAR_OPERATIVE = 512
E1_REPLICATES = 40
E2_TRAJECTORIES = 40
STATIC_MIN_PAIRED_DECISIONS = 1500
DYNAMIC_MIN_PAIRED_TRAJECTORIES = 1200

SMOKE_IDS = tuple(f"C{i:03d}" for i in range(1, 4))
DEFAULT_OUTPUT = REPO_ROOT / "results" / "frozen" / "confirmatory_instance_manifest.csv"


def _stable_edges(graph: nx.Graph) -> tuple[tuple[int, int], ...]:
    return tuple(sorted((int(i), int(j)) for i, j in graph.edges()))


def _validate_primary_cell(
    instance_id: str,
    *,
    graph_family: str = GRAPH_FAMILY,
    depth: int = DEPTH,
) -> None:
    if graph_family != GRAPH_FAMILY:
        raise ValueError(f"unsupported graph_family for primary cell: {graph_family!r}")
    if int(depth) != DEPTH:
        raise ValueError(f"unsupported depth for primary cell: {depth!r}")
    if instance_id not in CONFIRMATORY_INSTANCE_IDS:
        raise ValueError(f"confirmatory instance id must be C001..C048; got {instance_id!r}")


def _pilot_graph_edges() -> dict[str, tuple[tuple[int, int], ...]]:
    return {
        instance_id: _stable_edges(maxcut_graph_for_instance(instance_id))
        for instance_id in PILOT_INSTANCE_IDS
    }


def verify_firewall_disjointness(instance_ids: tuple[str, ...]) -> None:
    overlap = set(instance_ids) & set(PILOT_INSTANCE_IDS)
    if overlap:
        raise ValueError(f"confirmatory ids overlap pilot ids: {sorted(overlap)}")

    pilot_seeds = {graph_seed_for_instance(instance_id) for instance_id in PILOT_INSTANCE_IDS}
    confirmatory_seeds = {
        graph_seed_for_instance(instance_id) for instance_id in instance_ids
    }
    seed_overlap = pilot_seeds & confirmatory_seeds
    if seed_overlap:
        raise ValueError(f"confirmatory graph seeds overlap pilot seeds: {sorted(seed_overlap)}")

    pilot_edges = _pilot_graph_edges()
    pilot_edge_sets = set(pilot_edges.values())
    collisions = []
    for instance_id in instance_ids:
        _validate_primary_cell(instance_id)
        edges = _stable_edges(maxcut_graph_for_instance(instance_id))
        if edges in pilot_edge_sets:
            collisions.append(instance_id)
    if collisions:
        raise ValueError(f"confirmatory graph edge sets collide with pilot graphs: {collisions}")


def verify_design_counts() -> None:
    if not set(CONFIRMATORY_E2_INSTANCE_IDS).issubset(CONFIRMATORY_INSTANCE_IDS):
        raise ValueError("E2 ids must be a subset of E1 ids")
    if len(CONFIRMATORY_INSTANCE_IDS) * E1_REPLICATES < STATIC_MIN_PAIRED_DECISIONS:
        raise ValueError("static paired decision count is below PAP gate")
    if len(CONFIRMATORY_E2_INSTANCE_IDS) * E2_TRAJECTORIES < DYNAMIC_MIN_PAIRED_TRAJECTORIES:
        raise ValueError("dynamic paired trajectory count is below PAP gate")


def _difficulty_bounds(epsilon_values: np.ndarray) -> tuple[float, float]:
    q1, q2 = np.quantile(np.asarray(epsilon_values, dtype=float), [1.0 / 3.0, 2.0 / 3.0])
    return float(q1), float(q2)


def assign_difficulty_terciles(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    q1, q2 = _difficulty_bounds(df["epsilon_opt_ideal"].to_numpy(dtype=float))

    def label(value: float) -> str:
        # Smaller epsilon means a tighter decision-quality tolerance.
        if float(value) <= q1:
            return "hard"
        if float(value) <= q2:
            return "medium"
        return "easy"

    out = df.copy()
    out["difficulty_tercile"] = [label(value) for value in out["epsilon_opt_ideal"]]
    bounds = {"hard_medium": q1, "medium_easy": q2}
    return out, bounds


def build_manifest(instance_ids: tuple[str, ...] = CONFIRMATORY_INSTANCE_IDS) -> tuple[pd.DataFrame, dict[str, float]]:
    verify_design_counts()
    verify_firewall_disjointness(instance_ids)
    rows = []
    for instance_id in instance_ids:
        _validate_primary_cell(instance_id)
        landscape = landscape_for_instance(
            instance_id,
            candidate_count=CANDIDATE_COUNT,
            depth=DEPTH,
            num_qubits=N_QUBITS,
            graph_degree=DEGREE,
            local_radius=LOCAL_RADIUS,
            search_radius=SEARCH_RADIUS,
            search_count=SEARCH_COUNT,
        )
        epsilon = epsilon_opt_from_ideal_values(
            landscape.ideal_values,
            quantile=EPSILON_QUANTILE,
        )
        rows.append(
            {
                "instance_id": instance_id,
                "graph_family": GRAPH_FAMILY,
                "depth": DEPTH,
                "n_qubits": N_QUBITS,
                "degree": DEGREE,
                "graph_seed": landscape.graph_seed,
                "epsilon_opt_ideal": float(epsilon),
                "difficulty_tercile": "unassigned",
                "in_E1": instance_id in CONFIRMATORY_INSTANCE_IDS,
                "in_E2": instance_id in CONFIRMATORY_E2_INSTANCE_IDS,
                "in_E3": instance_id in CONFIRMATORY_INSTANCE_IDS,
            }
        )
    df = pd.DataFrame(rows)
    df, bounds = assign_difficulty_terciles(df)
    ordered_cols = [
        "instance_id",
        "graph_family",
        "depth",
        "n_qubits",
        "degree",
        "graph_seed",
        "epsilon_opt_ideal",
        "difficulty_tercile",
        "in_E1",
        "in_E2",
        "in_E3",
    ]
    return df[ordered_cols], bounds


def write_manifest(df: pd.DataFrame, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)


def parse_instance_ids(raw: str | None, *, smoke: bool) -> tuple[str, ...]:
    if raw:
        ids = tuple(value.strip() for value in raw.split(",") if value.strip())
    elif smoke:
        ids = SMOKE_IDS
    else:
        ids = CONFIRMATORY_INSTANCE_IDS
    unknown = [value for value in ids if value not in CONFIRMATORY_INSTANCE_IDS]
    if unknown:
        raise ValueError(f"unknown confirmatory ids: {unknown}")
    return ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="write C001-C003 only")
    parser.add_argument("--instance-ids", default=None, help="comma-separated C### ids")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)

    instance_ids = parse_instance_ids(args.instance_ids, smoke=bool(args.smoke))
    df, bounds = build_manifest(instance_ids)
    output = Path(args.output).resolve()
    write_manifest(df, output)
    payload = {
        "output": str(output),
        "rows": int(len(df)),
        "instance_ids": list(instance_ids),
        "tercile_bounds": bounds,
        "noise_free": True,
        "ran_confirmatory_experiment": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
