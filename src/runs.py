"""Resumable development and final-training runners for protocol V2."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from time import perf_counter
from typing import Callable, Iterable
import json
import os

import numpy as np
import pandas as pd

from .config import (
    AHDAS_CONFIG,
    ARM_ORDER,
    CHECKPOINTS,
    DEVELOPMENT_ROOT,
    JOOKEN_ARCHIVE,
    MAX_REQUESTS,
    PROJECT_ROOT,
    RESULTS_ROOT,
    RUNS_ROOT,
    SEEDS_MANIFEST,
    SELECTED_CONFIG_PATH,
    SPLIT_MANIFEST,
    SURVIVOR_RUNS,
)
from .dataset import KnapsackInstance, load_partitions
from .gep import (
    BatchEvaluator,
    SearchConfig,
    SearchOutcome,
    decode_gene,
    evolve_historical_ahdas,
    evolve_priority_formula,
    phenotype_key,
    random_gene_search,
    simplified_formula,
    to_infix,
)
from .io_utils import (
    atomic_csv,
    atomic_json,
    atomic_run_directory,
    canonical_json,
    validate_run_directory,
)
from .protocol import verify_lock
from .ranking import audit_ranking_equivalence


IRACE_ELITES_PATH = DEVELOPMENT_ROOT / "irace_elites_v2.csv"
SURVIVOR_RESULTS_PATH = DEVELOPMENT_ROOT / "tuning_results_v2.csv.gz"
SURVIVOR_SUMMARY_PATH = DEVELOPMENT_ROOT / "survivor_summary_v2.csv"
MODELS_PATH = RESULTS_ROOT / "models_v2.csv.gz"
CHECKPOINTS_PATH = RESULTS_ROOT / "checkpoints_v2.csv.gz"
HISTORIES_PATH = RESULTS_ROOT / "histories_v2.csv.gz"
EXPRESSIONS_PATH = RESULTS_ROOT / "expressions_v2.csv"
REPRESENTATIVES_PATH = RESULTS_ROOT / "representative_expressions_v2.csv"

PARAMETER_COLUMNS = (
    "head_length",
    "population_size",
    "tournament_size",
    "elite_fraction",
    "crossover_rate",
    "expected_mutations",
)


def _limit_threads() -> None:
    for variable in (
        "NUMBA_NUM_THREADS",
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ):
        os.environ.setdefault(variable, "1")


def _csv_text(frame: pd.DataFrame) -> str:
    return frame.to_csv(index=False, lineterminator="\n")


def _read_seed_rows(phase: str) -> list[dict[str, int | str]]:
    frame = pd.read_csv(SEEDS_MANIFEST, dtype=str)
    frame = frame[frame["phase"] == phase].copy()
    frame["run"] = frame["run"].astype(int)
    frame = frame.sort_values("run", kind="stable")
    if frame.empty or frame["run"].duplicated().any():
        raise AssertionError(f"Invalid {phase} seed schedule")
    return frame.to_dict("records")


def _group_standard_error(
    instances: list[KnapsackInstance], gaps: np.ndarray
) -> tuple[float, int]:
    frame = pd.DataFrame(
        {
            "group_id": [item.group_id for item in instances],
            "gap_ppm": np.asarray(gaps, dtype=np.float64),
        }
    )
    grouped = frame.groupby("group_id", sort=False)["gap_ppm"].mean()
    if len(grouped) < 2:
        return 0.0, len(grouped)
    return float(grouped.std(ddof=1) / np.sqrt(len(grouped))), len(grouped)


def _decorate_trace(
    rows: Iterable[dict[str, object]], metadata: dict[str, object]
) -> pd.DataFrame:
    values = []
    prefix = {
        key: metadata[key]
        for key in (
            "phase",
            "family",
            "model_id",
            "candidate_id",
            "arm",
            "run",
            "master_seed",
        )
        if key in metadata
    }
    for row in rows:
        values.append({**prefix, **row})
    return pd.DataFrame(values)


def _run_directory(
    phase: str, family: str, arm: str, run: int, candidate_id: str = ""
) -> Path:
    if phase == "survivor":
        return RUNS_ROOT / phase / candidate_id / arm / f"run_{run:03d}"
    return RUNS_ROOT / phase / family.lower() / arm / f"run_{run:03d}"


def _run_search(
    *,
    phase: str,
    family: str,
    arm: str,
    run: int,
    master_seed: int,
    config: SearchConfig,
    training: list[KnapsackInstance],
    train_evaluator: BatchEvaluator,
    validation_evaluator: BatchEvaluator | None = None,
    candidate_id: str = "",
) -> dict[str, object]:
    destination = _run_directory(phase, family, arm, run, candidate_id)
    if destination.exists():
        validate_run_directory(destination)
        existing = json.loads((destination / "meta.json").read_text(encoding="utf-8"))
        expected = {
            "phase": phase,
            "family": family,
            "candidate_id": candidate_id,
            "arm": arm,
            "run": run,
            "master_seed": str(master_seed),
            **config.as_dict(),
        }
        mismatches = {
            key: (existing.get(key), value)
            for key, value in expected.items()
            if existing.get(key) != value
        }
        if mismatches:
            raise AssertionError(
                f"Completed run signature differs at {destination}: {mismatches}"
            )
        return existing

    started = perf_counter()
    if family == "GEP":
        outcome = evolve_priority_formula(
            train_evaluator.gap_vector,
            len(training),
            arm,
            master_seed,
            config,
            checkpoints=CHECKPOINTS,
        )
    elif family == "RANDOM":
        outcome = random_gene_search(
            train_evaluator.gap_vector,
            len(training),
            arm,
            master_seed,
            config,
            checkpoints=CHECKPOINTS,
        )
    elif family == "AHDAS_BASE":
        if arm != "BASE":
            raise ValueError("AHDAS_BASE is defined only for BASE terminals")
        outcome = evolve_historical_ahdas(
            train_evaluator.gap_vector,
            len(training),
            master_seed,
            config,
            checkpoints=CHECKPOINTS,
        )
    else:
        raise ValueError(f"Unknown search family {family}")

    train_gaps = train_evaluator.gap_vector(outcome.gene)
    train_se, train_groups = _group_standard_error(training, train_gaps)
    validation_mean: float | None = None
    validation_se: float | None = None
    validation_groups = 0
    if validation_evaluator is not None:
        validation_gaps = validation_evaluator.gap_vector(outcome.gene)
        validation_mean = float(validation_gaps.mean())
        validation_instances = list(validation_evaluator.instances)
        validation_se, validation_groups = _group_standard_error(
            validation_instances, validation_gaps
        )
    tree, active = decode_gene(outcome.gene, arm)
    model_id = (
        f"SURVIVOR-{candidate_id}-{arm}-{run:03d}"
        if phase == "survivor"
        else f"{family}-{arm}-{run:03d}"
    )
    metadata: dict[str, object] = {
        "phase": phase,
        "family": family,
        "model_id": model_id,
        "candidate_id": candidate_id,
        "arm": arm,
        "run": run,
        "master_seed": str(master_seed),
        "gene": outcome.gene,
        "phenotype": phenotype_key(outcome.gene, arm),
        "orf_length": active,
        "expression": to_infix(tree),
        "simplified": simplified_formula(tree),
        "train_mean_gap_ppm": float(train_gaps.mean()),
        "train_group_se_ppm": train_se,
        "train_group_count": train_groups,
        "validation_mean_gap_ppm": validation_mean,
        "validation_group_se_ppm": validation_se,
        "validation_group_count": validation_groups,
        "raw_requests": outcome.raw_requests,
        "unique_orfs": outcome.unique_orfs,
        "candidate_instance_evaluations": outcome.candidate_instance_evaluations,
        "elapsed_seconds": perf_counter() - started,
        **config.as_dict(),
    }
    checkpoint_frame = _decorate_trace(outcome.checkpoints, metadata)
    history_frame = _decorate_trace(outcome.generations, metadata)
    files = {
        "meta.json": canonical_json(metadata),
        "model.csv": _csv_text(pd.DataFrame([metadata])),
        "checkpoints.csv": _csv_text(checkpoint_frame),
        "history.csv": _csv_text(history_frame),
    }
    atomic_run_directory(destination, files)
    print(
        f"complete {phase}/{family}/{candidate_id or '-'} {arm} run {run}: "
        f"train={metadata['train_mean_gap_ppm']:.3f} ppm",
        flush=True,
    )
    return metadata


def _irace_candidates() -> list[dict[str, object]]:
    if not IRACE_ELITES_PATH.is_file():
        raise FileNotFoundError(
            f"Missing {IRACE_ELITES_PATH}; run `make tune` before survivor checks"
        )
    frame = pd.read_csv(IRACE_ELITES_PATH)
    missing = set(PARAMETER_COLUMNS) - set(frame)
    if missing:
        raise AssertionError(f"irace elite table lacks {sorted(missing)}")
    frame = frame.drop_duplicates(list(PARAMETER_COLUMNS), keep="first").head(5)
    if len(frame) != 5:
        raise AssertionError(f"Expected five distinct irace survivors, found {len(frame)}")
    candidates: list[dict[str, object]] = []
    for rank, row in enumerate(frame.itertuples(index=False), start=1):
        values = row._asdict()
        parameters = {
            "head_length": int(float(values["head_length"])),
            "population_size": int(float(values["population_size"])),
            "tournament_size": int(float(values["tournament_size"])),
            "elite_fraction": float(values["elite_fraction"]),
            "crossover_rate": float(values["crossover_rate"]),
            "expected_mutations": int(float(values["expected_mutations"])),
            "budget": MAX_REQUESTS,
        }
        candidates.append(
            {
                "candidate_id": f"irace_{rank:02d}",
                "irace_order": rank,
                "parameters": parameters,
            }
        )
    return candidates


def _survivor_arm(arm: str, candidates: list[dict[str, object]]) -> int:
    _limit_threads()
    train = load_partitions(SPLIT_MANIFEST, ["train"], JOOKEN_ARCHIVE)
    validation = load_partitions(SPLIT_MANIFEST, ["validation"], JOOKEN_ARCHIVE)
    train_evaluator = BatchEvaluator(train, arm)
    validation_evaluator = BatchEvaluator(validation, arm)
    seeds = _read_seed_rows("survivor")
    completed = 0
    for candidate in candidates:
        config = SearchConfig.from_dict(candidate["parameters"])
        for seed_row in seeds:
            _run_search(
                phase="survivor",
                family="GEP",
                arm=arm,
                run=int(seed_row["run"]),
                master_seed=int(seed_row["master_seed"]),
                config=config,
                training=train,
                train_evaluator=train_evaluator,
                validation_evaluator=validation_evaluator,
                candidate_id=str(candidate["candidate_id"]),
            )
            completed += 1
    return completed


def _parallel_arms(
    function: Callable[..., int],
    *,
    workers: int,
    extra_args: tuple[object, ...] = (),
) -> None:
    if workers < 1:
        raise ValueError("workers must be positive")
    if workers == 1:
        for arm in ARM_ORDER:
            function(arm, *extra_args)
        return
    with ProcessPoolExecutor(max_workers=min(workers, len(ARM_ORDER))) as executor:
        futures = {
            executor.submit(function, arm, *extra_args): arm for arm in ARM_ORDER
        }
        for future in as_completed(futures):
            arm = futures[future]
            count = future.result()
            print(f"arm {arm} finished {count} runs", flush=True)


def _collect_meta(root: Path) -> pd.DataFrame:
    records = []
    for path in sorted(root.rglob("meta.json")):
        validate_run_directory(path.parent)
        records.append(json.loads(path.read_text(encoding="utf-8")))
    if not records:
        raise FileNotFoundError(f"No completed run metadata below {root}")
    return pd.DataFrame(records)


def run_survivors(workers: int = 4) -> dict[str, object]:
    candidates = _irace_candidates()
    _parallel_arms(_survivor_arm, workers=workers, extra_args=(candidates,))
    frame = _collect_meta(RUNS_ROOT / "survivor")
    expected = len(candidates) * len(ARM_ORDER) * SURVIVOR_RUNS
    keys = ["candidate_id", "arm", "run"]
    if len(frame) != expected or frame.duplicated(keys).any():
        raise AssertionError(
            f"Survivor run matrix is incomplete: expected {expected}, found {len(frame)}"
        )
    frame["validation_rank"] = frame.groupby(["arm", "run"])[
        "validation_mean_gap_ppm"
    ].rank(method="average", ascending=True)
    summaries = []
    parameter_lookup = {str(item["candidate_id"]): item for item in candidates}
    for candidate_id, subset in frame.groupby("candidate_id", sort=False):
        arm_means = subset.groupby("arm")["validation_mean_gap_ppm"].mean()
        row: dict[str, object] = {
            "candidate_id": candidate_id,
            "mean_validation_rank": float(subset["validation_rank"].mean()),
            "pooled_validation_mean_gap_ppm": float(
                subset["validation_mean_gap_ppm"].mean()
            ),
            "worst_arm_validation_mean_gap_ppm": float(arm_means.max()),
        }
        for arm in ARM_ORDER:
            row[f"{arm}_validation_mean_gap_ppm"] = float(arm_means.loc[arm])
        row.update(parameter_lookup[str(candidate_id)]["parameters"])
        summaries.append(row)
    summary = pd.DataFrame(summaries).sort_values(
        [
            "mean_validation_rank",
            "pooled_validation_mean_gap_ppm",
            "worst_arm_validation_mean_gap_ppm",
            *PARAMETER_COLUMNS,
        ],
        kind="stable",
    )
    summary["selection_order"] = np.arange(1, len(summary) + 1)
    winner = summary.iloc[0].to_dict()
    selected = {
        "candidate_id": winner["candidate_id"],
        "selection_rule": (
            "mean paired validation rank; pooled validation mean gap; "
            "worst-arm validation mean gap; ordered parameter tuple"
        ),
        "parameters": {
            key: (
                int(winner[key])
                if key in {
                    "head_length",
                    "population_size",
                    "tournament_size",
                    "expected_mutations",
                    "budget",
                }
                else float(winner[key])
            )
            for key in (*PARAMETER_COLUMNS, "budget")
        },
        "development_evidence": {
            "survivor_configurations": 5,
            "paired_seeds": SURVIVOR_RUNS,
            "terminal_arms": list(ARM_ORDER),
            "mean_validation_rank": float(winner["mean_validation_rank"]),
            "pooled_validation_mean_gap_ppm": float(
                winner["pooled_validation_mean_gap_ppm"]
            ),
            "worst_arm_validation_mean_gap_ppm": float(
                winner["worst_arm_validation_mean_gap_ppm"]
            ),
        },
    }
    atomic_csv(frame.sort_values(keys, kind="stable"), SURVIVOR_RESULTS_PATH)
    atomic_csv(summary, SURVIVOR_SUMMARY_PATH)
    atomic_json(selected, SELECTED_CONFIG_PATH)
    return selected


def _selected_config() -> SearchConfig:
    if not SELECTED_CONFIG_PATH.is_file():
        raise FileNotFoundError("Survivor selection has not produced selected_config_v2.json")
    payload = json.loads(SELECTED_CONFIG_PATH.read_text(encoding="utf-8"))
    return SearchConfig.from_dict(payload["parameters"])


def _final_arm(arm: str, selected_values: dict[str, object]) -> int:
    _limit_threads()
    training = load_partitions(
        SPLIT_MANIFEST, ["train", "validation"], JOOKEN_ARCHIVE
    )
    evaluator = BatchEvaluator(training, arm)
    config = SearchConfig.from_dict(selected_values)
    seeds = _read_seed_rows("final")
    completed = 0
    for family in ("GEP", "RANDOM"):
        for seed_row in seeds:
            _run_search(
                phase="final",
                family=family,
                arm=arm,
                run=int(seed_row["run"]),
                master_seed=int(seed_row["master_seed"]),
                config=config,
                training=training,
                train_evaluator=evaluator,
            )
            completed += 1
    return completed


def _historical_final() -> int:
    _limit_threads()
    training = load_partitions(
        SPLIT_MANIFEST, ["train", "validation"], JOOKEN_ARCHIVE
    )
    evaluator = BatchEvaluator(training, "BASE")
    config = SearchConfig.from_dict(AHDAS_CONFIG)
    seeds = _read_seed_rows("final")
    for seed_row in seeds:
        _run_search(
            phase="final",
            family="AHDAS_BASE",
            arm="BASE",
            run=int(seed_row["run"]),
            master_seed=int(seed_row["master_seed"]),
            config=config,
            training=training,
            train_evaluator=evaluator,
        )
    return len(seeds)


def _merge_trace(filename: str) -> pd.DataFrame:
    frames = []
    for path in sorted((RUNS_ROOT / "final").rglob(filename)):
        validate_run_directory(path.parent)
        try:
            frame = pd.read_csv(path)
        except pd.errors.EmptyDataError:
            continue
        if not frame.empty:
            frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def merge_final_runs() -> pd.DataFrame:
    models = _collect_meta(RUNS_ROOT / "final")
    expected = 75 * (len(ARM_ORDER) * 2 + 1)
    keys = ["family", "arm", "run"]
    if len(models) != expected or models.duplicated(keys).any():
        raise AssertionError(
            f"Final model matrix is incomplete: expected {expected}, found {len(models)}"
        )
    family_counts = models.groupby("family").size().to_dict()
    if family_counts != {"AHDAS_BASE": 75, "GEP": 300, "RANDOM": 300}:
        raise AssertionError(f"Unexpected final family counts: {family_counts}")
    models = models.sort_values(keys, kind="stable").reset_index(drop=True)
    checkpoints = _merge_trace("checkpoints.csv")
    histories = _merge_trace("history.csv")
    atomic_csv(models, MODELS_PATH)
    atomic_csv(checkpoints, CHECKPOINTS_PATH)
    atomic_csv(histories, HISTORIES_PATH)

    expressions = models[
        [
            "family",
            "arm",
            "run",
            "master_seed",
            "gene",
            "phenotype",
            "orf_length",
            "expression",
            "simplified",
            "train_mean_gap_ppm",
            "train_group_se_ppm",
        ]
    ].copy()
    atomic_csv(expressions, EXPRESSIONS_PATH)

    representatives = []
    for arm in ARM_ORDER:
        subset = models[(models["family"] == "GEP") & (models["arm"] == arm)].copy()
        best = subset.sort_values(
            ["train_mean_gap_ppm", "run"], kind="stable"
        ).iloc[0]
        threshold = float(best["train_mean_gap_ppm"] + best["train_group_se_ppm"])
        eligible = subset[subset["train_mean_gap_ppm"] <= threshold].copy()
        chosen = eligible.sort_values(
            ["orf_length", "simplified", "run"], kind="stable"
        ).iloc[0]
        representatives.append(
            {
                "arm": arm,
                "model_id": chosen["model_id"],
                "run": int(chosen["run"]),
                "gene": chosen["gene"],
                "phenotype": chosen["phenotype"],
                "expression": chosen["expression"],
                "simplified": chosen["simplified"],
                "orf_length": int(chosen["orf_length"]),
                "train_mean_gap_ppm": float(chosen["train_mean_gap_ppm"]),
                "eligibility_threshold_ppm": threshold,
                "eligible_models": len(eligible),
                "selection_rule": (
                    "shortest ORF within one best-model group SE; then simplified "
                    "expression and run index"
                ),
            }
        )
    atomic_csv(pd.DataFrame(representatives), REPRESENTATIVES_PATH)
    audit_ranking_equivalence(models)
    return models


def run_final_training(workers: int = 4) -> pd.DataFrame:
    verify_lock()
    selected = _selected_config().as_dict()
    _parallel_arms(_final_arm, workers=workers, extra_args=(selected,))
    _historical_final()
    return merge_final_runs()
