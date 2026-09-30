"""Frozen protocol checks and explicit standalone-publication provenance."""

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


PUBLICATION_MANIFEST = PROJECT_ROOT / "provenance" / "publication_manifest.json"
ORIGINAL_SOURCE_PREFIX = "iscmi2026_v2/"
PACKAGING_ADAPTATIONS = {
    "Makefile": "Use repository-local setup, data retrieval, and publication commands.",
    "src/config.py": "Use the standalone repository as the repository root.",
    "src/protocol.py": "Verify original provenance and declared publication adaptations locally.",
    "tuning/target-runner": "Use the standalone virtual environment or ISCMI_PYTHON override.",
}


def original_publication_hashes(lock: dict[str, object]) -> dict[str, str]:
    """Flatten only the original V2 source names; reject unexpected ancestors."""
    original = lock.get("source_hashes")
    if not isinstance(original, dict) or not original:
        raise PermissionError("Original protocol has no source hashes")
    mapped: dict[str, str] = {}
    for name, expected in original.items():
        if name.startswith(ORIGINAL_SOURCE_PREFIX):
            relative = name[len(ORIGINAL_SOURCE_PREFIX):]
        elif name == "experiment_design_iscmi_v2.md":
            relative = name
        else:
            raise PermissionError(f"Unexpected original source path: {name}")
        _publication_path(relative)
        if relative in mapped:
            raise PermissionError(f"Duplicate flattened source path: {relative}")
        mapped[relative] = expected
    return mapped


def _publication_path(relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise PermissionError(f"Invalid publication path: {relative}")
    resolved = (PROJECT_ROOT / path).resolve()
    if not resolved.is_relative_to(PROJECT_ROOT.resolve()):
        raise PermissionError(f"Publication path escapes the repository: {relative}")
    return resolved


def verify_publication_sources() -> dict[str, object]:
    """Validate the untouched original lock and every declared packaging change."""
    if not PUBLICATION_MANIFEST.is_file():
        raise PermissionError("Missing publication manifest; frozen provenance cannot be verified")
    manifest = json.loads(PUBLICATION_MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise PermissionError("Unsupported publication manifest schema")
    if (
        not PROTOCOL_LOCK_PATH.is_file()
        or sha256_file(PROTOCOL_LOCK_PATH) != manifest.get("original_protocol_lock_sha256")
    ):
        raise PermissionError("Original protocol lock changed or is missing")
    lock = json.loads(PROTOCOL_LOCK_PATH.read_text(encoding="utf-8"))
    original = original_publication_hashes(lock)
    expected = manifest.get("expected_source_hashes")
    if not isinstance(expected, dict) or set(expected) != set(original):
        raise PermissionError("Publication source set differs from the original protocol")
    current = locked_source_hashes()
    if current != expected:
        missing = sorted(set(expected) - set(current))
        changed = sorted(key for key in set(current) & set(expected) if current[key] != expected[key])
        extra = sorted(set(current) - set(expected))
        raise PermissionError(
            f"Publication source hash mismatch; missing={missing}, changed={changed}, extra={extra}"
        )
    changes = {name for name in original if expected[name] != original[name]}
    adaptations = manifest.get("adaptations")
    if (
        not isinstance(adaptations, dict)
        or set(adaptations) != changes
        or not changes.issubset(PACKAGING_ADAPTATIONS)
    ):
        raise PermissionError("Undeclared or unsupported publication source adaptation")
    for name, adaptation in adaptations.items():
        snapshot = f"provenance/original/{name}"
        if (
            not isinstance(adaptation, dict)
            or adaptation.get("original_snapshot") != snapshot
            or adaptation.get("original_sha256") != original[name]
            or adaptation.get("packaged_sha256") != expected[name]
            or not adaptation.get("reason")
        ):
            raise PermissionError(f"Invalid publication adaptation: {name}")
        archive = _publication_path(snapshot)
        if not archive.is_file() or sha256_file(archive) != original[name]:
            raise PermissionError(f"Archived original changed or is missing: {snapshot}")
    return manifest


def verify_history() -> list[str]:
    manifest = verify_publication_sources()
    return [
        f"PASS publication: {len(manifest['expected_source_hashes'])} locked artifacts "
        "verified against original hashes and declared packaging adaptations",
        "INFO history: the original V1 manifest is retained as historical evidence; "
        "external V1 files are not distributed or rechecked by this release",
    ]


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
    """The paper release retains the original approval and cannot replace it."""
    raise PermissionError(
        "This publication preserves the original protocol lock. "
        "Do not relock the frozen paper artifacts; use a separate experiment "
        "and an explicitly new protocol for development or retuning."
    )


def verify_lock() -> dict[str, object]:
    if not PROTOCOL_LOCK_PATH.is_file():
        raise PermissionError("Confirmatory access is blocked: protocol_lock.json does not exist")
    lock = json.loads(PROTOCOL_LOCK_PATH.read_text(encoding="utf-8"))
    if lock.get("status") != "locked":
        raise PermissionError("Protocol status is not locked")
    verify_publication_sources()
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
    return lock
