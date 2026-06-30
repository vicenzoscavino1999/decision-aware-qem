from __future__ import annotations

import csv
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import experiments.proof_of_mechanism_run as pom


REPO_ROOT = Path(__file__).resolve().parents[1]
RESULT_CSV = REPO_ROOT / "results" / "phase_diagram" / "grid.csv"
REFERENCE_CSV = REPO_ROOT / "reproducibility" / "reference_extension" / "phase_diagram" / "grid.csv"
EXTENSION_MANIFEST = REPO_ROOT / "reproducibility" / "reference_extension" / "extension_manifest.json"
EXTENSION_CHECKSUMS = REPO_ROOT / "reproducibility" / "reference_extension" / "checksums.sha256"

INSTANCE_ID = "POM_001"
METHODS = ("Raw", "CDR", "PEC")
P1_GRID = (0.0025, 0.005, 0.0075, 0.01, 0.015, 0.02, 0.03, 0.04)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def phase_rows() -> list[dict[str, object]]:
    base_config = pom.load_config()
    p2_over_p1 = float(base_config["noise"]["p2"]) / float(base_config["noise"]["p1"])
    rows: list[dict[str, object]] = []
    for p1 in P1_GRID:
        config = copy.deepcopy(base_config)
        p2 = p2_over_p1 * float(p1)
        config["noise"]["p1"] = float(p1)
        config["noise"]["p2"] = float(p2)
        analytics = pom.instance_analytics(INSTANCE_ID, config)
        for budget in [int(value) for value in config["budget_grid"]]:
            budget_data = analytics["analytic_by_budget"][str(budget)]
            for method in METHODS:
                method_data = budget_data[method]
                rows.append(
                    {
                        "instance_id": INSTANCE_ID,
                        "p1": f"{float(p1):.12g}",
                        "p2": f"{float(p2):.12g}",
                        "budget": int(budget),
                        "method": method,
                        "mse": f"{float(method_data['MSE_expected']):.17g}",
                        "gri": f"{float(method_data['GRI']):.17g}",
                    }
                )
    return rows


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["instance_id", "p1", "p2", "budget", "method", "mse", "gri"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def update_reference(rows: list[dict[str, object]]) -> None:
    write_csv(rows, RESULT_CSV)
    write_csv(rows, REFERENCE_CSV)

    manifest = json.loads(EXTENSION_MANIFEST.read_text(encoding="utf-8"))
    checksums = manifest.setdefault("checksums", {})
    rel = "phase_diagram/grid.csv"
    checksums[rel] = "sha256:" + sha256(REFERENCE_CSV)
    manifest["created_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    EXTENSION_MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with EXTENSION_CHECKSUMS.open("w", encoding="utf-8", newline="\n") as handle:
        for path, digest in sorted(checksums.items()):
            handle.write(f"{digest}  {path}\n")


def separation_by_budget(rows: list[dict[str, object]]) -> dict[int, list[tuple[float, str, str]]]:
    grouped: dict[tuple[int, float], list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault((int(row["budget"]), float(row["p1"])), []).append(row)

    result: dict[int, list[tuple[float, str, str]]] = {}
    for (budget, p1), cell_rows in grouped.items():
        by_mse = min(cell_rows, key=lambda row: (float(row["mse"]), str(row["method"])))
        by_gri = min(cell_rows, key=lambda row: (float(row["gri"]), str(row["method"])))
        if str(by_mse["method"]) != str(by_gri["method"]):
            result.setdefault(budget, []).append((p1, str(by_mse["method"]), str(by_gri["method"])))
        else:
            result.setdefault(budget, [])
    return result


def main() -> int:
    rows = phase_rows()
    update_reference(rows)
    separation = separation_by_budget(rows)
    any_separation = any(values for values in separation.values())
    for budget in sorted(separation):
        examples = ", ".join(
            f"p1={p1:.4g}: MSE={mse_method}, GRI={gri_method}"
            for p1, mse_method, gri_method in separation[budget][:3]
        )
        print(
            f"budget={budget} separation={bool(separation[budget])}"
            + (f" examples=[{examples}]" if examples else "")
        )
    print(f"wrote={RESULT_CSV.relative_to(REPO_ROOT).as_posix()}")
    print(f"archived={REFERENCE_CSV.relative_to(REPO_ROOT).as_posix()}")
    if any_separation:
        print("PHASE GRID PASS")
    else:
        print("PHASE GRID COMPLETE: no argmin separation observed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
