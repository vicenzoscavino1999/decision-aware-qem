import json
import logging
import subprocess
import sys
from pathlib import Path

from reproducibility import run_all


REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_ALL = REPO_ROOT / "reproducibility" / "run_all.py"
GATE_OUTPUT = Path("level1/gate0_mini.csv")


def _run(output: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(RUN_ALL),
            "--mode",
            "fast",
            "--level",
            "1",
            "--output",
            str(output),
            *extra,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_first_run_creates_complete_checkpoint_and_clean_manifest(tmp_path):
    output = tmp_path / "results"
    result = _run(output)
    assert result.returncode == 0, result.stderr
    checkpoint = _json(output / ".partial" / "checkpoint.json")
    assert set(checkpoint["blocks"]) == {
        "level1/gate0_mini",
        "level1/pullback_mini",
        "level1/budget_ledger",
    }
    assert all(entry["status"] == "complete" for entry in checkpoint["blocks"].values())
    assert _json(output / "manifest.json")["execution_mode"] == "clean"


def test_second_run_reuses_complete_blocks_and_marks_resumed(tmp_path):
    output = tmp_path / "results"
    assert _run(output).returncode == 0
    result = _run(output)
    assert result.returncode == 0, result.stderr
    assert _json(output / "manifest.json")["execution_mode"] == "resumed"
    log = (output / "run.log").read_text(encoding="utf-8")
    assert log.count("skipping/reuse complete checkpoint") >= 3


def test_corrupted_output_recomputes_only_invalid_block(tmp_path):
    output = tmp_path / "results"
    assert _run(output).returncode == 0
    gate = output / GATE_OUTPUT
    original = gate.read_bytes()
    gate.write_bytes(b"corrupted")

    result = _run(output)
    assert result.returncode == 0, result.stderr
    assert gate.read_bytes() == original
    log = (output / "run.log").read_text(encoding="utf-8")
    assert "output hash mismatch: level1/gate0_mini.csv" in log
    assert "block=level1/gate0_mini start" in log


def test_restart_discards_partial_ledger_and_recomputes(tmp_path):
    output = tmp_path / "results"
    assert _run(output).returncode == 0
    marker = output / ".partial" / "stale.marker"
    marker.write_text("stale", encoding="ascii")

    result = _run(output, "--restart")
    assert result.returncode == 0, result.stderr
    assert not marker.exists()
    assert _json(output / "manifest.json")["execution_mode"] == "restarted"
    checkpoint = _json(output / ".partial" / "checkpoint.json")
    assert all(entry["status"] == "complete" for entry in checkpoint["blocks"].values())


def test_staged_tmp_without_final_output_is_not_reused(tmp_path):
    output = tmp_path / "results"
    assert _run(output).returncode == 0
    final = output / GATE_OUTPUT
    final.unlink()
    staged = output / ".partial" / "tmp" / "level1" / "gate0_mini" / GATE_OUTPUT
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_bytes(b"partial")

    result = _run(output)
    assert result.returncode == 0, result.stderr
    assert final.exists()
    assert final.read_bytes() != b"partial"
    checkpoint = _json(output / ".partial" / "checkpoint.json")
    assert checkpoint["blocks"]["level1/gate0_mini"]["status"] == "complete"
    log = (output / "run.log").read_text(encoding="utf-8")
    assert "output missing: level1/gate0_mini.csv" in log


def test_all_invalid_blocks_are_recomputed_without_resumed_label(tmp_path):
    output = tmp_path / "results"
    assert _run(output).returncode == 0
    for rel in [
        "level1/gate0_mini.csv",
        "pilot/pullback_frontier.csv",
        "frozen/budget_ledger.csv",
    ]:
        (output / rel).write_bytes(b"corrupted")

    result = _run(output)
    assert result.returncode == 0, result.stderr
    manifest = _json(output / "manifest.json")
    assert manifest["execution_mode"] == "clean"
    assert manifest["checkpoint_preexisting"] is True
    log = (output / "run.log").read_text(encoding="utf-8")
    assert "execution_mode=clean reused_blocks=0" in log


def test_concurrent_writer_is_rejected(tmp_path):
    output = tmp_path / "results"
    with run_all.RunLock(output):
        result = _run(output)
    assert result.returncode != 0
    assert "another run_all process is active" in result.stderr


def test_continue_on_error_writes_incomplete_manifest_and_runs_independent_block(
    tmp_path, monkeypatch
):
    output = tmp_path / "results"
    failed_rel = Path("pilot/failed.csv")
    completed_rel = Path("pilot/completed.csv")

    def fail(_staging: Path) -> None:
        raise RuntimeError("injected failure")

    def complete(staging: Path) -> None:
        path = staging / completed_rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("value\n1\n", encoding="ascii")

    blocks = [
        run_all.BlockSpec("level1/failing", (failed_rel,), fail),
        run_all.BlockSpec("level1/independent", (completed_rel,), complete),
    ]
    stale_failed = output / failed_rel
    stale_failed.parent.mkdir(parents=True, exist_ok=True)
    stale_failed.write_text("stale\n", encoding="ascii")
    monkeypatch.setattr(run_all, "_level1_blocks", lambda _stage, **_kwargs: blocks)
    complete_run = run_all.run_level1(
        output,
        None,
        restart_requested=False,
        checkpoint_preexisting=False,
        continue_on_error=True,
    )
    assert complete_run is False
    assert (output / completed_rel).exists()
    manifest = _json(output / "manifest.json")
    assert manifest["block_status"] == {
        "level1/failing": "incomplete",
        "level1/independent": "complete",
    }
    assert manifest["incomplete_blocks"] == ["level1/failing"]
    assert failed_rel.as_posix() not in manifest["outputs"]


def test_outputs_from_previous_stage_are_not_added_to_current_manifest(tmp_path):
    output = tmp_path / "results"
    assert _run(output).returncode == 0
    stale_csv = output / "pilot" / "executability_budget_table.csv"
    stale_md = output / "pilot" / "executability_budget_table.md"
    stale_csv.write_text("stale\n", encoding="ascii")
    stale_md.write_text("stale\n", encoding="ascii")

    result = _run(output)
    assert result.returncode == 0, result.stderr
    outputs = _json(output / "manifest.json")["outputs"]
    assert "pilot/executability_budget_table.csv" not in outputs
    assert "pilot/executability_budget_table.md" not in outputs


def test_changed_block_input_fingerprint_forces_recomputation(tmp_path):
    output = tmp_path / "results"
    checkpoint_path = output / ".partial" / "checkpoint.json"
    checkpoint = run_all._empty_checkpoint()
    input_path = tmp_path / "config.yaml"
    input_path.write_text("value: 1\n", encoding="ascii")
    output_rel = Path("pilot/fingerprint.csv")
    calls = 0

    def produce(staging: Path) -> None:
        nonlocal calls
        calls += 1
        path = staging / output_rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"call\n{calls}\n", encoding="ascii")

    spec = run_all.BlockSpec(
        "pilot/fingerprint",
        (output_rel,),
        produce,
        (input_path,),
    )
    assert run_all._run_block(output, checkpoint_path, checkpoint, spec) is False
    assert calls == 1
    assert run_all._run_block(output, checkpoint_path, checkpoint, spec) is True
    assert calls == 1

    input_path.write_text("value: 2\n", encoding="ascii")
    assert run_all._run_block(output, checkpoint_path, checkpoint, spec) is False
    assert calls == 2


