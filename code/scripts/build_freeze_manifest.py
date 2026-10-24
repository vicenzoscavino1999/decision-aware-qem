from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.update_reference_manifest import git_value, sha256  # noqa: E402


OUTPUT_REL = Path("results/frozen/freeze_manifest.json")

PRIMARY_CONFIGS = [
    Path("reproducibility/config/selectors.yaml"),
    Path("reproducibility/config/decision_aware_qem.yaml"),
    Path("reproducibility/config/budget_allocation.yaml"),
    Path("reproducibility/config/budget_grid.yaml"),
    Path("reproducibility/config/gri_calibration.yaml"),
    Path("reproducibility/config/inference.yaml"),
    Path("reproducibility/config/claim_registry.yaml"),
    Path("reproducibility/config/pullback_prediction_spec.yaml"),
    Path("reproducibility/config/confirmatory_design.yaml"),
    Path("reproducibility/config/dynamic_task.yaml"),
    Path("reproducibility/config/a3_pullback_frontier.yaml"),
    Path("reproducibility/config/gate0_pilot.yaml"),
    Path("reproducibility/config/a3_gaussianity.yaml"),
    Path("reproducibility/config/cdev_learning.yaml"),
    Path("reproducibility/config/rng_policy.yaml"),
    Path("reproducibility/config/tolerances.yaml"),
]

FROZEN_ARTIFACTS = [
    Path("results/frozen/budget_ledger.csv"),
    Path("results/frozen/confirmatory_instance_manifest.csv"),
    Path("results/frozen/contrast_matrices.npz"),
    Path("results/frozen/critical_bands.csv"),
]

CONFIRMATORY_AND_SHARED_CODE = [
    Path("experiments/e1_static_da_selector.py"),
    Path("experiments/e2_dynamic_batch_candidate_optimizer.py"),
    Path("experiments/e3_bstar_prediction.py"),
    Path("experiments/a3_pullback_frontier.py"),
    Path("experiments/gate0_pilot_full_vs_diagonal.py"),
    Path("experiments/pilot_power_report.py"),
    Path("experiments/confirmatory_instance_manifest.py"),
    Path("reproducibility/run_all.py"),
    Path("reproducibility/verify.py"),
    Path("scripts/build_freeze_manifest.py"),
    Path("scripts/update_reference_manifest.py"),
]

PILOT_REFERENCE_OUTPUTS = [
    Path("reproducibility/reference/reference_manifest.json"),
]

PAP_FILES = [
    Path("PAP_HASH.txt"),
]

SECONDARY_EXCLUDED_CONFIGS = [
    Path("reproducibility/config/regime_frontier.yaml"),
    Path("reproducibility/config/focal_lower_bound.yaml"),
    Path("reproducibility/config/gri_empirical_ablation.yaml"),
    Path("reproducibility/config/method_tuning_ablation.yaml"),
    Path("reproducibility/config/budget_ledger_schema.yaml"),
]

SMOKE_OUTPUT_PATTERNS = [
    "results/confirmatory/e1_static_decision_failure.csv",
    "results/confirmatory/e1_static_decision_failure.md",
    "results/confirmatory/e1_static_selector_table.csv",
    "results/confirmatory/e2_dynamic_confirmatory_dyn_smoke.md",
    "results/confirmatory/e3_pullback_frontier.csv",
    "results/confirmatory/e3_pullback_frontier.md",
    "results/confirmatory/raw/*.npz",
    "results/confirmatory/a3_frozen_prediction/*.npz",
]


def freeze_file_list() -> list[Path]:
    src_files = [
        path.relative_to(REPO_ROOT)
        for path in sorted((REPO_ROOT / "src" / "daqem").glob("*.py"))
    ]
    files = (
        PRIMARY_CONFIGS
        + FROZEN_ARTIFACTS
        + CONFIRMATORY_AND_SHARED_CODE
        + src_files
        + PILOT_REFERENCE_OUTPUTS
        + PAP_FILES
    )
    return sorted(dict.fromkeys(files), key=lambda path: path.as_posix())


def _version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def collect_versions() -> dict[str, str | None]:
    return {
        "python": sys.version.split()[0],
        "qiskit": _version("qiskit"),
        "qiskit-aer": _version("qiskit-aer"),
        "scipy": _version("scipy"),
        "cvxpy": _version("cvxpy"),
    }


def checksums_for(files: list[Path]) -> dict[str, str]:
    checksums: dict[str, str] = {}
    missing = []
    for rel in files:
        path = REPO_ROOT / rel
        if not path.exists():
            missing.append(rel.as_posix())
            continue
        checksums[rel.as_posix()] = f"sha256:{sha256(path)}"
    if missing:
        raise FileNotFoundError("missing freeze files: " + ", ".join(missing))
    return dict(sorted(checksums.items()))


def checksum_block(checksums: dict[str, str]) -> str:
    return "".join(f"{path} {digest}\n" for path, digest in sorted(checksums.items()))


def freeze_hash_from_checksums(checksums: dict[str, str]) -> str:
    block = checksum_block(checksums).encode("utf-8")
    return "sha256:" + hashlib.sha256(block).hexdigest().upper()


def build_manifest() -> dict[str, object]:
    pap_hash = (REPO_ROOT / "PAP_HASH.txt").read_text(encoding="utf-8").strip()
    checksums = checksums_for(freeze_file_list())
    release_root=REPO_ROOT.parent
    runtime_files=('Dockerfile','requirements-lock.linux.txt','reproduce.py')
    runtime_checksums={name:'sha256:'+sha256(release_root/name) for name in runtime_files}
    images=re.findall(r'^FROM\s+(\S+)',(release_root/'Dockerfile').read_text(),flags=re.MULTILINE)
    if not images or any('@sha256:' not in image for image in images):
        raise ValueError('Every Docker base image must be pinned by digest')
    return {
        "pap_hash": pap_hash,
        "vcs": "none (hashed by file content; not a git repo)",
        "git_tag": git_value(["git", "describe", "--tags", "--always"]),
        "git_commit_sha": git_value(["git", "rev-parse", "HEAD"]),
        "versions": collect_versions(),
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "checksums": checksums,
        "freeze_hash": freeze_hash_from_checksums(checksums),
        "runtime_contract":{"base_images":images,"checksums":runtime_checksums,
                            "scope":"Docker bases and dependency lock; complete release inventory is in ../release_manifest.json"},
        "secondary_excluded_configs": [path.as_posix() for path in SECONDARY_EXCLUDED_CONFIGS],
        "smoke_output_patterns_excluded": SMOKE_OUTPUT_PATTERNS,
    }


def write_manifest(output: Path = REPO_ROOT / OUTPUT_REL) -> dict[str, object]:
    manifest = build_manifest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    manifest = write_manifest()
    print(
        json.dumps(
            {
                "output": OUTPUT_REL.as_posix(),
                "files": len(manifest["checksums"]),
                "freeze_hash": manifest["freeze_hash"],
                "git_commit_sha": manifest["git_commit_sha"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
