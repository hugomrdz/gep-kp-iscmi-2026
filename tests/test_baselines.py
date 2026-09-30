import numpy as np

from src.baselines import baseline_scores, power_ranker_scores
from src.config import BASELINE_ORDER
from src.dataset import KnapsackInstance
from src.gep import pack_by_scores


def test_named_baselines_are_feasible_and_ordered() -> None:
    case = KnapsackInstance(
        name="case",
        n=5,
        c=10,
        g=2,
        f=0.1,
        eps=0.0,
        s=100,
        optimum=21,
        capacity=9,
        profits=np.asarray([10, 9, 8, 4, 2], dtype=np.int64),
        weights=np.asarray([6, 5, 4, 2, 1], dtype=np.int64),
    )
    scores = baseline_scores(case)
    assert tuple(scores) == BASELINE_ORDER
    for method, vector in scores.items():
        solution = pack_by_scores(case, vector, method)
        assert solution.total_weight <= case.capacity


def test_power_ranker_alpha_beta_one_matches_maxpw() -> None:
    case = KnapsackInstance(
        name="case",
        n=5,
        c=10,
        g=2,
        f=0.1,
        eps=0.0,
        s=100,
        optimum=21,
        capacity=9,
        profits=np.asarray([10, 9, 8, 4, 2], dtype=np.int64),
        weights=np.asarray([6, 5, 4, 2, 1], dtype=np.int64),
    )
    direct = pack_by_scores(case, baseline_scores(case)["MAXPW"], "MAXPW")
    parametric = pack_by_scores(case, power_ranker_scores(case, 1.0, 1.0), "ranker")
    assert np.array_equal(direct.selected, parametric.selected)
