"""Protocol locking, environment capture, and V1 immutability checks."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import importlib.metadata
import json
import os
import platform
import subprocess
import zipfile

import pandas as pd

from .config import (
    BOOTSTRAP_REPLICATES,
    BOOTSTRAP_SEED,
    CHECKPOINTS,
    FINAL_RUNS,
    ENVIRONMENT_PATH,
    JOOKEN_ARCHIVE,
    JOOKEN_ARCHIVE_SHA256,
    PROJECT_ROOT,
    PROTOCOL_LOCK_PATH,
    REPOSITORY_ROOT,
    ROW_PERMUTATIONS,
    POWER_PLAN,
    ASSERTIONS_PATH,
    SEEDS_MANIFEST,
    SELECTED_CONFIG_PATH,
    SESOI_PPM,
    SPLIT_MANIFEST,
)
from .io_utils import atomic_json, hash_paths, sha256_file
from .pisinger import ARCHIVE_SPECS


HISTORY_MANIFEST = PROJECT_ROOT / "protocol" / "history_manifest.sha256"


def verify_history() -> list[str]:
    failures: list[str] = []
    for line in HISTORY_MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        path = (PROJECT_ROOT / relative).resolve()
        if not path.is_file():
            failures.append(f"missing {relative}")
        elif sha256_file(path) != expected:
            failures.append(f"changed {relative}")
    if failures:
        raise AssertionError("Historical artifact check failed: " + "; ".join(failures))
    return [f"PASS history: {len(HISTORY_MANIFEST.read_text().splitlines())} V1 files unchanged"]


def _system_command(command: list[str]) -> str | None:
    try:
        return subprocess.check_output(
            command, text=True, stderr=subprocess.STDOUT
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def environment_record() -> dict[str, object]:
    packages = (
        "numpy", "pandas", "scipy", "sympy", "matplotlib", "numba",
        "statsmodels", "psutil", "nbformat", "nbclient", "ipykernel", "pytest",
    )
    archive_commit = None
    if JOOKEN_ARCHIVE.exists():
        with zipfile.ZipFile(JOOKEN_ARCHIVE) as archive:
            archive_commit = archive.comment.decode("ascii", errors="replace").strip() or None
    return {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "logical_cores": os.cpu_count(),
        "packages": {name: importlib.metadata.version(name) for name in packages},
        "r_version": _system_command(["Rscript", "--version"]),
        "irace_version": _system_command(
            ["Rscript", "-e", "cat(as.character(packageVersion('irace')))" ]
        ),
        "jooken_archive_sha256": sha256_file(JOOKEN_ARCHIVE) if JOOKEN_ARCHIVE.exists() else None,
        "jooken_expected_sha256": JOOKEN_ARCHIVE_SHA256,
        "jooken_archive_commit": archive_commit,
    }


def locked_source_hashes() -> dict[str, str]:
    paths = list((PROJECT_ROOT / "src").glob("*.py"))
    paths.extend(
        [
            REPOSITORY_ROOT / "experiment_design_iscmi_v2.md",
            SPLIT_MANIFEST,
            SEEDS_MANIFEST,
            POWER_PLAN,
            ENVIRONMENT_PATH,
            ASSERTIONS_PATH,
            SELECTED_CONFIG_PATH,
            PROJECT_ROOT / "results" / "permutations_v2.csv.gz",
            PROJECT_ROOT / "results" / "power_ranker_config_v2.json",
            PROJECT_ROOT / "results" / "development" / "irace_elites_v2.csv",
            PROJECT_ROOT / "results" / "development" / "irace_all_configurations_v2.csv",
            PROJECT_ROOT / "results" / "development" / "irace_postselection_v2.csv",
            PROJECT_ROOT / "results" / "development" / "tuning_results_v2.csv.gz",
            PROJECT_ROOT / "results" / "development" / "survivor_summary_v2.csv",
            PROJECT_ROOT / "tuning" / "parameters.txt",
            PROJECT_ROOT / "tuning" / "instances.txt",
            PROJECT_ROOT / "tuning" / "run_irace.R",
            PROJECT_ROOT / "tuning" / "finalize_irace.R",
            PROJECT_ROOT / "tuning" / "target_runner.py",
            PROJECT_ROOT / "tuning" / "target-runner",
            PROJECT_ROOT / "tuning" / "R-packages.lock",
            PROJECT_ROOT / "tuning" / "work" / "_SUCCESS",
            PROJECT_ROOT / "tuning" / "work" / "final_elites.txt",
            PROJECT_ROOT / "tuning" / "work" / "scenario_used.txt",
            PROJECT_ROOT / "protocol" / "history_manifest.sha256",
            PROJECT_ROOT / "protocol" / "implementation_log.md",
            PROJECT_ROOT / "protocol" / "pisinger_sources.md",
            PROJECT_ROOT / "protocol" / "prelock_review.md",
            PROJECT_ROOT / "requirements.txt",
            PROJECT_ROOT / "Makefile",
        ]
    )
    paths.extend(sorted((PROJECT_ROOT / "tuning" / "work").glob("irace*.Rdata")))
    return hash_paths((path for path in paths if path.exists()), relative_to=REPOSITORY_ROOT)


def create_lock(approver: str) -> dict[str, object]:
    if not approver.strip():
        raise ValueError("A non-empty --approver is required")
    verify_history()
    for path in (SPLIT_MANIFEST, SEEDS_MANIFEST, SELECTED_CONFIG_PATH):
        if not path.is_file():
            raise FileNotFoundError(f"Cannot lock without {path}")
    selected = json.loads(SELECTED_CONFIG_PATH.read_text(encoding="utf-8"))
    transfer_archives = sorted((PROJECT_ROOT / "data" / "pisinger").glob("*.tgz"))
    transfer_manifest = PROJECT_ROOT / "results" / "pisinger_manifest_v2.csv"
    if (
        {path.name for path in transfer_archives} != set(ARCHIVE_SPECS)
        or not transfer_manifest.is_file()
    ):
        raise FileNotFoundError(
            "All three Pisinger archives and pisinger_manifest_v2.csv are required before lock"
        )
    transfer_rows = pd.read_csv(transfer_manifest)
    if transfer_rows.empty or transfer_rows["name"].duplicated().any():
        raise AssertionError("Pisinger manifest is empty or contains duplicate names")
    for path in transfer_archives:
        spec = ARCHIVE_SPECS[path.name]
        if path.stat().st_size != spec["bytes"] or sha256_file(path) != spec["sha256"]:
            raise AssertionError(f"Pisinger source fingerprint differs for {path.name}")
        declared = transfer_rows.loc[
            transfer_rows["archive"] == path.name, "archive_sha256"
        ].unique()
        if len(declared) != 1 or str(declared[0]) != sha256_file(path):
            raise AssertionError(f"Pisinger manifest hash differs for {path.name}")
        if int((transfer_rows["archive"] == path.name).sum()) != spec["cases"]:
            raise AssertionError(f"Pisinger case count differs for {path.name}")
    survivor_path = PROJECT_ROOT / "results" / "development" / "tuning_results_v2.csv.gz"
    survivor_rows = pd.read_csv(survivor_path)
    if (
        len(survivor_rows) != 200
        or survivor_rows.duplicated(["candidate_id", "arm", "run"]).any()
        or survivor_rows["candidate_id"].nunique() != 5
    ):
        raise AssertionError("The five-by-four-by-ten survivor matrix is incomplete")
    if selected.get("candidate_id") not in set(survivor_rows["candidate_id"]):
        raise AssertionError("Selected configuration is not one of the five survivors")
    lock = {
        "protocol_version": "2.0.0",
        "status": "locked",
        "locked_utc": datetime.now(timezone.utc).isoformat(),
        "approver": approver.strip(),
        "selected_config": selected,
        "source_hashes": locked_source_hashes(),
        "pisinger_archives": {
            path.name: sha256_file(path) for path in transfer_archives
        },
        "pisinger_manifest_sha256": sha256_file(transfer_manifest),
        "pisinger_cases": {
            "supplied": int(len(transfer_rows)),
            "retained_byte_distinct": int(transfer_rows["retained"].astype(bool).sum()),
        },
        "confirmatory": {
            "runs_per_arm": FINAL_RUNS,
            "checkpoints": CHECKPOINTS,
            "row_permutations": ROW_PERMUTATIONS,
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "sesoi_ppm": SESOI_PPM,
            "primary_contrast": "FULL - BASE",
            "secondary_contrasts": ["FULL - CAP", "FULL - SCALE"],
            "headline_order": ["BASE", "CAP", "SCALE", "FULL", "DEF", "MAXP", "MAXPW", "MINW"],
        },
    }
    atomic_json(lock, PROTOCOL_LOCK_PATH)
    return lock


def verify_lock() -> dict[str, object]:
    if not PROTOCOL_LOCK_PATH.is_file():
        raise PermissionError("Confirmatory access is blocked: protocol_lock.json does not exist")
    lock = json.loads(PROTOCOL_LOCK_PATH.read_text(encoding="utf-8"))
    if lock.get("status") != "locked":
        raise PermissionError("Protocol status is not locked")
    current = locked_source_hashes()
    if current != lock.get("source_hashes"):
        missing = sorted(set(lock.get("source_hashes", {})) - set(current))
        changed = sorted(
            key for key in set(current) & set(lock.get("source_hashes", {}))
            if current[key] != lock["source_hashes"][key]
        )
        extra = sorted(set(current) - set(lock.get("source_hashes", {})))
        raise PermissionError(
            f"Protocol source hash mismatch; missing={missing}, changed={changed}, extra={extra}"
        )
    for filename, expected in lock.get("pisinger_archives", {}).items():
        path = PROJECT_ROOT / "data" / "pisinger" / filename
        if not path.is_file() or sha256_file(path) != expected:
            raise PermissionError(f"Locked Pisinger archive mismatch: {filename}")
    transfer_manifest = PROJECT_ROOT / "results" / "pisinger_manifest_v2.csv"
    if (
        not transfer_manifest.is_file()
        or sha256_file(transfer_manifest) != lock.get("pisinger_manifest_sha256")
    ):
        raise PermissionError("Locked Pisinger manifest mismatch")
    verify_history()
    return lock
