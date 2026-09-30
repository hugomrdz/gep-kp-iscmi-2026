"""Deterministic baseline rules and transparent power-ranker control."""

from __future__ import annotations

from itertools import product
from typing import Iterable

import numpy as np
import pandas as pd

from .config import BASELINE_ORDER
from .dataset import KnapsackInstance
from .gep import pack_by_scores


def baseline_scores(instance: KnapsackInstance) -> dict[str, np.ndarray]:
    return {
        "DEF": -np.arange(instance.n, dtype=np.float64),
        "MAXP": instance.profits.astype(np.float64),
        "MAXPW": instance.profits.astype(np.float64) / instance.weights,
        "MINW": -instance.weights.astype(np.float64),
    }


def power_ranker_scores(
    instance: KnapsackInstance, alpha: float, beta: float
) -> np.ndarray:
    profit = instance.profits.astype(np.float64) / instance.profits.max()
    weight = instance.weights.astype(np.float64) / instance.weights.max()
    numerator = np.power(profit, alpha)
    denominator = np.power(weight, beta)
    output = np.ones(instance.n, dtype=np.float64)
    np.divide(numerator, denominator, out=output, where=np.abs(denominator) > 1e-12)
    return output


def _evaluation_row(
    instance: KnapsackInstance,
    method: str,
    profit: int,
    packed_weight: int,
    *,
    permutation_index: int = 0,
) -> dict[str, int | float | str | bool]:
    certified = instance.optimum >= 0
    gap = (
        1e6 * (instance.optimum - profit) / instance.optimum
        if certified
        else np.nan
    )
    if packed_weight > instance.capacity:
        raise AssertionError(f"{method} is infeasible for {instance.name}")
    if certified and profit > instance.optimum:
        raise AssertionError(f"{method} exceeds the optimum for {instance.name}")
    return {
        "model_id": method,
        "method": method,
        "method_family": "baseline",
        "arm": "",
        "run": 0,
        "master_seed": "",
        "checkpoint": 0,
        "dataset": instance.dataset,
        "name": instance.name,
        "group_id": instance.group_id,
        "partition": instance.partition,
        "region": instance.region,
        "permutation_index": permutation_index,
        "n": instance.n,
        "c": instance.c,
        "g": instance.g,
        "f": instance.f,
        "eps": instance.eps,
        "s": instance.s,
        "profit": int(profit),
        "optimum": int(instance.optimum),
        "gap_ppm": float(gap),
        "exact": bool(certified and profit == instance.optimum),
        "feasible": True,
        "packed_weight": int(packed_weight),
        "capacity": int(instance.capacity),
    }


def evaluate_baselines(
    instances: Iterable[KnapsackInstance], *, permutation_index: int = 0
) -> pd.DataFrame:
    rows = []
    values = list(instances)
    for instance in values:
        scores = baseline_scores(instance)
        if tuple(scores) != BASELINE_ORDER:
            raise AssertionError("Baseline order changed")
        for method, values_for_method in scores.items():
            solution = pack_by_scores(instance, values_for_method, method)
            rows.append(
                _evaluation_row(
                    instance,
                    method,
                    solution.total_profit,
                    solution.total_weight,
                    permutation_index=permutation_index,
                )
            )
    return pd.DataFrame(rows)


def fit_power_ranker(validation: Iterable[KnapsackInstance]) -> tuple[dict[str, float], pd.DataFrame]:
    cases = list(validation)
    if not cases or any(not case.certified for case in cases):
        raise ValueError("Power-ranker validation requires certified cases")
    grid = np.arange(0.0, 3.0001, 0.25)
    rows = []
    for alpha, beta in product(grid, grid):
        if alpha == 0.0 and beta == 0.0:
            continue
        gaps = []
        for instance in cases:
            solution = pack_by_scores(
                instance,
                power_ranker_scores(instance, float(alpha), float(beta)),
                "POWER_RANKER",
            )
            gaps.append(1e6 * (instance.optimum - solution.total_profit) / instance.optimum)
        rows.append(
            {
                "alpha": float(alpha),
                "beta": float(beta),
                "validation_mean_gap_ppm": float(np.mean(gaps)),
                "validation_median_gap_ppm": float(np.median(gaps)),
            }
        )
    frame = pd.DataFrame(rows).sort_values(
        ["validation_mean_gap_ppm", "alpha", "beta"], kind="stable"
    )
    best_mean = float(frame.iloc[0]["validation_mean_gap_ppm"])
    tied = frame[np.isclose(frame["validation_mean_gap_ppm"], best_mean, rtol=0, atol=1e-12)].copy()
    tied["sum_exponents"] = tied["alpha"] + tied["beta"]
    selected = tied.sort_values(["sum_exponents", "alpha", "beta"], kind="stable").iloc[0]
    return {
        "alpha": float(selected["alpha"]),
        "beta": float(selected["beta"]),
        "validation_mean_gap_ppm": best_mean,
    }, frame


def evaluate_power_ranker(
    instances: Iterable[KnapsackInstance], alpha: float, beta: float
) -> pd.DataFrame:
    rows = []
    for instance in instances:
        solution = pack_by_scores(
            instance, power_ranker_scores(instance, alpha, beta), "POWER_RANKER"
        )
        rows.append(
            _evaluation_row(
                instance,
                "POWER_RANKER",
                solution.total_profit,
                solution.total_weight,
            )
        )
    return pd.DataFrame(rows)
