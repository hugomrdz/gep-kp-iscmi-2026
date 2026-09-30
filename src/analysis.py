"""Protocol-locked confirmatory analysis and figure-source tables."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable
import json
import warnings

import numpy as np
import pandas as pd
from scipy import stats

from .config import (
    ARM_ORDER,
    BASELINE_ORDER,
    BOOTSTRAP_REPLICATES,
    BOOTSTRAP_SEED,
    CONFIRMATORY_ROOT,
    HEADLINE_ORDER,
    MAX_REQUESTS,
    RESULTS_ROOT,
    SESOI_PPM,
    TRANSFER_ROOT,
)
from .evaluation import JOOKEN_EVALUATIONS_PATH, PISINGER_EVALUATIONS_PATH, ROW_ORDER_ROOT
from .io_utils import atomic_csv, atomic_json
from .protocol import verify_lock
from .runs import CHECKPOINTS_PATH, MODELS_PATH
from .oracle import ORACLE_PATH


FIGURE_DATA_ROOT = RESULTS_ROOT / "figure_data"
HEADLINE_PATH = FIGURE_DATA_ROOT / "headline_bar_v2.csv"
BOOTSTRAP_PATH = CONFIRMATORY_ROOT / "headline_bootstrap_v2.csv.gz"
METHOD_SUMMARY_PATH = CONFIRMATORY_ROOT / "method_summary_v2.csv"
RUN_SUMMARY_PATH = CONFIRMATORY_ROOT / "run_summary_v2.csv.gz"
CONTRASTS_PATH = CONFIRMATORY_ROOT / "contrasts_v2.csv"
FRIEDMAN_PATH = CONFIRMATORY_ROOT / "friedman_v2.csv"
POSTHOC_PATH = CONFIRMATORY_ROOT / "posthoc_v2.csv"
MIXED_MODEL_PATH = CONFIRMATORY_ROOT / "mixed_model_sensitivity_v2.csv"
ANYTIME_PATH = FIGURE_DATA_ROOT / "anytime_v2.csv"
GENERALIZATION_PATH = FIGURE_DATA_ROOT / "generalization_v2.csv"
ROW_ORDER_PATH = CONFIRMATORY_ROOT / "row_order_summary_v2.csv"
TRANSFER_SUMMARY_PATH = TRANSFER_ROOT / "transfer_summary_v2.csv"
UNRESOLVED_SUMMARY_PATH = CONFIRMATORY_ROOT / "unresolved_summary_v2.csv"
UNRESOLVED_CASES_PATH = CONFIRMATORY_ROOT / "unresolved_cases_v2.csv.gz"
CONTROL_SUMMARY_PATH = CONFIRMATORY_ROOT / "control_summary_v2.csv"
CONTROL_CONTRASTS_PATH = CONFIRMATORY_ROOT / "control_contrasts_v2.csv"
STATISTICS_PATH = CONFIRMATORY_ROOT / "statistics_v2.csv"
SUMMARY_JSON_PATH = CONFIRMATORY_ROOT / "summary_v2.json"

READ_COLUMNS = [
    "model_id",
    "method",
    "family",
    "arm",
    "run",
    "master_seed",
    "checkpoint",
    "name",
    "group_id",
    "partition",
    "region",
    "profit",
    "optimum",
    "gap_ppm",
    "exact",
]


def _label(frame: pd.DataFrame) -> pd.Series:
    return pd.Series(
        np.where(frame["family"].eq("GEP"), frame["arm"], frame["method"]),
        index=frame.index,
        dtype="object",
    )


def _stream_filter(
    path: Path,
    predicate: Callable[[pd.DataFrame], pd.Series],
    *,
    usecols: Iterable[str] = READ_COLUMNS,
    chunksize: int = 200_000,
) -> pd.DataFrame:
    frames = []
    for chunk in pd.read_csv(
        path,
        usecols=list(usecols),
        chunksize=chunksize,
        dtype={"master_seed": str},
    ):
        subset = chunk.loc[predicate(chunk)].copy()
        if not subset.empty:
            frames.append(subset)
    if not frames:
        raise AssertionError(f"No rows selected from {path}")
    return pd.concat(frames, ignore_index=True)


def load_headline() -> pd.DataFrame:
    frame = _stream_filter(
        JOOKEN_EVALUATIONS_PATH,
        lambda chunk: (
            (chunk["family"].eq("GEP") & chunk["checkpoint"].eq(MAX_REQUESTS))
            | (
                chunk["family"].eq("baseline")
                & chunk["method"].isin(BASELINE_ORDER)
            )
        )
        & chunk["gap_ppm"].notna(),
    )
    frame["label"] = _label(frame)
    expected_labels = set(HEADLINE_ORDER)
    if set(frame["label"]) != expected_labels:
        raise AssertionError(f"Headline methods differ: {set(frame['label'])}")
    id_rows = frame[frame["partition"] == "id_test"]
    gep_count = len(id_rows[id_rows["family"] == "GEP"])
    baseline_count = len(id_rows[id_rows["family"] == "baseline"])
    if gep_count != 4 * 75 * 345 or baseline_count != 4 * 345:
        raise AssertionError(
            f"ID headline matrix differs: GEP={gep_count}, baseline={baseline_count}"
        )
    return frame


def _tail_metrics(values: pd.Series) -> dict[str, float]:
    array = values.dropna().to_numpy(dtype=np.float64)
    if not len(array):
        return {key: np.nan for key in ("mean", "median", "p90", "cvar90", "worst")}
    threshold = np.quantile(array, 0.90)
    tail = array[array >= threshold]
    return {
        "mean": float(array.mean()),
        "median": float(np.median(array)),
        "p90": float(threshold),
        "cvar90": float(tail.mean()),
        "worst": float(array.max()),
    }


def method_summaries(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    run_rows = []
    group_columns = ["label", "family", "arm", "run", "partition", "region"]
    for keys, subset in frame.groupby(group_columns, dropna=False, sort=False):
        metrics = _tail_metrics(subset["gap_ppm"])
        run_rows.append(
            {
                **dict(zip(group_columns, keys, strict=True)),
                **{f"gap_{key}_ppm": value for key, value in metrics.items()},
                "exact_rate": float(subset["exact"].mean()),
                "instances": int(subset["name"].nunique()),
                "groups": int(subset["group_id"].nunique()),
            }
        )
    runs = pd.DataFrame(run_rows)
    models = pd.read_csv(MODELS_PATH)
    training = models[models["family"] == "GEP"][
        ["arm", "run", "train_mean_gap_ppm", "elapsed_seconds", "unique_orfs"]
    ]
    runs = runs.merge(training, on=["arm", "run"], how="left", validate="many_to_one")
    runs["train_to_test_change_ppm"] = runs["gap_mean_ppm"] - runs["train_mean_gap_ppm"]

    summary_rows = []
    summary_groups = ["label", "family", "arm", "partition", "region"]
    for keys, subset in runs.groupby(summary_groups, dropna=False, sort=False):
        summary_rows.append(
            {
                **dict(zip(summary_groups, keys, strict=True)),
                "runs": int(subset["run"].nunique()),
                "instances": int(subset["instances"].max()),
                "mean_gap_ppm": float(subset["gap_mean_ppm"].mean()),
                "sd_run_mean_gap_ppm": (
                    float(subset["gap_mean_ppm"].std(ddof=1)) if len(subset) > 1 else 0.0
                ),
                "median_gap_ppm": float(subset["gap_median_ppm"].mean()),
                "p90_gap_ppm": float(subset["gap_p90_ppm"].mean()),
                "cvar90_gap_ppm": float(subset["gap_cvar90_ppm"].mean()),
                "worst_gap_ppm": float(subset["gap_worst_ppm"].max()),
                "strict_exact_rate": float(subset["exact_rate"].mean()),
                "mean_train_to_test_change_ppm": float(
                    subset["train_to_test_change_ppm"].mean()
                )
                if subset["train_to_test_change_ppm"].notna().any()
                else np.nan,
            }
        )
    summary = pd.DataFrame(summary_rows)
    for (partition, region), block in summary.groupby(["partition", "region"]):
        maxpw_values = block.loc[block["label"] == "MAXPW", "mean_gap_ppm"]
        if len(maxpw_values) != 1:
            continue
        maxpw = float(maxpw_values.iloc[0])
        index = block.index
        summary.loc[index, "maxpw_gap_closure"] = (
            maxpw - summary.loc[index, "mean_gap_ppm"]
        ) / maxpw
    return runs, summary


def _crossed_arrays(id_rows: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, list[int], list[str]]:
    stochastic = (
        id_rows[id_rows["family"] == "GEP"]
        .groupby(["arm", "run", "group_id"], sort=False)["gap_ppm"]
        .mean()
        .unstack("arm")
    )
    runs = sorted(id_rows.loc[id_rows["family"] == "GEP", "run"].unique())
    groups = sorted(id_rows["group_id"].unique())
    index = pd.MultiIndex.from_product([runs, groups], names=["run", "group_id"])
    stochastic = stochastic.reindex(index)[list(ARM_ORDER)]
    if stochastic.isna().any().any() or len(runs) != 75 or len(groups) != 115:
        raise AssertionError("GEP crossed ID matrix is incomplete")
    array = stochastic.to_numpy().reshape(len(runs), len(groups), len(ARM_ORDER))
    array = np.moveaxis(array, 2, 0)

    deterministic = (
        id_rows[id_rows["family"] == "baseline"]
        .groupby(["method", "group_id"], sort=False)["gap_ppm"]
        .mean()
        .unstack("method")
        .reindex(groups)[list(BASELINE_ORDER)]
    )
    if deterministic.isna().any().any():
        raise AssertionError("Baseline group matrix is incomplete")
    return array, deterministic.to_numpy().T, runs, groups


def crossed_bootstrap(
    stochastic: np.ndarray, deterministic: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    replications = BOOTSTRAP_REPLICATES
    seed_count = stochastic.shape[1]
    group_count = stochastic.shape[2]
    gep = np.empty((replications, len(ARM_ORDER)), dtype=np.float64)
    baselines = np.empty((replications, len(BASELINE_ORDER)), dtype=np.float64)
    batch_size = 250
    seed_probability = np.full(seed_count, 1 / seed_count)
    group_probability = np.full(group_count, 1 / group_count)
    for start in range(0, replications, batch_size):
        stop = min(start + batch_size, replications)
        size = stop - start
        seed_weights = rng.multinomial(seed_count, seed_probability, size=size) / seed_count
        group_weights = (
            rng.multinomial(group_count, group_probability, size=size) / group_count
        )
        gep[start:stop] = np.einsum(
            "bs,asg,bg->ba", seed_weights, stochastic, group_weights, optimize=True
        )
        baselines[start:stop] = group_weights @ deterministic.T
    return gep, baselines


def _holm(pvalues: list[float]) -> list[float]:
    count = len(pvalues)
    order = np.argsort(pvalues)
    adjusted = np.empty(count, dtype=np.float64)
    running = 0.0
    for rank, index in enumerate(order):
        value = min(1.0, (count - rank) * float(pvalues[int(index)]))
        running = max(running, value)
        adjusted[int(index)] = running
    return adjusted.tolist()


def headline_and_contrasts(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    id_rows = frame[frame["partition"] == "id_test"].copy()
    stochastic, deterministic, runs, groups = _crossed_arrays(id_rows)
    gep_boot, baseline_boot = crossed_bootstrap(stochastic, deterministic)
    bootstrap = pd.DataFrame(
        np.column_stack((gep_boot, baseline_boot)), columns=list(HEADLINE_ORDER)
    )
    bootstrap.insert(0, "replicate", np.arange(1, len(bootstrap) + 1))
    point = np.concatenate((stochastic.mean(axis=(1, 2)), deterministic.mean(axis=1)))
    interval_values = np.column_stack((gep_boot, baseline_boot))
    bars = pd.DataFrame(
        {
            "method": HEADLINE_ORDER,
            "order": np.arange(1, len(HEADLINE_ORDER) + 1),
            "mean_gap_ppm": point,
            "ci95_low_ppm": np.quantile(interval_values, 0.025, axis=0),
            "ci95_high_ppm": np.quantile(interval_values, 0.975, axis=0),
            "interval": [
                *("95% crossed seed/group bootstrap" for _ in ARM_ORDER),
                *("95% sibling-group bootstrap" for _ in BASELINE_ORDER),
            ],
            "instances": 345,
            "groups": 115,
            "stochastic_runs": [*(75 for _ in ARM_ORDER), *(1 for _ in BASELINE_ORDER)],
            "budget": [*(MAX_REQUESTS for _ in ARM_ORDER), *(0 for _ in BASELINE_ORDER)],
        }
    )

    run_means = stochastic.mean(axis=2).T
    arm_index = {arm: index for index, arm in enumerate(ARM_ORDER)}
    planned = [("FULL", "BASE", "primary"), ("FULL", "CAP", "secondary"), ("FULL", "SCALE", "secondary")]
    contrast_rows = []
    secondary_p = []
    secondary_positions = []
    for left, right, family in planned:
        difference = run_means[:, arm_index[left]] - run_means[:, arm_index[right]]
        boot_difference = gep_boot[:, arm_index[left]] - gep_boot[:, arm_index[right]]
        ttest = stats.ttest_1samp(difference, 0.0)
        try:
            wilcoxon = stats.wilcoxon(difference, alternative="two-sided")
            wilcoxon_p = float(wilcoxon.pvalue)
        except ValueError:
            wilcoxon_p = 1.0
        try:
            from statsmodels.stats.weightstats import ttost_paired

            tost_p = float(
                ttost_paired(
                    run_means[:, arm_index[left]],
                    run_means[:, arm_index[right]],
                    -SESOI_PPM,
                    SESOI_PPM,
                )[0]
            )
        except Exception:
            tost_p = np.nan
        row = {
            "contrast": f"{left} - {right}",
            "family": family,
            "estimate_ppm": float(difference.mean()),
            "ci95_low_ppm": float(np.quantile(boot_difference, 0.025)),
            "ci95_high_ppm": float(np.quantile(boot_difference, 0.975)),
            "ci90_low_ppm": float(np.quantile(boot_difference, 0.05)),
            "ci90_high_ppm": float(np.quantile(boot_difference, 0.95)),
            "bootstrap_two_sided_p": float(
                min(1.0, 2 * min(np.mean(boot_difference <= 0), np.mean(boot_difference >= 0)))
            ),
            "paired_t_p": float(ttest.pvalue),
            "paired_wilcoxon_p": wilcoxon_p,
            "paired_dz": float(difference.mean() / difference.std(ddof=1)),
            "sesoi_ppm": SESOI_PPM,
            "tost_p": tost_p,
            "equivalent_at_872_ppm": bool(
                np.quantile(boot_difference, 0.05) > -SESOI_PPM
                and np.quantile(boot_difference, 0.95) < SESOI_PPM
            ),
        }
        contrast_rows.append(row)
        if family == "secondary":
            secondary_positions.append(len(contrast_rows) - 1)
            secondary_p.append(row["paired_t_p"])
    adjusted = _holm(secondary_p)
    for position, value in zip(secondary_positions, adjusted, strict=True):
        contrast_rows[position]["holm_paired_t_p"] = value
    contrast_rows[0]["holm_paired_t_p"] = contrast_rows[0]["paired_t_p"]
    contrasts = pd.DataFrame(contrast_rows)

    method_group = {}
    for index, arm in enumerate(ARM_ORDER):
        method_group[arm] = stochastic[index].mean(axis=0)
    for index, method in enumerate(BASELINE_ORDER):
        method_group[method] = deterministic[index]
    friedman_result = stats.friedmanchisquare(
        *(method_group[method] for method in HEADLINE_ORDER)
    )
    friedman = pd.DataFrame(
        [
            {
                "test": "Friedman blocked by 115 sibling groups",
                "methods": 8,
                "groups": 115,
                "statistic": float(friedman_result.statistic),
                "p_value": float(friedman_result.pvalue),
            }
        ]
    )
    posthoc_rows = []
    raw_p = []
    for method in BASELINE_ORDER:
        difference = method_group["FULL"] - method_group[method]
        result = stats.wilcoxon(difference, alternative="two-sided")
        raw_p.append(float(result.pvalue))
        posthoc_rows.append(
            {
                "contrast": f"FULL - {method}",
                "mean_group_difference_ppm": float(difference.mean()),
                "median_group_difference_ppm": float(np.median(difference)),
                "wins": int(np.sum(difference < 0)),
                "ties": int(np.sum(np.isclose(difference, 0, atol=1e-12, rtol=0))),
                "losses": int(np.sum(difference > 0)),
                "wilcoxon_p": float(result.pvalue),
            }
        )
    for row, value in zip(posthoc_rows, _holm(raw_p), strict=True):
        row["holm_p"] = value
    posthoc = pd.DataFrame(posthoc_rows)
    return bars, contrasts, friedman, posthoc, bootstrap


def anytime_summary() -> pd.DataFrame:
    partials = []
    usecols = ["family", "arm", "run", "checkpoint", "partition", "region", "gap_ppm", "exact"]
    for chunk in pd.read_csv(JOOKEN_EVALUATIONS_PATH, usecols=usecols, chunksize=200_000):
        subset = chunk[(chunk["family"] == "GEP") & chunk["gap_ppm"].notna()]
        if subset.empty:
            continue
        partial = subset.groupby(
            ["arm", "run", "checkpoint", "partition", "region"], sort=False
        ).agg(gap_sum=("gap_ppm", "sum"), exact_sum=("exact", "sum"), observations=("gap_ppm", "size"))
        partials.append(partial.reset_index())
    combined = pd.concat(partials, ignore_index=True)
    runs = combined.groupby(
        ["arm", "run", "checkpoint", "partition", "region"], sort=False
    )[["gap_sum", "exact_sum", "observations"]].sum().reset_index()
    runs["mean_gap_ppm"] = runs["gap_sum"] / runs["observations"]
    runs["exact_rate"] = runs["exact_sum"] / runs["observations"]
    summary = runs.groupby(["arm", "checkpoint", "partition", "region"], sort=False).agg(
        median_run_mean_gap_ppm=("mean_gap_ppm", "median"),
        mean_run_mean_gap_ppm=("mean_gap_ppm", "mean"),
        ci95_low_ppm=("mean_gap_ppm", lambda values: np.quantile(values, 0.025)),
        ci95_high_ppm=("mean_gap_ppm", lambda values: np.quantile(values, 0.975)),
        median_exact_rate=("exact_rate", "median"),
        runs=("run", "nunique"),
    ).reset_index()
    return summary


def row_order_summary(headline: pd.DataFrame) -> pd.DataFrame:
    partial = []
    original = headline.copy()
    original["permutation_index"] = 0
    original = original.groupby(
        ["label", "family", "arm", "run", "partition", "region", "permutation_index"],
        dropna=False,
    )["gap_ppm"].mean().reset_index(name="mean_gap_ppm")
    partial.append(original)
    usecols = ["method", "family", "arm", "run", "partition", "region", "gap_ppm", "permutation_index"]
    for path in sorted(ROW_ORDER_ROOT.glob("permutation_*.csv.gz")):
        chunks = []
        for chunk in pd.read_csv(path, usecols=usecols, chunksize=200_000):
            subset = chunk[
                (
                    (chunk["family"] == "GEP")
                    | (
                        (chunk["family"] == "baseline")
                        & chunk["method"].isin(BASELINE_ORDER)
                    )
                )
                & chunk["gap_ppm"].notna()
            ].copy()
            subset["label"] = _label(subset)
            chunks.append(subset)
        values = pd.concat(chunks, ignore_index=True)
        partial.append(
            values.groupby(
                ["label", "family", "arm", "run", "partition", "region", "permutation_index"],
                dropna=False,
            )["gap_ppm"].mean().reset_index(name="mean_gap_ppm")
        )
    all_values = pd.concat(partial, ignore_index=True)
    return all_values.groupby(
        ["label", "family", "arm", "run", "partition", "region"], dropna=False
    ).agg(
        permutations=("permutation_index", "nunique"),
        permutation_mean_gap_ppm=("mean_gap_ppm", "mean"),
        permutation_sd_gap_ppm=("mean_gap_ppm", "std"),
        permutation_min_gap_ppm=("mean_gap_ppm", "min"),
        permutation_max_gap_ppm=("mean_gap_ppm", "max"),
    ).reset_index()


def transfer_summary() -> pd.DataFrame:
    if not PISINGER_EVALUATIONS_PATH.is_file():
        return pd.DataFrame()
    usecols = ["method", "family", "arm", "run", "checkpoint", "region", "name", "gap_ppm", "exact"]
    partials = []
    for chunk in pd.read_csv(PISINGER_EVALUATIONS_PATH, usecols=usecols, chunksize=200_000):
        final_budget = (
            (chunk["family"].isin(["GEP", "RANDOM"]) & chunk["checkpoint"].eq(MAX_REQUESTS))
            | chunk["family"].isin(["AHDAS_BASE", "baseline"])
        )
        subset = chunk[final_budget & chunk["gap_ppm"].notna()].copy()
        subset["label"] = np.where(
            subset["family"].eq("GEP"),
            subset["arm"],
            np.where(
                subset["family"].eq("RANDOM"),
                "RANDOM-" + subset["arm"].astype(str),
                subset["method"],
            ),
        )
        partials.append(subset)
    frame = pd.concat(partials, ignore_index=True)
    runs = frame.groupby(["label", "family", "arm", "run", "region"], dropna=False).agg(
        mean_gap_ppm=("gap_ppm", "mean"),
        exact_rate=("exact", "mean"),
        instances=("name", "nunique"),
    ).reset_index()
    return runs.groupby(["label", "family", "arm", "region"], dropna=False).agg(
        mean_gap_ppm=("mean_gap_ppm", "mean"),
        sd_run_mean_gap_ppm=("mean_gap_ppm", "std"),
        strict_exact_rate=("exact_rate", "mean"),
        runs=("run", "nunique"),
        instances=("instances", "max"),
    ).reset_index()


def unresolved_summary() -> tuple[pd.DataFrame, pd.DataFrame]:
    usecols = ["method", "family", "arm", "run", "checkpoint", "name", "partition", "profit"]
    frame = _stream_filter(
        JOOKEN_EVALUATIONS_PATH,
        lambda chunk: chunk["partition"].eq("unresolved")
        & (
            (chunk["family"].eq("GEP") & chunk["checkpoint"].eq(MAX_REQUESTS))
            | (chunk["family"].eq("baseline") & chunk["method"].isin(BASELINE_ORDER))
        ),
        usecols=usecols,
    )
    frame["label"] = _label(frame)
    averaged = frame.groupby(["label", "name"], sort=False)["profit"].mean().unstack("label")
    rows = []
    for method in HEADLINE_ORDER:
        values = averaged[method]
        row = {
            "method": method,
            "instances": len(values),
            "mean_raw_profit": float(values.mean()),
            "median_raw_profit": float(values.median()),
            "best_profit_count": int((values == averaged.max(axis=1)).sum()),
        }
        for baseline in BASELINE_ORDER:
            difference = values - averaged[baseline]
            row[f"vs_{baseline}_wins"] = int((difference > 0).sum())
            row[f"vs_{baseline}_ties"] = int((difference == 0).sum())
            row[f"vs_{baseline}_losses"] = int((difference < 0).sum())
        rows.append(row)
    cases = averaged.reset_index()
    cases["best_heuristic_profit"] = averaged.max(axis=1).to_numpy()
    cases["best_heuristic_methods"] = [
        "|".join(averaged.columns[row.to_numpy() == row.max()])
        for _, row in averaged.iterrows()
    ]
    if ORACLE_PATH.is_file():
        oracle = pd.read_csv(ORACLE_PATH)
        cases = cases.merge(oracle, on="name", how="left", validate="one_to_one")
        for method in HEADLINE_ORDER:
            cases[f"{method}_certified_gap_ppm"] = np.where(
                cases["certified_optimal"].fillna(False),
                1e6
                * (cases["certified_optimum"] - cases[method])
                / cases["certified_optimum"],
                np.nan,
            )
    return pd.DataFrame(rows), cases


def control_summaries() -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = _stream_filter(
        JOOKEN_EVALUATIONS_PATH,
        lambda chunk: chunk["gap_ppm"].notna()
        & (
            (
                chunk["family"].isin(["GEP", "RANDOM"])
                & chunk["checkpoint"].eq(MAX_REQUESTS)
            )
            | (
                chunk["family"].eq("AHDAS_BASE")
                & chunk["checkpoint"].eq(21_280)
            )
            | (
                chunk["family"].eq("baseline")
                & chunk["method"].isin([*BASELINE_ORDER, "POWER_RANKER"])
            )
        ),
    )
    frame["label"] = np.select(
        [frame["family"].eq("GEP"), frame["family"].eq("RANDOM")],
        [frame["arm"], "RANDOM-" + frame["arm"].astype(str)],
        default=frame["method"],
    )
    runs = frame.groupby(
        ["label", "family", "arm", "run", "partition", "region"],
        dropna=False,
        sort=False,
    ).agg(
        mean_gap_ppm=("gap_ppm", "mean"),
        median_gap_ppm=("gap_ppm", "median"),
        strict_exact_rate=("exact", "mean"),
        instances=("name", "nunique"),
    ).reset_index()
    summary = runs.groupby(
        ["label", "family", "arm", "partition", "region"],
        dropna=False,
        sort=False,
    ).agg(
        mean_gap_ppm=("mean_gap_ppm", "mean"),
        sd_run_mean_gap_ppm=("mean_gap_ppm", "std"),
        median_gap_ppm=("median_gap_ppm", "mean"),
        strict_exact_rate=("strict_exact_rate", "mean"),
        runs=("run", "nunique"),
        instances=("instances", "max"),
    ).reset_index()

    contrast_rows = []
    for arm in ARM_ORDER:
        for (partition, region), block in runs[
            (runs["arm"] == arm) & runs["family"].isin(["GEP", "RANDOM"])
        ].groupby(["partition", "region"], sort=False):
            pivot = block.pivot(index="run", columns="family", values="mean_gap_ppm")
            if not {"GEP", "RANDOM"}.issubset(pivot):
                continue
            difference = pivot["GEP"] - pivot["RANDOM"]
            test = stats.ttest_1samp(difference, 0.0)
            contrast_rows.append(
                {
                    "contrast": f"GEP-{arm} - RANDOM-{arm}",
                    "partition": partition,
                    "region": region,
                    "paired_runs": len(difference),
                    "estimate_ppm": float(difference.mean()),
                    "ci95_low_ppm": float(
                        difference.mean()
                        - stats.t.ppf(0.975, len(difference) - 1)
                        * difference.std(ddof=1)
                        / np.sqrt(len(difference))
                    ),
                    "ci95_high_ppm": float(
                        difference.mean()
                        + stats.t.ppf(0.975, len(difference) - 1)
                        * difference.std(ddof=1)
                        / np.sqrt(len(difference))
                    ),
                    "paired_t_p": float(test.pvalue),
                    "exploratory": True,
                }
            )
    return summary, pd.DataFrame(contrast_rows)


def mixed_model_sensitivity(frame: pd.DataFrame) -> pd.DataFrame:
    values = frame[frame["family"] == "GEP"].copy()
    values = values.groupby(
        ["arm", "run", "master_seed", "group_id", "region"], sort=False
    )["gap_ppm"].mean().reset_index()
    values["all"] = "all"
    try:
        import statsmodels.formula.api as smf

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = smf.mixedlm(
                "gap_ppm ~ C(arm, Treatment(reference='BASE')) * C(region)",
                values,
                groups=values["all"],
                re_formula="0",
                vc_formula={
                    "seed": "0 + C(master_seed)",
                    "instance_group": "0 + C(group_id)",
                },
                use_sparse=True,
            )
            fit = model.fit(reml=True, method="lbfgs", maxiter=500, disp=False)
        confidence = fit.conf_int()
        rows = []
        for term, estimate in fit.fe_params.items():
            rows.append(
                {
                    "term": term,
                    "estimate_ppm": float(estimate),
                    "standard_error_ppm": float(fit.bse_fe[term]),
                    "ci95_low_ppm": float(confidence.loc[term, 0]),
                    "ci95_high_ppm": float(confidence.loc[term, 1]),
                    "converged": bool(fit.converged),
                    "note": "crossed sparse variance components for seed and sibling group",
                }
            )
        return pd.DataFrame(rows)
    except Exception as error:
        return pd.DataFrame(
            [
                {
                    "term": "MODEL_FAILURE",
                    "estimate_ppm": np.nan,
                    "standard_error_ppm": np.nan,
                    "ci95_low_ppm": np.nan,
                    "ci95_high_ppm": np.nan,
                    "converged": False,
                    "note": f"{type(error).__name__}: {error}",
                }
            ]
        )


def run_analysis() -> dict[str, object]:
    verify_lock()
    FIGURE_DATA_ROOT.mkdir(parents=True, exist_ok=True)
    frame = load_headline()
    run_summary, method_summary = method_summaries(frame)
    bars, contrasts, friedman, posthoc, bootstrap = headline_and_contrasts(frame)
    anytime = anytime_summary()
    row_order = row_order_summary(frame)
    transfer = transfer_summary()
    unresolved, unresolved_cases = unresolved_summary()
    controls, control_contrasts = control_summaries()
    mixed = mixed_model_sensitivity(frame)

    generalization = method_summary[
        method_summary["label"].isin(HEADLINE_ORDER)
        & method_summary["partition"].isin(["id_test", "ood_n", "ood_c", "ood_nc"])
    ].copy()
    statistics = pd.concat(
        [
            contrasts.assign(test="planned_representation_contrast"),
            friedman.assign(test="friedman"),
            posthoc.assign(test="full_vs_baseline_wilcoxon"),
            control_contrasts.assign(test="exploratory_gep_vs_random"),
        ],
        ignore_index=True,
        sort=False,
    )
    atomic_csv(run_summary, RUN_SUMMARY_PATH)
    atomic_csv(method_summary, METHOD_SUMMARY_PATH)
    atomic_csv(bars, HEADLINE_PATH)
    atomic_csv(bootstrap, BOOTSTRAP_PATH)
    atomic_csv(contrasts, CONTRASTS_PATH)
    atomic_csv(friedman, FRIEDMAN_PATH)
    atomic_csv(posthoc, POSTHOC_PATH)
    atomic_csv(mixed, MIXED_MODEL_PATH)
    atomic_csv(anytime, ANYTIME_PATH)
    atomic_csv(generalization, GENERALIZATION_PATH)
    atomic_csv(row_order, ROW_ORDER_PATH)
    if not transfer.empty:
        atomic_csv(transfer, TRANSFER_SUMMARY_PATH)
    atomic_csv(unresolved, UNRESOLVED_SUMMARY_PATH)
    atomic_csv(unresolved_cases, UNRESOLVED_CASES_PATH)
    atomic_csv(controls, CONTROL_SUMMARY_PATH)
    atomic_csv(control_contrasts, CONTROL_CONTRASTS_PATH)
    atomic_csv(statistics, STATISTICS_PATH)
    summary = {
        "protocol_version": "2.0.0",
        "primary_endpoint": "mean ID optimality gap in ppm",
        "id_instances": 345,
        "id_sibling_groups": 115,
        "gep_runs_per_arm": 75,
        "raw_request_budget": MAX_REQUESTS,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "sesoi_ppm": SESOI_PPM,
        "headline": bars.to_dict("records"),
        "contrasts": contrasts.to_dict("records"),
        "friedman": friedman.to_dict("records"),
        "unresolved_solver": (
            {
                "attempted": int(len(unresolved_cases)),
                "newly_certified": int(
                    unresolved_cases.get(
                        "certified_optimal", pd.Series(dtype=bool)
                    ).fillna(False).sum()
                ),
            }
            if "certified_optimal" in unresolved_cases
            else {"attempted": 0, "newly_certified": 0}
        ),
        "artifacts": {
            "headline": HEADLINE_PATH.relative_to(RESULTS_ROOT).as_posix(),
            "statistics": STATISTICS_PATH.relative_to(RESULTS_ROOT).as_posix(),
            "method_summary": METHOD_SUMMARY_PATH.relative_to(RESULTS_ROOT).as_posix(),
        },
    }
    atomic_json(summary, SUMMARY_JSON_PATH)
    return summary


def main() -> None:
    summary = run_analysis()
    print(json.dumps(summary["contrasts"], indent=2))


if __name__ == "__main__":
    main()