def test_logging_suppresses_third_party_info(tmp_path):
    output = tmp_path / "results"
    run_all._setup_logging(output)
    logging.getLogger("qiskit.test").info("third-party-noise")
    logging.getLogger("run_all").info("owned-message")
    logging.shutdown()
    log = (output / "run.log").read_text(encoding="utf-8")
    assert "owned-message" in log
    assert "third-party-noise" not in log


def test_fingerprint_includes_e0_runtime_dependencies():
    versions = run_all._fingerprint_dependency_versions()
    assert "networkx" in versions
    assert "PyYAML" in versions


def test_gate0_pilot_generation_blocks_are_profile_scoped(tmp_path):
    smoke = {
        spec.block_id: spec
        for spec in run_all._level1_blocks("pilot", profile="smoke", output_root=tmp_path)
    }
    full = {
        spec.block_id: spec
        for spec in run_all._level1_blocks("pilot", profile="full", output_root=tmp_path)
    }
    assert "pilot/gate0_generate/smoke/P001" in smoke
    assert "pilot/gate0_generate/full/P001" in full
    assert smoke["pilot/gate0_generate/smoke/P001"].outputs == (
        Path("pilot/raw/P001.npz"),
    )
    assert full["pilot/gate0_generate/full/P001"].outputs == (
        Path("pilot/raw/P001.npz"),
    )
