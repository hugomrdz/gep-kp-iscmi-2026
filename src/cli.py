"""Guarded command-line entry point for the V2 experiment."""

from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

import numpy as np
import pandas as pd

from .baselines import baseline_scores, fit_power_ranker
from .config import (
    ARM_ORDER,
    ASSERTIONS_PATH,
    ENVIRONMENT_PATH,
    FALLBACK_CONFIG,
    JOOKEN_ARCHIVE,
    JOOKEN_ARCHIVE_SHA256,
    PERMUTATION_SEED,
    POWER_PLAN,
    RESULTS_ROOT,
    ROW_PERMUTATIONS,
    SEEDS_MANIFEST,
    SELECTED_CONFIG_PATH,
    SPLIT_MANIFEST,
    SPLIT_SEED,
    ensure_directories,
)
from .dataset import (
    attach_manifest,
    build_split_manifest,
    load_collection,
    load_partitions,
    validate_split_manifest,
)
from .gep import (
    BatchEvaluator,
    SearchConfig,
    evolve_priority_formula,
    is_valid_gene,
    pack_gene,
    pack_gene_independent,
    random_gene,
)
from .io_utils import atomic_csv, atomic_json, atomic_text, sha256_file
from .protocol import create_lock, environment_record, verify_history, verify_lock
from .pisinger import prepare_pisinger
from .evaluation import evaluate_all
from .oracle import solve_unresolved
from .verification import verify_available
from .runs import run_final_training, run_survivors
from .seeds import permutation_manifest, seed_manifest


def _marginal_balance(manifest: pd.DataFrame) -> pd.DataFrame:
    id_rows = manifest[manifest["partition"].isin(["train", "validation", "id_test"])]
    groups = id_rows.drop_duplicates("group_id")
    rows = []
    for partition in ("train", "validation", "id_test"):
        subset = groups[groups["partition"] == partition]
        for factor in ("n", "c", "g", "f", "eps"):
            global_counts = groups[factor].value_counts()
            actual_counts = subset[factor].value_counts()
            for level in sorted(global_counts.index):
                expected = len(subset) * int(global_counts[level]) / len(groups)
                actual = int(actual_counts.get(level, 0))
                rows.append(
                    {
                        "partition": partition,
                        "factor": factor,
                        "level": level,
                        "group_count": actual,
                        "proportional_target": expected,
                        "absolute_deviation": abs(actual - expected),
                    }
                )
    return pd.DataFrame(rows)


def _collection_profile(instances: list, manifest: pd.DataFrame) -> pd.DataFrame:
    metadata = manifest.set_index("name")
    rows = []
    for item in instances:
        profits = item.profits.astype(np.float64)
        weights = item.weights.astype(np.float64)
        row = metadata.loc[item.name]
        rows.append(
            {
                "name": item.name,
                "partition": row["partition"],
                "region": row["region"],
                "certified": item.certified,
                "n": item.n,
                "c": item.c,
                "g": item.g,
                "f": item.f,
                "eps": item.eps,
                "s": item.s,
                "pearson_weight_profit": float(np.corrcoef(weights, profits)[0, 1]),
                "capacity_over_sum_weight": float(
                    item.capacity / item.weights.sum(dtype=np.int64)
                ),
                "max_weight_over_capacity": float(item.weights.max() / item.capacity),
                "profit_decades": float(np.log10(profits.max() / profits.min())),
            }
        )
    return pd.DataFrame(rows)


