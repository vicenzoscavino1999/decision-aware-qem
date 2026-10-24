import json
from pathlib import Path

from scripts import build_freeze_manifest as bfm


def test_freeze_manifest_contains_explicit_freeze_file_list():
    manifest = json.loads((bfm.REPO_ROOT / bfm.OUTPUT_REL).read_text(encoding="utf-8"))
    checksums = manifest["checksums"]

    for rel in bfm.freeze_file_list():
        assert rel.as_posix() in checksums

    assert checksums["results/frozen/confirmatory_instance_manifest.csv"] == (
        "sha256:71EE69F28807CF2D64A5E15D584B618C0D4D1588A7C706D7826B499D7E92BB60"
    )
    assert manifest["pap_hash"] == (
        "sha256:84317E348002DC98CFFB18D8F340A382C0675846C6298852E7465C0097628101"
    )


def test_freeze_manifest_excludes_secondary_configs_and_smoke_outputs():
    manifest = json.loads((bfm.REPO_ROOT / bfm.OUTPUT_REL).read_text(encoding="utf-8"))
    checksums = set(manifest["checksums"])

    for rel in bfm.SECONDARY_EXCLUDED_CONFIGS:
        assert rel.as_posix() not in checksums

    smoke_paths = {
        "results/confirmatory/e1_static_decision_failure.csv",
        "results/confirmatory/e1_static_decision_failure.md",
        "results/confirmatory/e1_static_selector_table.csv",
        "results/confirmatory/e2_dynamic_confirmatory_dyn_smoke.md",
        "results/confirmatory/e3_pullback_frontier.csv",
        "results/confirmatory/e3_pullback_frontier.md",
    }
    assert checksums.isdisjoint(smoke_paths)
    assert not any(path.startswith("results/confirmatory/raw/") for path in checksums)
    assert not any(
        path.startswith("results/confirmatory/a3_frozen_prediction/") for path in checksums
    )


def test_freeze_hash_is_deterministic_from_ordered_checksums():
    first = bfm.build_manifest()
    second = bfm.build_manifest()

    assert first["checksums"] == second["checksums"]
    assert first["freeze_hash"] == second["freeze_hash"]
    assert first["freeze_hash"] == bfm.freeze_hash_from_checksums(first["checksums"])
    assert first["vcs"] == "none (hashed by file content; not a git repo)"


def test_freeze_manifest_output_path_is_frozen_artifact():
    assert bfm.OUTPUT_REL == Path("results/frozen/freeze_manifest.json")
