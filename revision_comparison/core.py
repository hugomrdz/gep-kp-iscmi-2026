"""Feature extraction, fixed-order labels, R prediction, and grouped inference."""
from pathlib import Path
import subprocess
import numpy as np
import pandas as pd

from src.config import BASELINE_ORDER

FEATURES = ["mean_profit_over_max", "mean_weight_over_max", "correlation_01"]
MODEL_IDS = ["GEP-BASE-020", "GEP-CAP-008", "GEP-SCALE-042", "GEP-FULL-071"]
TEST_PARTITIONS = ["id_test", "ood_n", "ood_c", "ood_nc"]


def instance_features(instance):
    p = np.asarray(instance.profits, dtype=np.float64)
    w = np.asarray(instance.weights, dtype=np.float64)
    if p.shape != w.shape or len(p) == 0 or np.any(p <= 0) or np.any(w <= 0):
        raise ValueError("Features require nonempty paired positive profits and weights")
    pc, wc = p - p.mean(), w - w.mean()
    denom = np.linalg.norm(pc) * np.linalg.norm(wc)
    undefined = bool(denom == 0)
    rho = 0.0 if undefined else float(np.clip(np.dot(pc, wc) / denom, -1, 1))
    return dict(zip(FEATURES, [float(p.mean() / p.max()), float(w.mean() / w.max()),
                               (rho + 1.0) / 2.0]), correlation_undefined=undefined)


def best_label(profits):
    """Python max preserves BASELINE_ORDER for equal integer profits."""
    if set(profits) != set(BASELINE_ORDER):
        raise ValueError("Exactly the four original rules must supply labels")
    winner = max(BASELINE_ORDER, key=lambda method: profits[method])
    ties = [m for m in BASELINE_ORDER if profits[m] == profits[winner]]
    return winner, "|".join(ties)


def assert_separation(development, test):
    if set(development.name) & set(test.name):
        raise ValueError("Development/test instance leakage")
    if set(development.group_id) & set(test.group_id):
        raise ValueError("Development/test sibling-group leakage")
    if not set(development.partition) <= {"train", "validation"}:
        raise ValueError("Invalid development partition")
    if not set(test.partition) <= set(TEST_PARTITIONS):
        raise ValueError("Invalid test partition")


def predict_r(train_path, test_path, output_path, metadata_path):
    script = Path(__file__).with_name("predict.R")
    subprocess.run(["Rscript", "--vanilla", str(script), str(train_path), str(test_path),
                    str(output_path), str(metadata_path)], check=True, capture_output=True, text=True)
    return pd.read_csv(output_path)


def grouped_bootstrap(outcomes, replicates=10_000, seed=20261022):
    ids = outcomes[outcomes.partition.eq("id_test")]
    group_sizes = ids[ids.method.eq("kNN")].groupby("group_id").size()
    if len(group_sizes) != 115 or not group_sizes.eq(3).all():
        raise ValueError("ID bootstrap requires 115 complete groups of three siblings")
    group = ids.groupby(["group_id", "method"]).gap_ppm.mean().unstack().sort_index()
    differences = group[MODEL_IDS].sub(group["kNN"], axis=0)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(group), size=(replicates, len(group)))
    samples = differences.to_numpy()[draws].mean(axis=1)
    # Two-sided Bonferroni: alpha=.05/4, each tail=.00625.
    intervals = np.quantile(samples, [0.00625, 0.99375], axis=0, method="linear")
    rows = []
    for i, method in enumerate(MODEL_IDS):
        rows.append({"contrast": f"{method} - kNN", "mean_difference_ppm": differences[method].mean(),
                     "ci9875_low_ppm": intervals[0, i], "ci9875_high_ppm": intervals[1, i],
                     "groups": len(group), "replicates": replicates, "seed": seed,
                     "conditional_on_selected_models": True})
    return pd.DataFrame(rows), pd.DataFrame(samples, columns=MODEL_IDS), differences