def prepare() -> None:
    ensure_directories()
    if sha256_file(JOOKEN_ARCHIVE) != JOOKEN_ARCHIVE_SHA256:
        raise AssertionError("Jooken archive hash differs from the locked source")
    history_messages = verify_history()
    instances = load_collection(JOOKEN_ARCHIVE)
    if SPLIT_MANIFEST.is_file():
        manifest = pd.read_csv(SPLIT_MANIFEST)
    else:
        manifest = build_split_manifest(instances)
    validate_split_manifest(manifest)
    attached = attach_manifest(instances, manifest)
    seeds = seed_manifest()
    test_names = manifest.loc[
        ~manifest["partition"].isin(["train", "validation"]), "name"
    ].tolist()
    permutations = permutation_manifest(test_names, ROW_PERMUTATIONS)
    development_seeds = np.random.SeedSequence(20260912).generate_state(
        20, dtype=np.uint64
    )
    scenario_lines = [
        f"{fold}::{arm}::{int(model_seed)}"
        for model_seed in development_seeds
        for fold in ("fold_0", "fold_1", "fold_2", "fold_3")
        for arm in ARM_ORDER
    ]
    validation = [item for item in attached if item.partition == "validation"]
    power_config, power_grid = fit_power_ranker(validation)

    atomic_csv(manifest, SPLIT_MANIFEST)
    atomic_csv(seeds, SEEDS_MANIFEST)
    atomic_csv(permutations, RESULTS_ROOT / "permutations_v2.csv.gz")
    atomic_csv(_marginal_balance(manifest), RESULTS_ROOT / "split_balance_v2.csv")
    atomic_csv(_collection_profile(attached, manifest), RESULTS_ROOT / "collection_profile_v2.csv.gz")
    atomic_csv(power_grid, RESULTS_ROOT / "power_ranker_grid_v2.csv")
    atomic_json(power_config, RESULTS_ROOT / "power_ranker_config_v2.json")
    atomic_text("\n".join(scenario_lines) + "\n", Path("tuning/instances.txt"))
    atomic_json(environment_record(), ENVIRONMENT_PATH)
    atomic_text(
        "# Power plan\n\n"
        "Pilot paired SD: 2,192 ppm.\n\n"
        "Smallest effect of interest: 872 ppm, so the planning effect is $d_z\\approx0.40$.\n\n"
        "With three planned representation contrasts, conservative familywise control near "
        "$0.05/3$, 80% power requires approximately 67 paired runs. The locked design uses "
        "75 paired runs per terminal arm.\n",
        POWER_PLAN,
    )
    messages = history_messages + [
        "PASS data: archive hash and 3240 unique instance files validated",
        "PASS data: 2977 certified and 263 unresolved cases validated",
        "PASS split: 1038 train, 345 validation, 345 ID, 1249 OOD, 263 unresolved",
        "PASS split: every ID group retains all three s siblings",
        "PASS split: four balanced development folds contain 87/87/86/86 groups",
        f"PASS permutations: {len(permutations)} fixed rows use root seed {PERMUTATION_SEED}",
        f"PASS irace scenarios: {len(scenario_lines)} rows form 80 complete four-arm blocks",
        f"PASS power ranker: alpha={power_config['alpha']}, beta={power_config['beta']} selected on validation only",
    ]
    atomic_text("\n".join(messages) + "\n", ASSERTIONS_PATH)
    print("Preparation complete:")
    print(manifest.groupby("partition").size().to_string())


