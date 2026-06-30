from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_SCRIPT = REPO_ROOT / "scripts" / "archive_confirmatory_outputs.py"
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify_confirmatory.py"
CONFIRMATORY_RESULTS_ROOT = REPO_ROOT / "results" / "confirmatory"
CONFIRMATORY_RESULTS_MISSING = not CONFIRMATORY_RESULTS_ROOT.exists()
CONFIRMATORY_RESULTS_SKIP_REASON = (
    "host-only: archiva desde el árbol confirmatorio completo, excluido de la imagen"
)


def _run_archive(tmp_path: Path) -> Path:
    archive_root = tmp_path / "reference_confirmatory"
    subprocess.run(
        [
            sys.executable,
            str(ARCHIVE_SCRIPT),
            "--source-root",
            str(CONFIRMATORY_RESULTS_ROOT),
            "--archive-root",
            str(archive_root),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return archive_root


@pytest.mark.skipif(CONFIRMATORY_RESULTS_MISSING, reason=CONFIRMATORY_RESULTS_SKIP_REASON)
def test_confirmatory_archive_verify_passes(tmp_path: Path) -> None:
    archive_root = _run_archive(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), "--archive-root", str(archive_root)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CONFIRMATORY VERIFY PASS" in proc.stdout
    assert len(list((archive_root / "raw").glob("*.npz"))) == 48
    assert len(list((archive_root / "a3").glob("*.npz"))) == 48
    assert len(list((archive_root / "e2" / "instances").glob("*_results.csv"))) == 32
    assert len(list((archive_root / "e2" / "instances").glob("*_trace.csv"))) == 32
    assert len(list((archive_root / "e2" / "instances").glob("*_cost.json"))) == 32


@pytest.mark.skipif(CONFIRMATORY_RESULTS_MISSING, reason=CONFIRMATORY_RESULTS_SKIP_REASON)
def test_confirmatory_verify_fails_on_corrupted_archive(tmp_path: Path) -> None:
    archive_root = _run_archive(tmp_path)
    corrupted = tmp_path / "corrupted_reference"
    shutil.copytree(archive_root, corrupted)
    target = corrupted / "e1" / "e1_static_decision_failure.csv"
    target.write_text(target.read_text(encoding="utf-8") + "\n# corrupt\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), "--archive-root", str(corrupted)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    assert proc.returncode != 0
    assert "checksum mismatch" in proc.stdout


@pytest.mark.skipif(CONFIRMATORY_RESULTS_MISSING, reason=CONFIRMATORY_RESULTS_SKIP_REASON)
def test_confirmatory_summary_expected_targets(tmp_path: Path) -> None:
    archive_root = _run_archive(tmp_path)
    summary = json.loads(
        (archive_root / "confirmatory_claims_summary.json").read_text(encoding="utf-8")
    )
    e1 = summary["e1"]["aggregate"]
    assert e1["both_fail"] == 725
    assert e1["both_ok"] == 967
    assert e1["b"] == 165
    assert e1["c"] == 63
    assert e1["paired_n"] == 1920
    assert round(e1["failure_rate_MSE"], 6) == 0.463542
    assert round(e1["failure_rate_DA"], 6) == 0.410417
    assert round(e1["observed_rel_reduction"], 6) == 0.114607
    assert round(e1["mcnemar_z"], 4) == 6.7551
    assert e1["one_sided_reject"] is True

    e3 = summary["e3"]
    assert e3["active_pairs"] == 502
    assert e3["ordering_matches"] == 502
    assert e3["directional_match_fraction"] == 1.0
    assert e3["directionally_sensitive_pass"] == 487
    assert e3["fail"] == 15

    e2 = summary["e2"]
    assert [round(e2["aggregate_success_decision"]["DA"][str(b)], 4) for b in e2["budgets"]] == [
        0.5078,
        0.5773,
        0.6562,
        0.7,
        0.7461,
        0.7758,
    ]
    assert [round(e2["aggregate_success_decision"]["MSE"][str(b)], 4) for b in e2["budgets"]] == [
        0.4766,
        0.5531,
        0.6406,
        0.693,
        0.7578,
        0.7883,
    ]
    assert e2["reaches_0.80"] == {"DA": False, "MSE": False}
    assert e2["per_instance_reach_counts"]["DA_reaches"] == 15
    assert e2["per_instance_reach_counts"]["MSE_reaches"] == 14
    assert e2["median_shot_ratio_MSE_over_DA_where_both_reach"] == 6.0
