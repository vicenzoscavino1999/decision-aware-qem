import json
from pathlib import Path

import numpy as np
import pandas as pd

from experiments import e1_static_da_selector as e1
from experiments import pilot_power_report as ppr
from experiments.gate0_pilot_full_vs_diagonal import (
    _write_deterministic_npz,
    confirmatory_raw_relpath,
)


def _write_manifest(root: Path) -> None:
    path = root / e1.MANIFEST_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "instance_id": "C001",
                "epsilon_opt_ideal": 0.01,
                "difficulty_tercile": "hard",
            },
            {
                "instance_id": "C017",
                "epsilon_opt_ideal": 0.03,
                "difficulty_tercile": "easy",
            },
        ]
    ).to_csv(path, index=False)


def _write_raw(root: Path, instance_id: str, *, offset: float) -> None:
    config = e1.load_gate0_config("confirmatory_e1_smoke")
    replicates = int(config["replicates"])
    scales = np.asarray(config["zne_lambdas"], dtype=float)
    candidate_count = int(config["candidate_count"])
    ideal_values = np.linspace(0.0, 2.4, candidate_count)
    estimates = np.empty((replicates, len(scales), candidate_count, 1), dtype=float)
    for r in range(replicates):
        for s, scale in enumerate(scales):
            noise = 0.01 * (r + 1) + 0.002 * s + offset
            estimates[r, s, :, 0] = ideal_values + noise
            estimates[r, s, 0, 0] = noise
            if r % 7 == 0:
                estimates[r, s, 1, 0] = noise - 0.03
    estimates = np.rint(estimates * 512) / 512
    metadata = {
        "profile": config["profile"],
        "output_namespace": "confirmatory",
        "instance_id": instance_id,
        "candidate_count": candidate_count,
        "replicates": replicates,
        "budget_grid": [512],
        "B_max": 512,
    }
    _write_deterministic_npz(
        root / confirmatory_raw_relpath(instance_id),
        metadata_json=np.array(json.dumps(metadata, sort_keys=True)),
        instance_id=np.array(instance_id),
        budgets=np.asarray([512], dtype=np.int64),
        zne_lambdas=scales,
        angles=np.zeros((candidate_count, 4), dtype=float),
        ideal_values=ideal_values,
        x_star=np.array(0, dtype=np.int64),
        graph_edges=np.asarray([(idx, (idx + 1) % 10) for idx in range(10)], dtype=np.int64),
        primitive_objective_estimates=estimates,
    )


def test_e1_uses_power_report_build_power_table():
    assert e1.build_power_table is ppr.build_power_table


def test_e1_smoke_from_confirmatory_raws_writes_confirmatory_outputs(tmp_path):
    _write_manifest(tmp_path)
    _write_raw(tmp_path, "C001", offset=0.0)
    _write_raw(tmp_path, "C017", offset=0.02)

    result = e1.run(tmp_path, profile="confirmatory_e1_smoke")

    assert result["rows"] == 2
    assert (tmp_path / e1.E1_CSV_REL).exists()
    assert (tmp_path / e1.SELECTOR_TABLE_REL).exists()
    assert (tmp_path / e1.REPORT_REL).exists()
    assert not (tmp_path / "pilot" / "e1_static_decision_failure.csv").exists()
    table = pd.read_csv(tmp_path / e1.E1_CSV_REL)
    assert set(table["cell"]) == {"C001", "C017"}
    assert set(table["budget"]) == {512}
    assert table["paired_n"].sum() == 40
    assert {"MSE_selected_method", "DA_selected_method", "epsilon_opt_tercile"}.issubset(
        table.columns
    )
    aggregate = result["aggregate"]
    assert aggregate["B_star_operational"] == 512
    assert aggregate["paired_n"] == 40
    assert isinstance(aggregate["mcnemar_one_sided_reject"], bool)


def test_build_power_table_default_signature_keeps_pilot_defaults():
    assert ppr.build_power_table.__defaults__[0] == ppr.DEFAULT_OUTPUT_ROOT
    assert ppr.build_power_table.__kwdefaults__["profile"] == "full"
    assert ppr.build_power_table.__kwdefaults__["raw_path_func"] is ppr.raw_relpath
    assert ppr.build_power_table.__kwdefaults__["expected_profile"] == "full"
