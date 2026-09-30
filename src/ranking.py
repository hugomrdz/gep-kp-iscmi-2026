"""Deterministic probe audit for ranking equivalence to named heuristics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .baselines import baseline_scores
from .config import RANKING_AUDIT_SEED, RESULTS_ROOT
from .dataset import KnapsackInstance
from .gep import decode_gene, evaluate_tree, sanitize_scores, terminal_environment
from .io_utils import atomic_csv


RANKING_EQUIVALENCE_PATH = RESULTS_ROOT / "ranking_equivalence_v2.csv"
PROBE_COUNT = 128


def _probes() -> list[KnapsackInstance]:
    rng = np.random.default_rng(RANKING_AUDIT_SEED)
    values = []
    for index in range(PROBE_COUNT):
        n = int(rng.integers(17, 102))
        weights = rng.integers(1, 100_001, size=n, dtype=np.int64)
        independent = np.exp(rng.uniform(0, np.log(10**9), size=n)).astype(np.int64) + 1
        if index % 4 == 0:
            profits = independent
        elif index % 4 == 1:
            profits = weights * int(rng.integers(2, 50)) + rng.integers(1, 1000, size=n)
        elif index % 4 == 2:
            profits = np.maximum(1, 10**9 - weights * int(rng.integers(2, 50)))
        else:
            profits = (weights // int(rng.integers(1, 20)) + independent // 1000) + 1
        profits = np.asarray(profits, dtype=np.int64)
        capacity = max(1, int(weights.sum(dtype=np.int64) * rng.uniform(0.1, 0.9)))
        values.append(
            KnapsackInstance(
                name=f"ranking_probe_{index:03d}",
                n=n,
                c=10**9,
                g=index % 4,
                f=capacity / weights.sum(dtype=np.int64),
                eps=0.0,
                s=index,
                optimum=-1,
                capacity=capacity,
                profits=profits,
                weights=weights,
                dataset="synthetic-ranking-audit",
            )
        )
    return values


def audit_ranking_equivalence(models: pd.DataFrame) -> pd.DataFrame:
    probes = _probes()
    baseline_orders = {
        probe.name: {
            method: np.argsort(-scores, kind="stable")
            for method, scores in baseline_scores(probe).items()
        }
        for probe in probes
    }
    rows = []
    for model in models.itertuples(index=False):
        tree, _ = decode_gene(str(model.gene), str(model.arm))
        agreements = {method: 0 for method in ("DEF", "MAXP", "MAXPW", "MINW")}
        for probe in probes:
            scores = sanitize_scores(
                evaluate_tree(tree, terminal_environment(probe, str(model.arm))),
                (probe.n,),
            )
            order = np.argsort(-scores, kind="stable")
            for method, baseline_order in baseline_orders[probe.name].items():
                agreements[method] += int(np.array_equal(order, baseline_order))
        exact_labels = [method for method, count in agreements.items() if count == PROBE_COUNT]
        rows.append(
            {
                "model_id": model.model_id,
                "family": model.family,
                "arm": model.arm,
                "run": int(model.run),
                "probe_seed": RANKING_AUDIT_SEED,
                "probes": PROBE_COUNT,
                "ranking_equivalent_to": "|".join(exact_labels),
                **{
                    f"{method}_exact_order_fraction": count / PROBE_COUNT
                    for method, count in agreements.items()
                },
            }
        )
    frame = pd.DataFrame(rows)
    atomic_csv(frame, RANKING_EQUIVALENCE_PATH)
    return frame

