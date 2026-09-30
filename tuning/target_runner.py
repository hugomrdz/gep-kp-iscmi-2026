#!/usr/bin/env python3
"""External irace target: train on one blocked fold and score full validation."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
import argparse
import os
import sys

import numpy as np
import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
os.environ.setdefault("NUMBA_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

from src.config import JOOKEN_ARCHIVE, SPLIT_MANIFEST, TUNING_REQUESTS  # noqa: E402
from src.dataset import load_manifest_rows, validate_split_manifest  # noqa: E402
from src.gep import BatchEvaluator, SearchConfig, evolve_priority_formula  # noqa: E402
from src.io_utils import atomic_json  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("configuration_id")
    parser.add_argument("instance_id")
    parser.add_argument("irace_seed")
    parser.add_argument("scenario")
    parser.add_argument("--head-length", type=int, required=True)
    parser.add_argument("--population-size", type=int, required=True)
    parser.add_argument("--tournament-size", type=int, required=True)
    parser.add_argument("--elite-fraction", type=float, required=True)
    parser.add_argument("--crossover-rate", type=float, required=True)
    parser.add_argument("--expected-mutations", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fold, arm, encoded_seed = args.scenario.split("::")
    model_seed = int(encoded_seed)
    manifest = pd.read_csv(SPLIT_MANIFEST)
    validate_split_manifest(manifest)
    train_rows = manifest[(manifest.partition == "train") & (manifest.fold == fold)]
    validation_rows = manifest[manifest.partition == "validation"]
    train = load_manifest_rows(train_rows, JOOKEN_ARCHIVE)
    validation = load_manifest_rows(validation_rows, JOOKEN_ARCHIVE)
    config = SearchConfig(
        head_length=args.head_length,
        population_size=args.population_size,
        tournament_size=args.tournament_size,
        elite_fraction=args.elite_fraction,
        crossover_rate=args.crossover_rate,
        expected_mutations=args.expected_mutations,
        budget=TUNING_REQUESTS,
    )
    started = perf_counter()
    train_evaluator = BatchEvaluator(train, arm)
    outcome = evolve_priority_formula(
        train_evaluator.gap_vector,
        len(train),
        arm,
        model_seed,
        config,
        checkpoints=(TUNING_REQUESTS,),
    )
    validation_evaluator = BatchEvaluator(validation, arm)
    _profits, _weights, gaps = validation_evaluator.evaluate(outcome.gene)
    cost = float(np.mean(gaps))
    elapsed = perf_counter() - started
    result = {
        "configuration_id": args.configuration_id,
        "instance_id": args.instance_id,
        "irace_seed": args.irace_seed,
        "scenario": args.scenario,
        "fold": fold,
        "arm": arm,
        "model_seed": str(model_seed),
        "validation_mean_gap_ppm": cost,
        "train_mean_gap_ppm": outcome.mean_gap_ppm,
        "gene": outcome.gene,
        "elapsed_seconds": elapsed,
        **config.as_dict(),
    }
    target_dir = PROJECT / "tuning" / "work" / "target-results"
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_scenario = args.scenario.replace("::", "_")
    atomic_json(
        result,
        target_dir
        / f"config_{args.configuration_id}_instance_{args.instance_id}_{safe_scenario}.json",
    )
    print(f"{cost:.12f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
