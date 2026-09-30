"""Frozen-model evaluation on Jooken and external transfer instances."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Iterable, Iterator
import json

import numpy as np
import pandas as pd

from .baselines import (
    evaluate_baselines,
    evaluate_power_ranker,
)
from .config import (
    CHECKPOINTS,
    CONFIRMATORY_ROOT,
    JOOKEN_ARCHIVE,
    MAX_REQUESTS,
    RESULTS_ROOT,
    ROW_PERMUTATIONS,
    SPLIT_MANIFEST,
    TRANSFER_ROOT,
)
from .dataset import KnapsackInstance, load_partitions
from .gep import BatchEvaluator
from .io_utils import (
    atomic_csv,
    atomic_csv_stream,
    atomic_json,
    sha256_file,
)
from .protocol import verify_lock
from .pisinger import PISINGER_MANIFEST, iter_retained_batches
from .runs import CHECKPOINTS_PATH, MODELS_PATH


JOOKEN_EVALUATIONS_PATH = CONFIRMATORY_ROOT / "evaluations_jooken_v2.csv.gz"
ROW_ORDER_ROOT = CONFIRMATORY_ROOT / "row_order"
EVALUATION_MANIFEST_PATH = CONFIRMATORY_ROOT / "evaluation_manifest_v2.csv"
PISINGER_EVALUATIONS_PATH = TRANSFER_ROOT / "evaluations_pisinger_v2.csv.gz"

EVALUATION_COLUMNS = [
    "model_id",
    "method",
    "family",
    "arm",
    "run",
    "master_seed",
    "checkpoint",
    "gene",
    "dataset",
    "name",
    "group_id",
    "partition",
    "region",
    "permutation_index",
    "n",
    "c",
    "g",
    "f",
    "eps",
    "s",
    "profit",
    "optimum",
    "quality",
    "gap_ppm",
    "exact",
    "feasible",
    "packed_weight",
    "capacity",
]


def _model_specs(*, final_only: bool) -> pd.DataFrame:
    checkpoints = pd.read_csv(CHECKPOINTS_PATH, dtype={"master_seed": str})
    required = {
        "model_id",
        "family",
        "arm",
        "run",
        "master_seed",
        "gene",
        "raw_requests",
    }
    if not required.issubset(checkpoints):
        raise AssertionError(f"Checkpoint table lacks {sorted(required - set(checkpoints))}")
    specs = checkpoints.rename(columns={"raw_requests": "checkpoint"}).copy()
    specs["checkpoint"] = specs["checkpoint"].astype(int)
    if final_only:
        max_budget = specs.groupby("model_id")["checkpoint"].transform("max")
        specs = specs[specs["checkpoint"] == max_budget].copy()
    key = ["model_id", "checkpoint"]
    if specs.duplicated(key).any():
        raise AssertionError("Duplicate model/checkpoint rows")
    expected_models = pd.read_csv(MODELS_PATH)["model_id"].nunique()
    if final_only and len(specs) != expected_models:
        raise AssertionError(
            f"Final checkpoint count differs: {len(specs)} versus {expected_models} models"
        )
    return specs.sort_values(["family", "arm", "run", "checkpoint"], kind="stable")


def _instance_frame(instances: list[KnapsackInstance]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "dataset": [item.dataset for item in instances],
            "name": [item.name for item in instances],
            "group_id": [item.group_id for item in instances],
            "partition": [item.partition for item in instances],
            "region": [item.region for item in instances],
            "n": [item.n for item in instances],
            "c": [item.c for item in instances],
            "g": [item.g for item in instances],
            "f": [item.f for item in instances],
            "eps": [item.eps for item in instances],
            "s": [item.s for item in instances],
            "optimum": [item.optimum for item in instances],
            "capacity": [item.capacity for item in instances],
        }
    )


def _result_frame(
    instances: list[KnapsackInstance],
    profits: np.ndarray,
    weights: np.ndarray,
    *,
    model_id: str,
    method: str,
    family: str,
    arm: str,
    run: int,
    master_seed: str,
    checkpoint: int,
    gene: str,
    permutation_index: int,
) -> pd.DataFrame:
    frame = _instance_frame(instances)
    frame["profit"] = np.asarray(profits, dtype=np.int64)
    frame["packed_weight"] = np.asarray(weights, dtype=np.int64)
    certified = frame["optimum"] >= 0
    frame["quality"] = np.nan
    frame["gap_ppm"] = np.nan
    frame.loc[certified, "quality"] = (
        frame.loc[certified, "profit"] / frame.loc[certified, "optimum"]
    )
    frame.loc[certified, "gap_ppm"] = 1e6 * (
        frame.loc[certified, "optimum"] - frame.loc[certified, "profit"]
    ) / frame.loc[certified, "optimum"]
    frame["exact"] = certified & (frame["profit"] == frame["optimum"])
    frame["feasible"] = frame["packed_weight"] <= frame["capacity"]
    if not frame["feasible"].all():
        raise AssertionError(f"{model_id} produced an infeasible solution")
    if (frame.loc[certified, "profit"] > frame.loc[certified, "optimum"]).any():
        raise AssertionError(f"{model_id} exceeded a certified optimum")
    frame.insert(0, "gene", gene)
    frame.insert(0, "checkpoint", int(checkpoint))
    frame.insert(0, "master_seed", str(master_seed))
    frame.insert(0, "run", int(run))
    frame.insert(0, "arm", arm)
    frame.insert(0, "family", family)
    frame.insert(0, "method", method)
    frame.insert(0, "model_id", model_id)
    frame["permutation_index"] = int(permutation_index)
    return frame[EVALUATION_COLUMNS]


def _gene_frames(
    instances: list[KnapsackInstance],
    specs: pd.DataFrame,
    *,
    permutation_index: int,
) -> Iterator[pd.DataFrame]:
    for arm, arm_specs in specs.groupby("arm", sort=False):
        evaluator = BatchEvaluator(instances, str(arm))
        cache: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for row in arm_specs.itertuples(index=False):
            gene = str(row.gene)
            if gene not in cache:
                profits, weights, _gaps = evaluator.evaluate(gene)
                cache[gene] = profits, weights
            profits, weights = cache[gene]
            family = str(row.family)
            method = str(arm) if family == "GEP" else family
            yield _result_frame(
                instances,
                profits,
                weights,
                model_id=str(row.model_id),
                method=method,
                family=family,
                arm=str(arm),
                run=int(row.run),
                master_seed=str(row.master_seed),
                checkpoint=int(row.checkpoint),
                gene=gene,
                permutation_index=permutation_index,
            )


def _baseline_frames(
    instances: list[KnapsackInstance],
    *,
    permutation_index: int,
) -> Iterator[pd.DataFrame]:
    baseline = evaluate_baselines(instances, permutation_index=permutation_index)
    for method, subset in baseline.groupby("method", sort=False):
        frame = subset.rename(columns={"method_family": "family"}).copy()
        frame["gene"] = ""
        frame["quality"] = np.nan
        certified = frame["optimum"] >= 0
        frame.loc[certified, "quality"] = (
            frame.loc[certified, "profit"] / frame.loc[certified, "optimum"]
        )
        yield frame[EVALUATION_COLUMNS]

    config = json.loads(
        (RESULTS_ROOT / "power_ranker_config_v2.json").read_text(encoding="utf-8")
    )
    power = evaluate_power_ranker(instances, config["alpha"], config["beta"])
    power["permutation_index"] = permutation_index
    power = power.rename(columns={"method_family": "family"})
    power["gene"] = f"P^{config['alpha']}/W^{config['beta']}"
    power["quality"] = np.nan
    certified = power["optimum"] >= 0
    power.loc[certified, "quality"] = (
        power.loc[certified, "profit"] / power.loc[certified, "optimum"]
    )
    yield power[EVALUATION_COLUMNS]


def _permuted_instances(
    instances: list[KnapsackInstance], seeds: dict[str, int]
) -> list[KnapsackInstance]:
    output = []
    for item in instances:
        permutation = np.random.default_rng(seeds[item.name]).permutation(item.n)
        output.append(
            replace(
                item,
                profits=item.profits[permutation].copy(),
                weights=item.weights[permutation].copy(),
            )
        )
    return output


def _record_file(path: Path, rows: int, kind: str) -> dict[str, object]:
    return {
        "kind": kind,
        "path": path.relative_to(RESULTS_ROOT).as_posix(),
        "rows": int(rows),
        "sha256": sha256_file(path),
    }


def evaluate_jooken() -> pd.DataFrame:
    """Evaluate frozen checkpoint genes and all row-order audit permutations."""

    verify_lock()
    partitions = ["id_test", "ood_n", "ood_c", "ood_nc", "unresolved"]
    instances = load_partitions(SPLIT_MANIFEST, partitions, JOOKEN_ARCHIVE)
    specs = _model_specs(final_only=False)
    files: list[dict[str, object]] = []

    def original_frames() -> Iterator[pd.DataFrame]:
        yield from _gene_frames(instances, specs, permutation_index=0)
        yield from _baseline_frames(instances, permutation_index=0)

    rows = atomic_csv_stream(original_frames(), JOOKEN_EVALUATIONS_PATH)
    expected_original = len(instances) * (len(specs) + 5)
    if rows != expected_original:
        raise AssertionError(
            f"Original-order evaluation rows differ: {rows} versus {expected_original}"
        )
    files.append(_record_file(JOOKEN_EVALUATIONS_PATH, rows, "jooken_original"))

    final_specs = _model_specs(final_only=True)
    permutations = pd.read_csv(
        RESULTS_ROOT / "permutations_v2.csv.gz", dtype={"seed": str}
    )
    wanted_names = {item.name for item in instances}
    permutations = permutations[permutations["name"].isin(wanted_names)]
    for index in range(1, ROW_PERMUTATIONS + 1):
        path = ROW_ORDER_ROOT / f"permutation_{index:02d}.csv.gz"
        if path.is_file():
            existing_rows = sum(
                len(chunk) for chunk in pd.read_csv(path, chunksize=100_000)
            )
            expected_rows = len(instances) * (len(final_specs) + 5)
            if existing_rows != expected_rows:
                raise AssertionError(
                    f"Existing row-order file is incomplete: {path} has "
                    f"{existing_rows}, expected {expected_rows}"
                )
            files.append(
                _record_file(path, existing_rows, "row_order_existing")
            )
            continue
        rows_for_index = permutations[permutations["permutation_index"] == index]
        seed_lookup = {
            str(row.name): int(row.seed) for row in rows_for_index.itertuples(index=False)
        }
        if set(seed_lookup) != wanted_names:
            raise AssertionError(f"Permutation {index} has incomplete seed coverage")
        permuted = _permuted_instances(instances, seed_lookup)

        def permutation_frames() -> Iterator[pd.DataFrame]:
            yield from _gene_frames(permuted, final_specs, permutation_index=index)
            yield from _baseline_frames(permuted, permutation_index=index)

        row_count = atomic_csv_stream(permutation_frames(), path)
        expected_rows = len(instances) * (len(final_specs) + 5)
        if row_count != expected_rows:
            raise AssertionError(
                f"Permutation {index} rows differ: {row_count} versus {expected_rows}"
            )
        files.append(_record_file(path, row_count, "row_order"))
    manifest = pd.DataFrame(files)
    atomic_csv(manifest, EVALUATION_MANIFEST_PATH)
    return manifest


def evaluate_pisinger() -> dict[str, object]:
    """Evaluate final frozen models on all retained certified Pisinger cases."""

    verify_lock()
    specs = _model_specs(final_only=True)

    def frames() -> Iterator[pd.DataFrame]:
        for member, instances in iter_retained_batches():
            print(f"transfer evaluation: {member} ({len(instances)} cases)", flush=True)
            yield from _gene_frames(instances, specs, permutation_index=0)
            yield from _baseline_frames(instances, permutation_index=0)

    rows = atomic_csv_stream(frames(), PISINGER_EVALUATIONS_PATH)
    transfer_manifest = pd.read_csv(PISINGER_MANIFEST)
    retained_cases = int(transfer_manifest["retained"].astype(bool).sum())
    expected = retained_cases * (len(specs) + 5)
    if rows != expected:
        raise AssertionError(f"Transfer rows differ: {rows} versus {expected}")
    return _record_file(PISINGER_EVALUATIONS_PATH, rows, "pisinger_transfer")


def evaluate_all() -> pd.DataFrame:
    jooken = evaluate_jooken()
    transfer = evaluate_pisinger()
    combined = pd.concat([jooken, pd.DataFrame([transfer])], ignore_index=True)
    atomic_csv(combined, EVALUATION_MANIFEST_PATH)
    return combined