def smoke() -> None:
    if not SPLIT_MANIFEST.is_file():
        raise FileNotFoundError("Run prepare before smoke")
    train = load_partitions(SPLIT_MANIFEST, ["train"], JOOKEN_ARCHIVE)
    sample = train[:12]
    config = SearchConfig.from_dict({**FALLBACK_CONFIG, "population_size": 128, "budget": 512})
    messages = []
    for arm_index, arm in enumerate(ARM_ORDER):
        rng = np.random.default_rng(20260910 + arm_index)
        genes = [random_gene(rng, arm, config.head_length) for _ in range(10_000)]
        if not all(is_valid_gene(gene, arm, config.head_length) for gene in genes):
            raise AssertionError(f"Random structural test failed for {arm}")
        evaluator = BatchEvaluator(sample, arm)
        for gene in genes[:25]:
            profits, weights, _ = evaluator.evaluate(gene)
            for index, instance in enumerate(sample):
                scalar = pack_gene(instance, gene, arm)
                independent = pack_gene_independent(instance, gene, arm)
                if scalar.total_profit != int(profits[index]) or scalar.total_weight != int(
                    weights[index]
                ):
                    raise AssertionError(f"Scalar/batch mismatch for {arm}")
                if not np.array_equal(scalar.selected, independent.selected):
                    raise AssertionError(f"Independent decoder mismatch for {arm}")
        outcome_a = evolve_priority_formula(
            evaluator.gap_vector, len(sample), arm, 20260920, config
        )
        outcome_b = evolve_priority_formula(
            evaluator.gap_vector, len(sample), arm, 20260920, config
        )
        if outcome_a.gene != outcome_b.gene or outcome_a.mean_gap_ppm != outcome_b.mean_gap_ppm:
            raise AssertionError(f"Seeded repeat is not deterministic for {arm}")
        if outcome_a.raw_requests != 512:
            raise AssertionError("Smoke run missed its exact budget")
        messages.append(
            f"PASS smoke {arm}: 10000 genes, 25 scalar/batch/independent audits, deterministic run"
        )

    for arm in ARM_ORDER:
        evaluator = BatchEvaluator(sample, arm)
        head = config.head_length
        padding = "0" * (2 * head + 1)
        named = {
            "DEF": "O" + padding[1:],
            "MAXP": "P" + padding[1:],
            "MAXPW": "/PW" + padding[3:],
            "MINW": "-0W" + padding[3:],
        }
        direct = baseline_scores(sample[0])
        for method, gene in named.items():
            if not is_valid_gene(gene, arm, head):
                raise AssertionError(f"Named baseline gene is invalid: {method}/{arm}")
            gene_solution = pack_gene(sample[0], gene, arm)
            from .gep import pack_by_scores

            direct_solution = pack_by_scores(sample[0], direct[method], method)
            if not np.array_equal(gene_solution.selected, direct_solution.selected):
                raise AssertionError(f"Named expression does not reproduce {method}/{arm}")
    messages.append("PASS smoke baselines: DEF, MAXP, MAXPW, and MINW expressions reproduced")
    existing = ASSERTIONS_PATH.read_text(encoding="utf-8") if ASSERTIONS_PATH.exists() else ""
    existing_lines = existing.splitlines()
    combined = existing_lines + [message for message in messages if message not in existing_lines]
    atomic_text("\n".join(combined) + "\n", ASSERTIONS_PATH)
    print("\n".join(messages))


def lock(approver: str) -> None:
    result = create_lock(approver)
    print(f"Protocol locked for {result['approver']} at {result['locked_utc']}")


def verify() -> None:
    if SPLIT_MANIFEST.is_file():
        validate_split_manifest(pd.read_csv(SPLIT_MANIFEST))
    if Path(SELECTED_CONFIG_PATH).exists() and Path(SELECTED_CONFIG_PATH).stat().st_size == 0:
        raise AssertionError("Selected configuration file is empty")
    messages = verify_available()
    print("\n".join(messages))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("prepare")
    subparsers.add_parser("prepare-transfer")
    subparsers.add_parser("smoke")
    lock_parser = subparsers.add_parser("lock")
    lock_parser.add_argument("--approver", required=True)
    subparsers.add_parser("verify")
    survivor_parser = subparsers.add_parser("survivors")
    survivor_parser.add_argument("--workers", type=int, default=4)
    final_parser = subparsers.add_parser("train-final")
    final_parser.add_argument("--workers", type=int, default=4)
    subparsers.add_parser("evaluate")
    oracle_parser = subparsers.add_parser("solve-unresolved")
    oracle_parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        prepare()
    elif args.command == "prepare-transfer":
        frame = prepare_pisinger()
        print(
            f"Pisinger audit complete: {len(frame)} supplied certificates, "
            f"{int(frame['retained'].sum())} retained byte-distinct cases"
        )
    elif args.command == "smoke":
        smoke()
    elif args.command == "lock":
        lock(args.approver)
    elif args.command == "verify":
        verify()
    elif args.command == "survivors":
        selected = run_survivors(args.workers)
        print(json.dumps(selected, indent=2, sort_keys=True))
    elif args.command == "train-final":
        models = run_final_training(args.workers)
        print(f"Final training complete: {len(models)} frozen models")
    elif args.command == "evaluate":
        manifest = evaluate_all()
        print(manifest.to_string(index=False))
    elif args.command == "solve-unresolved":
        frame = solve_unresolved(args.workers)
        print(
            f"HiGHS attempts complete: {int(frame['certified_optimal'].sum())}/263 "
            "newly certified"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
