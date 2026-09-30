import numpy as np

from src.config import ARM_ORDER
from src.dataset import KnapsackInstance
from src.gep import (
    BatchEvaluator,
    SearchConfig,
    decode_gene,
    evolve_priority_formula,
    is_valid_gene,
    pack_gene,
    pack_gene_independent,
    protected_divide,
    random_gene,
)


def instance(name: str = "synthetic") -> KnapsackInstance:
    return KnapsackInstance(
        name=name,
        n=6,
        c=100,
        g=2,
        f=0.1,
        eps=0.0,
        s=100,
        optimum=25,
        capacity=10,
        profits=np.asarray([10, 8, 7, 6, 4, 3], dtype=np.int64),
        weights=np.asarray([6, 5, 4, 4, 2, 2], dtype=np.int64),
        partition="train",
        region="ID",
        group_id=name,
        fold="fold_0",
    )


def test_protected_division_contract() -> None:
    left = np.asarray([4.0, 5.0, 6.0])
    right = np.asarray([2.0, 0.0, 1e-13])
    assert np.array_equal(protected_divide(left, right), np.asarray([2.0, 1.0, 1.0]))


def test_variable_gene_lengths_and_alphabets() -> None:
    for head in (6, 8, 10, 12):
        for arm_index, arm in enumerate(ARM_ORDER):
            rng = np.random.default_rng(1000 + head + arm_index)
            for _ in range(200):
                gene = random_gene(rng, arm, head)
                assert len(gene) == 2 * head + 1
                assert is_valid_gene(gene, arm, head)
                _, active = decode_gene(gene, arm)
                assert 1 <= active <= len(gene)


def test_batch_scalar_and_independent_decoders_agree() -> None:
    cases = [instance("a"), instance("b")]
    for arm_index, arm in enumerate(ARM_ORDER):
        evaluator = BatchEvaluator(cases, arm)
        rng = np.random.default_rng(2000 + arm_index)
        for _ in range(20):
            gene = random_gene(rng, arm, 8)
            profits, weights, _ = evaluator.evaluate(gene)
            for index, case in enumerate(cases):
                primary = pack_gene(case, gene, arm)
                independent = pack_gene_independent(case, gene, arm)
                assert primary.total_profit == int(profits[index])
                assert primary.total_weight == int(weights[index])
                assert np.array_equal(primary.selected, independent.selected)


def test_exact_mid_population_checkpoints_and_reproducibility() -> None:
    cases = [instance("a"), instance("b")]
    evaluator = BatchEvaluator(cases, "FULL")
    config = SearchConfig(6, 8, 2, 0.125, 0.7, 1, budget=32)
    first = evolve_priority_formula(
        evaluator.gap_vector, len(cases), "FULL", 123456, config, checkpoints=(7, 13, 32)
    )
    second = evolve_priority_formula(
        evaluator.gap_vector, len(cases), "FULL", 123456, config, checkpoints=(7, 13, 32)
    )
    assert [row["raw_requests"] for row in first.checkpoints] == [7, 13, 32]
    assert first.gene == second.gene
    assert first.mean_gap_ppm == second.mean_gap_ppm
    assert first.raw_requests == 32
