"""End-to-end artifact assertions for the V2 replication package."""

from __future__ import annotations

from pathlib import Path
import json

import nbformat
import pandas as pd

from .analysis import HEADLINE_PATH, STATISTICS_PATH, SUMMARY_JSON_PATH
from .config import (
    ARM_ORDER,
    CHECKPOINTS,
    FIGURES_ROOT,
    JOOKEN_ARCHIVE,
    JOOKEN_ARCHIVE_SHA256,
    NOTEBOOKS_ROOT,
    PROTOCOL_LOCK_PATH,
    RESULTS_ROOT,
    RUNS_ROOT,
)
from .evaluation import EVALUATION_MANIFEST_PATH
from .io_utils import sha256_file, validate_run_directory
from .pisinger import ARCHIVE_NAMES, PISINGER_MANIFEST, PISINGER_ROOT
from .protocol import verify_history, verify_lock
from .runs import CHECKPOINTS_PATH, MODELS_PATH


def _verify_runs() -> int:
    markers = sorted(RUNS_ROOT.rglob("_SUCCESS.json"))
    for marker in markers:
        validate_run_directory(marker.parent)
    return len(markers)


def _verify_pisinger() -> str:
    if not PISINGER_MANIFEST.is_file():
        raise FileNotFoundError(PISINGER_MANIFEST)
    manifest = pd.read_csv(PISINGER_MANIFEST)
    if manifest.empty or manifest["name"].duplicated().any():
        raise AssertionError("Pisinger manifest is empty or has duplicate names")
    for archive_name in ARCHIVE_NAMES:
        path = PISINGER_ROOT / archive_name
        expected_values = manifest.loc[
            manifest["archive"] == archive_name, "archive_sha256"
        ].unique()
        if len(expected_values) != 1 or sha256_file(path) != expected_values[0]:
            raise AssertionError(f"Pisinger archive hash mismatch: {archive_name}")
    if not manifest["supplied_solution_profit"].eq(manifest["optimum"]).all():
        raise AssertionError("A Pisinger supplied solution does not match its optimum")
    return (
        f"PASS transfer: {len(manifest)} certificates, "
        f"{int(manifest['retained'].astype(bool).sum())} byte-distinct cases"
    )


def _verify_models() -> str:
    models = pd.read_csv(MODELS_PATH)
    counts = models.groupby("family").size().to_dict()
    if counts != {"AHDAS_BASE": 75, "GEP": 300, "RANDOM": 300}:
        raise AssertionError(f"Final model counts differ: {counts}")
    if models.duplicated(["family", "arm", "run"]).any():
        raise AssertionError("Duplicate final family/arm/run model")
    checkpoints = pd.read_csv(CHECKPOINTS_PATH)
    expected = sum(
        sum(value <= int(row.budget) for value in CHECKPOINTS)
        for row in models.itertuples(index=False)
    )
    if len(checkpoints) != expected:
        raise AssertionError(
            f"Checkpoint rows differ: expected {expected}, found {len(checkpoints)}"
        )
    if checkpoints.duplicated(["model_id", "raw_requests"]).any():
        raise AssertionError("Duplicate model/request checkpoint")
    return f"PASS models: {len(models)} final models and {len(checkpoints)} checkpoints"


def _verify_evaluations() -> str:
    manifest = pd.read_csv(EVALUATION_MANIFEST_PATH)
    if manifest.empty or manifest["path"].duplicated().any():
        raise AssertionError("Evaluation manifest is empty or duplicated")
    for row in manifest.itertuples(index=False):
        path = RESULTS_ROOT / row.path
        if not path.is_file() or sha256_file(path) != row.sha256:
            raise AssertionError(f"Evaluation artifact hash mismatch: {path}")
    return f"PASS evaluations: {len(manifest)} hashed evaluation files"


def _verify_notebook() -> str:
    path = NOTEBOOKS_ROOT / "gep_kp_iscmi2026_v2.ipynb"
    notebook = nbformat.read(path, as_version=4)
    markdown = "\n".join(
        cell.source for cell in notebook.cells if cell.cell_type == "markdown"
    )
    if "\\[" in markdown or "\\]" in markdown:
        raise AssertionError("Notebook contains forbidden bracket math delimiters")
    code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
    if any(cell.execution_count is None for cell in code_cells):
        raise AssertionError("Advisor notebook has not been fully executed")
    return f"PASS notebook: {len(code_cells)} executed code cells and dollar math"


def verify_available(*, require_complete: bool | None = None) -> list[str]:
    messages = verify_history()
    if sha256_file(JOOKEN_ARCHIVE) != JOOKEN_ARCHIVE_SHA256:
        raise AssertionError("Jooken archive hash changed")
    messages.append("PASS data: locked Jooken archive hash")
    if require_complete is None:
        require_complete = PROTOCOL_LOCK_PATH.is_file()
    if PROTOCOL_LOCK_PATH.is_file():
        verify_lock()
        messages.append("PASS protocol: source and manifest hashes match the lock")
    marker_count = _verify_runs()
    messages.append(f"PASS atomic runs: {marker_count} committed directories")
    if PISINGER_MANIFEST.is_file():
        messages.append(_verify_pisinger())
    elif require_complete:
        raise FileNotFoundError(PISINGER_MANIFEST)
    if MODELS_PATH.is_file():
        messages.append(_verify_models())
    elif require_complete:
        raise FileNotFoundError(MODELS_PATH)
    if EVALUATION_MANIFEST_PATH.is_file():
        messages.append(_verify_evaluations())
    elif require_complete:
        raise FileNotFoundError(EVALUATION_MANIFEST_PATH)
    if require_complete:
        for path in (HEADLINE_PATH, STATISTICS_PATH, SUMMARY_JSON_PATH):
            if not path.is_file():
                raise FileNotFoundError(path)
        for stem in (
            "headline_id_gap_v2",
            "anytime_id_v2",
            "generalization_regions_v2",
            "run_distribution_id_v2",
            "row_order_robustness_v2",
        ):
            for suffix in ("pdf", "svg", "png"):
                path = FIGURES_ROOT / f"{stem}.{suffix}"
                if not path.is_file() or path.stat().st_size == 0:
                    raise FileNotFoundError(path)
        messages.append("PASS analysis: headline, statistics, and publication figures")
        messages.append(_verify_notebook())
    return messages

