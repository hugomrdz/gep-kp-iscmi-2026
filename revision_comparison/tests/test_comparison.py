from dataclasses import replace
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from src.dataset import KnapsackInstance
from src.gep import pack_by_scores
from src.baselines import baseline_scores
from revision_comparison.core import (FEATURES, MODEL_IDS, assert_separation, best_label,
                                     grouped_bootstrap, instance_features, predict_r)
from revision_comparison.study import outcome


def case(profits, weights):
    return SimpleNamespace(profits=np.asarray(profits), weights=np.asarray(weights))


def test_three_published_features_with_known_correlation():
    f = instance_features(case([2, 4, 6], [3, 6, 9]))
    assert np.allclose([f[k] for k in FEATURES], [2 / 3, 2 / 3, 1])
    f = instance_features(case([2, 4, 6], [9, 6, 3]))
    assert f[FEATURES[2]] == pytest.approx(0, abs=1e-15)
    assert not f["correlation_undefined"]


@pytest.mark.parametrize("profits,weights", [([2, 2, 2], [1, 2, 3]), ([1, 2, 3], [5, 5, 5]), ([2], [3])])
def test_undefined_correlation_and_zero_variance(profits, weights):
    f = instance_features(case(profits, weights))
    assert f["correlation_undefined"]
    assert f[FEATURES[2]] == 0.5
    assert all(np.isfinite(f[k]) and 0 <= f[k] <= 1 for k in FEATURES)


def test_features_invariant_to_positive_scale_and_item_order():
    p, w = np.array([3, 9, 4]), np.array([2, 7, 11])
    first = instance_features(case(p, w))
    second = instance_features(case(p[::-1] * 100, w[::-1] * 50))
    assert np.allclose([first[k] for k in FEATURES], [second[k] for k in FEATURES])


def test_label_ties_use_fixed_order_not_dict_order():
    assert best_label({"MINW": 10, "MAXPW": 10, "MAXP": 10, "DEF": 10}) == ("DEF", "DEF|MAXP|MAXPW|MINW")
    assert best_label({"MINW": 9, "MAXPW": 20, "MAXP": 20, "DEF": 10}) == ("MAXP", "MAXP|MAXPW")
    assert best_label({"DEF": 1, "MAXP": 3, "MAXPW": 5, "MINW": 4}) == ("MAXPW", "MAXPW")


def test_separation_rejects_instance_and_sibling_leakage():
    train = pd.DataFrame({"name": ["a"], "group_id": ["g1"], "partition": ["train"]})
    test = pd.DataFrame({"name": ["b"], "group_id": ["g2"], "partition": ["id_test"]})
    assert_separation(train, test)
    with pytest.raises(ValueError, match="instance leakage"):
        assert_separation(train, test.assign(name="a"))
    with pytest.raises(ValueError, match="sibling-group leakage"):
        assert_separation(train, test.assign(group_id="g1"))
    with pytest.raises(ValueError, match="development partition"):
        assert_separation(train.assign(partition="id_test"), test)


def test_actual_r_knn_known_neighbors_zero_variance_and_seeded_ties(tmp_path):
    train = pd.DataFrame({"name": ["a", "b", "c", "d"],
                          FEATURES[0]: [0, 0, 1, 1], FEATURES[1]: [0.5] * 4,
                          FEATURES[2]: [0.5] * 4, "label": ["DEF", "MAXP", "MAXPW", "MAXPW"]})
    test = pd.DataFrame({"name": [f"z{i:02d}" for i in range(20)],
                         FEATURES[0]: [0] * 19 + [0.99], FEATURES[1]: [0.5] * 20,
                         FEATURES[2]: [0.5] * 20})
    train.to_csv(tmp_path / "train.csv", index=False)
    test.to_csv(tmp_path / "test.csv", index=False)
    first = predict_r(tmp_path / "train.csv", tmp_path / "test.csv", tmp_path / "one.csv", tmp_path / "one.txt")
    second = predict_r(tmp_path / "train.csv", tmp_path / "test.csv", tmp_path / "two.csv", tmp_path / "two.txt")
    pd.testing.assert_frame_equal(first, second)
    assert set(first.prediction.iloc[:19]) == {"DEF", "MAXP"}
    assert first.winning_vote_fraction.iloc[:19].eq(0.5).all()
    assert first.prediction.iloc[-1] == "MAXPW" and first.winning_vote_fraction.iloc[-1] == 1


def test_feasibility_and_certified_optimum_recomputed_from_selection():
    item = KnapsackInstance(name="tiny", n=3, c=5, g=1, f=.1, eps=0., s=1, optimum=7,
                            capacity=5, profits=np.array([7, 4, 3]), weights=np.array([5, 3, 2]))
    solution = pack_by_scores(item, baseline_scores(item)["MAXPW"], "MAXPW")
    row = outcome(item, "MAXPW", solution)
    assert row["profit"] == 7 and row["feasible"] and row["optimum_bound_ok"]
    with pytest.raises(AssertionError):
        outcome(replace(item, optimum=6), "MAXPW", solution)


def test_bootstrap_resamples_complete_siblings_and_reports_all_four():
    rows = []
    for g in range(115):
        for s in range(3):
            for i, method in enumerate(["kNN"] + MODEL_IDS):
                rows.append({"name": f"{g}-{s}", "partition": "id_test", "group_id": f"g{g:03d}",
                             "method": method, "gap_ppm": 100 + i * (g - 57) + i * 10})
    frame = pd.DataFrame(rows)
    contrasts, samples, groups = grouped_bootstrap(frame)
    assert len(contrasts) == 4 and samples.shape == (10000, 4) and groups.shape == (115, 4)
    assert np.allclose(contrasts.mean_difference_ppm, [10, 20, 30, 40])
    draws = np.random.default_rng(20261022).integers(0, 115, size=(10000, 115))
    expected = (np.arange(115) - 57 + 10)[draws].mean(axis=1)
    assert np.allclose(samples.iloc[:, 0], expected)
    assert np.allclose(contrasts.iloc[0][["ci9875_low_ppm", "ci9875_high_ppm"]].astype(float),
                       np.quantile(expected, [.00625, .99375]))
    with pytest.raises(ValueError, match="115 complete groups"):
        grouped_bootstrap(frame[frame.name.ne("0-0")])
