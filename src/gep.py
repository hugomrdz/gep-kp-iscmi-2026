"""Single-gene GEP engine with variable alphabets and raw-request checkpoints."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from math import ceil
from typing import Callable, Iterable

import numpy as np
import sympy as sp

from .config import CHECKPOINTS, MAX_REQUESTS, TERMINAL_SETS
from .dataset import KnapsackInstance


EPSILON = 1e-12
SCORE_FLOOR = -1e9
SCORE_CEILING = 1e9
FUNCTIONS = ("+", "-", "*", "/")


def protected_divide(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    left, right = np.broadcast_arrays(
        np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    )
    output = np.ones_like(left, dtype=np.float64)
    np.divide(left, right, out=output, where=np.abs(right) > EPSILON)
    return output


@dataclass(frozen=True)
class Primitive:
    symbol: str
    arity: int
    function: Callable[..., np.ndarray]


PRIMITIVES = {
    "+": Primitive("+", 2, np.add),
    "-": Primitive("-", 2, np.subtract),
    "*": Primitive("*", 2, np.multiply),
    "/": Primitive("/", 2, protected_divide),
}


@dataclass
class Node:
    symbol: str
    arm: str
    children: list["Node"] = field(default_factory=list)

    @property
    def arity(self) -> int:
        if self.symbol in PRIMITIVES:
            return PRIMITIVES[self.symbol].arity
        if self.symbol in TERMINAL_SETS[self.arm]:
            return 0
        raise ValueError(f"Unknown symbol {self.symbol!r} for {self.arm}")


def decode_gene(gene: str, arm: str) -> tuple[Node, int]:
    if arm not in TERMINAL_SETS:
        raise ValueError(f"Unknown terminal arm {arm!r}")
    if not gene:
        raise ValueError("Gene cannot be empty")
    root = Node(gene[0], arm)
    awaiting: deque[Node] = deque([root] if root.arity else [])
    cursor = 1
    while awaiting:
        parent = awaiting.popleft()
        for _ in range(parent.arity):
            if cursor >= len(gene):
                raise ValueError("Gene ended before its expression tree closed")
            child = Node(gene[cursor], arm)
            cursor += 1
            parent.children.append(child)
            if child.arity:
                awaiting.append(child)
    return root, cursor


def phenotype_key(gene: str, arm: str) -> str:
    return gene[: decode_gene(gene, arm)[1]]


def to_infix(node: Node) -> str:
    if node.arity == 0:
        return node.symbol
    left, right = (to_infix(child) for child in node.children)
    if node.symbol == "/":
        return f"pdiv({left}, {right})"
    return f"({left} {node.symbol} {right})"


def _ordinary_sympy(node: Node) -> sp.Expr:
    if node.arity == 0:
        return sp.Integer(node.symbol) if node.symbol in {"0", "1"} else sp.Symbol(node.symbol)
    left, right = (_ordinary_sympy(child) for child in node.children)
    return {"+": left + right, "-": left - right, "*": left * right, "/": left / right}[
        node.symbol
    ]


def simplified_formula(node: Node) -> str:
    try:
        return str(sp.simplify(_ordinary_sympy(node)))
    except Exception:
        return to_infix(node)


def terminal_environment(instance: KnapsackInstance, arm: str) -> dict[str, np.ndarray]:
    profits = instance.profits.astype(np.float64)
    weights = instance.weights.astype(np.float64)
    n = instance.n
    shared = {
        "P": profits / profits.max(),
        "W": weights / weights.max(),
        "O": 1.0 - np.arange(n, dtype=np.float64) / max(n - 1, 1),
        "1": np.ones(n, dtype=np.float64),
        "0": np.zeros(n, dtype=np.float64),
    }
    if "K" in TERMINAL_SETS[arm]:
        shared["K"] = weights / instance.capacity
    if "T" in TERMINAL_SETS[arm]:
        shared["T"] = np.full(
            n, instance.capacity / instance.weights.sum(dtype=np.int64), dtype=np.float64
        )
    if "L" in TERMINAL_SETS[arm]:
        shared["L"] = np.log1p(profits) / np.log1p(profits.max())
    if set(shared) != set(TERMINAL_SETS[arm]):
        raise AssertionError(f"Terminal environment mismatch for {arm}: {set(shared)}")
    return shared


def evaluate_tree(node: Node, environment: dict[str, np.ndarray]) -> np.ndarray:
    if node.arity == 0:
        return environment[node.symbol]
    arguments = [evaluate_tree(child, environment) for child in node.children]
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        result = PRIMITIVES[node.symbol].function(*arguments)
    return np.asarray(result, dtype=np.float64)


def sanitize_scores(scores: np.ndarray, shape: tuple[int, ...]) -> np.ndarray:
    values = np.asarray(scores, dtype=np.float64)
    if values.shape != shape:
        values = np.broadcast_to(values, shape).copy()
    values = np.nan_to_num(
        values, nan=SCORE_FLOOR, neginf=SCORE_FLOOR, posinf=SCORE_CEILING
    )
    return np.clip(values, SCORE_FLOOR, SCORE_CEILING)


try:
    from numba import njit

    NUMBA_AVAILABLE = True

    @njit(cache=True)
    def _scan_batch_numba(
        orders: np.ndarray,
        weights: np.ndarray,
        profits: np.ndarray,
        capacities: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        row_count = orders.shape[0]
        packed_weights = np.zeros(row_count, dtype=np.int64)
        packed_profits = np.zeros(row_count, dtype=np.int64)
        for row in range(row_count):
            remaining = capacities[row]
            for position in range(orders.shape[1]):
                item = orders[row, position]
                weight = weights[row, item]
                if weight <= remaining:
                    remaining -= weight
                    packed_weights[row] += weight
                    packed_profits[row] += profits[row, item]
        return packed_weights, packed_profits

except ImportError:  # pragma: no cover
    NUMBA_AVAILABLE = False


def _scan_batch_python(
    orders: np.ndarray,
    weights: np.ndarray,
    profits: np.ndarray,
    capacities: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    packed_weights = np.zeros(len(orders), dtype=np.int64)
    packed_profits = np.zeros(len(orders), dtype=np.int64)
    for row, order in enumerate(orders):
        remaining = int(capacities[row])
        for item_value in order:
            item = int(item_value)
            weight = int(weights[row, item])
            if weight <= remaining:
                remaining -= weight
                packed_weights[row] += weight
                packed_profits[row] += int(profits[row, item])
    return packed_weights, packed_profits


def _scan_batch(
    orders: np.ndarray,
    weights: np.ndarray,
    profits: np.ndarray,
    capacities: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    if NUMBA_AVAILABLE:
        return _scan_batch_numba(orders, weights, profits, capacities)
    return _scan_batch_python(orders, weights, profits, capacities)


@dataclass(frozen=True)
class PackingSolution:
    selected: np.ndarray
    total_weight: int
    total_profit: int
    method: str


def pack_by_scores(
    instance: KnapsackInstance, scores: np.ndarray, method: str
) -> PackingSolution:
    values = sanitize_scores(scores, (instance.n,))
    item_ids = np.arange(instance.n, dtype=np.int64)
    order = np.lexsort((item_ids, -values))
    selected = np.zeros(instance.n, dtype=bool)
    remaining = instance.capacity
    for item_value in order:
        item = int(item_value)
        weight = int(instance.weights[item])
        if weight <= remaining:
            selected[item] = True
            remaining -= weight
    total_weight = int(instance.weights[selected].sum(dtype=np.int64))
    total_profit = int(instance.profits[selected].sum(dtype=np.int64))
    if total_weight > instance.capacity:
        raise AssertionError(f"{method} generated an infeasible solution")
    return PackingSolution(selected, total_weight, total_profit, method)


def pack_gene(instance: KnapsackInstance, gene: str, arm: str) -> PackingSolution:
    tree, _ = decode_gene(gene, arm)
    scores = evaluate_tree(tree, terminal_environment(instance, arm))
    return pack_by_scores(instance, scores, f"GEP-{arm}")


@dataclass(frozen=True)
class _BatchGroup:
    positions: np.ndarray
    instances: tuple[KnapsackInstance, ...]
    weights: np.ndarray
    profits: np.ndarray
    capacities: np.ndarray
    optima: np.ndarray
    environment: dict[str, np.ndarray]


def _batch_environment(
    instances: tuple[KnapsackInstance, ...],
    weights: np.ndarray,
    profits: np.ndarray,
    capacities: np.ndarray,
    arm: str,
) -> dict[str, np.ndarray]:
    rows, n = weights.shape
    float_weights = weights.astype(np.float64)
    float_profits = profits.astype(np.float64)
    environment = {
        "P": float_profits / float_profits.max(axis=1)[:, None],
        "W": float_weights / float_weights.max(axis=1)[:, None],
        "O": np.broadcast_to(
            1.0 - np.arange(n, dtype=np.float64) / max(n - 1, 1), (rows, n)
        ).copy(),
        "1": np.ones((rows, n), dtype=np.float64),
        "0": np.zeros((rows, n), dtype=np.float64),
    }
    if "K" in TERMINAL_SETS[arm]:
        environment["K"] = float_weights / capacities[:, None]
    if "T" in TERMINAL_SETS[arm]:
        tightness = capacities / weights.sum(axis=1, dtype=np.int64)
        environment["T"] = np.broadcast_to(tightness[:, None], (rows, n)).copy()
    if "L" in TERMINAL_SETS[arm]:
        environment["L"] = np.log1p(float_profits) / np.log1p(
            float_profits.max(axis=1)
        )[:, None]
    if set(environment) != set(TERMINAL_SETS[arm]):
        raise AssertionError(f"Batched terminal environment mismatch for {arm}")
    return environment


class BatchEvaluator:
    """Semantics-preserving evaluator grouped by equal item count."""

    def __init__(self, instances: Iterable[KnapsackInstance], arm: str):
        self.instances = tuple(instances)
        self.arm = arm
        if not self.instances:
            raise ValueError("BatchEvaluator needs at least one instance")
        self.groups: tuple[_BatchGroup, ...] = tuple(
            self._make_group(n) for n in sorted({item.n for item in self.instances})
        )

    def _make_group(self, n: int) -> _BatchGroup:
        positions = np.asarray(
            [index for index, item in enumerate(self.instances) if item.n == n], dtype=np.int64
        )
        instances = tuple(self.instances[int(index)] for index in positions)
        weights = np.stack([item.weights for item in instances]).astype(np.int64, copy=False)
        profits = np.stack([item.profits for item in instances]).astype(np.int64, copy=False)
        capacities = np.asarray([item.capacity for item in instances], dtype=np.int64)
        optima = np.asarray([item.optimum for item in instances], dtype=np.int64)
        return _BatchGroup(
            positions,
            instances,
            weights,
            profits,
            capacities,
            optima,
            _batch_environment(instances, weights, profits, capacities, self.arm),
        )

    def evaluate(self, gene: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        tree, _ = decode_gene(gene, self.arm)
        profits = np.empty(len(self.instances), dtype=np.int64)
        weights = np.empty(len(self.instances), dtype=np.int64)
        gaps = np.full(len(self.instances), np.nan, dtype=np.float64)
        for group in self.groups:
            scores = sanitize_scores(
                evaluate_tree(tree, group.environment), group.weights.shape
            )
            orders = np.argsort(-scores, axis=1, kind="stable")
            group_weights, group_profits = _scan_batch(
                orders, group.weights, group.profits, group.capacities
            )
            weights[group.positions] = group_weights
            profits[group.positions] = group_profits
            certified = group.optima > 0
            local_gaps = np.full(len(group.optima), np.nan, dtype=np.float64)
            local_gaps[certified] = 1e6 * (
                group.optima[certified] - group_profits[certified]
            ) / group.optima[certified]
            gaps[group.positions] = local_gaps
        return profits, weights, gaps

    def gap_vector(self, gene: str) -> np.ndarray:
        gaps = self.evaluate(gene)[2]
        if np.isnan(gaps).any():
            raise ValueError("Training objective requires certified optima")
        return gaps


@dataclass(frozen=True)
class SearchConfig:
    head_length: int
    population_size: int
    tournament_size: int
    elite_fraction: float
    crossover_rate: float
    expected_mutations: int
    budget: int = MAX_REQUESTS

    @property
    def tail_length(self) -> int:
        return self.head_length + 1

    @property
    def gene_length(self) -> int:
        return self.head_length + self.tail_length

    @property
    def elite_count(self) -> int:
        return max(1, ceil(self.population_size * self.elite_fraction))

    @property
    def mutation_rate(self) -> float:
        return self.expected_mutations / self.gene_length

    @property
    def populations(self) -> int:
        if self.budget % self.population_size:
            raise ValueError("Budget must be divisible by population size")
        return self.budget // self.population_size

    @classmethod
    def from_dict(cls, values: dict[str, int | float]) -> "SearchConfig":
        return cls(
            head_length=int(values["head_length"]),
            population_size=int(values["population_size"]),
            tournament_size=int(values["tournament_size"]),
            elite_fraction=float(values["elite_fraction"]),
            crossover_rate=float(values["crossover_rate"]),
            expected_mutations=int(values["expected_mutations"]),
            budget=int(values.get("budget", MAX_REQUESTS)),
        )

    def as_dict(self) -> dict[str, int | float]:
        return {
            "head_length": self.head_length,
            "tail_length": self.tail_length,
            "gene_length": self.gene_length,
            "population_size": self.population_size,
            "populations": self.populations,
            "tournament_size": self.tournament_size,
            "elite_fraction": self.elite_fraction,
            "elite_count": self.elite_count,
            "crossover_rate": self.crossover_rate,
            "expected_mutations": self.expected_mutations,
            "mutation_rate": self.mutation_rate,
            "budget": self.budget,
        }


def random_gene(rng: np.random.Generator, arm: str, head_length: int) -> str:
    terminals = TERMINAL_SETS[arm]
    tail_length = head_length + 1
    head = "".join(rng.choice(FUNCTIONS + terminals, size=head_length))
    tail = "".join(rng.choice(terminals, size=tail_length))
    return head + tail


def is_valid_gene(gene: str, arm: str, head_length: int) -> bool:
    if arm not in TERMINAL_SETS or len(gene) != 2 * head_length + 1:
        return False
    terminals = TERMINAL_SETS[arm]
    if any(symbol not in FUNCTIONS + terminals for symbol in gene[:head_length]):
        return False
    if any(symbol not in terminals for symbol in gene[head_length:]):
        return False
    try:
        decode_gene(gene, arm)
    except (KeyError, ValueError):
        return False
    return True


def _mutate(
    gene: str,
    arm: str,
    config: SearchConfig,
    rng: np.random.Generator,
) -> str:
    symbols = list(gene)
    terminals = TERMINAL_SETS[arm]
    for position, old in enumerate(symbols):
        if rng.random() >= config.mutation_rate:
            continue
        alphabet = FUNCTIONS + terminals if position < config.head_length else terminals
        alternatives = tuple(symbol for symbol in alphabet if symbol != old)
        symbols[position] = str(rng.choice(alternatives))
    output = "".join(symbols)
    if not is_valid_gene(output, arm, config.head_length):
        raise AssertionError("Mutation produced an invalid gene")
    return output


def _recombine(
    left: str, right: str, arm: str, config: SearchConfig, rng: np.random.Generator
) -> tuple[str, str]:
    cut = int(rng.integers(1, config.gene_length))
    children = (left[:cut] + right[cut:], right[:cut] + left[cut:])
    if not all(is_valid_gene(child, arm, config.head_length) for child in children):
        raise AssertionError("Crossover produced an invalid gene")
    return children


def _fitness_tuple(mean_gap: float, gene: str, arm: str) -> tuple[float, int, str, str]:
    key = phenotype_key(gene, arm)
    return float(mean_gap), len(key), key, gene


@dataclass(frozen=True)
class SearchOutcome:
    gene: str
    mean_gap_ppm: float
    raw_requests: int
    unique_orfs: int
    candidate_instance_evaluations: int
    checkpoints: tuple[dict[str, int | float | str], ...]
    generations: tuple[dict[str, int | float | str], ...]


def _checkpoint_row(
    request: int,
    gene: str,
    mean_gap: float,
    arm: str,
    unique_orfs: int,
    candidate_instance_evaluations: int,
) -> dict[str, int | float | str]:
    tree, active = decode_gene(gene, arm)
    return {
        "raw_requests": request,
        "gene": gene,
        "orf_length": active,
        "expression": to_infix(tree),
        "simplified": simplified_formula(tree),
        "train_mean_gap_ppm": float(mean_gap),
        "unique_orfs": unique_orfs,
        "candidate_instance_evaluations": candidate_instance_evaluations,
    }


def evolve_priority_formula(
    gap_function: Callable[[str], np.ndarray],
    training_case_count: int,
    arm: str,
    seed: int,
    config: SearchConfig,
    checkpoints: Iterable[int] = CHECKPOINTS,
) -> SearchOutcome:
    """Run GEP without early stopping and snapshot exact raw-request counts."""

    seed_sequence = np.random.SeedSequence(int(seed))
    initialization_seed, selection_seed, crossover_seed, mutation_seed = seed_sequence.spawn(4)
    initialization_rng = np.random.default_rng(initialization_seed)
    selection_rng = np.random.default_rng(selection_seed)
    crossover_rng = np.random.default_rng(crossover_seed)
    mutation_rng = np.random.default_rng(mutation_seed)
    population = [
        random_gene(initialization_rng, arm, config.head_length)
        for _ in range(config.population_size)
    ]
    cache: dict[str, float] = {}
    candidate_instance_evaluations = 0
    raw_requests = 0
    checkpoint_targets = set(int(value) for value in checkpoints if value <= config.budget)
    checkpoint_rows: list[dict[str, int | float | str]] = []
    generation_rows: list[dict[str, int | float | str]] = []
    global_best_gene = ""
    global_best_fitness: tuple[float, int, str, str] | None = None

    def evaluate(gene: str) -> tuple[float, int, str, str]:
        nonlocal candidate_instance_evaluations
        key = phenotype_key(gene, arm)
        if key not in cache:
            gaps = np.asarray(gap_function(gene), dtype=np.float64)
            if not np.isfinite(gaps).all() or np.any(gaps < -1e-7):
                raise AssertionError("Training produced invalid optimality gaps")
            cache[key] = float(gaps.mean())
            candidate_instance_evaluations += training_case_count
        return _fitness_tuple(cache[key], gene, arm)

    for population_index in range(config.populations):
        fitnesses: list[tuple[float, int, str, str]] = []
        for gene in population:
            fitness = evaluate(gene)
            fitnesses.append(fitness)
            raw_requests += 1
            if global_best_fitness is None or fitness < global_best_fitness:
                global_best_fitness = fitness
                global_best_gene = gene
            if raw_requests in checkpoint_targets:
                checkpoint_rows.append(
                    _checkpoint_row(
                        raw_requests,
                        global_best_gene,
                        global_best_fitness[0],
                        arm,
                        len(cache),
                        candidate_instance_evaluations,
                    )
                )
        order = sorted(range(len(population)), key=lambda index: fitnesses[index])
        current = fitnesses[order[0]]
        generation_rows.append(
            {
                "population_index": population_index,
                "raw_requests": raw_requests,
                "generation_best_gap_ppm": current[0],
                "global_best_gap_ppm": global_best_fitness[0],
                "global_best_gene": global_best_gene,
                "unique_orfs": len(cache),
                "candidate_instance_evaluations": candidate_instance_evaluations,
            }
        )
        if population_index + 1 == config.populations:
            break
        elites = [population[index] for index in order[: config.elite_count]]

        def select_parent() -> str:
            contenders = selection_rng.integers(
                0, len(population), size=config.tournament_size
            )
            winner = min((int(value) for value in contenders), key=lambda index: fitnesses[index])
            return population[winner]

        next_population = list(elites)
        while len(next_population) < config.population_size:
            parent_a, parent_b = select_parent(), select_parent()
            if crossover_rng.random() < config.crossover_rate:
                children = _recombine(parent_a, parent_b, arm, config, crossover_rng)
            else:
                children = (parent_a, parent_b)
            for child in children:
                next_population.append(_mutate(child, arm, config, mutation_rng))
                if len(next_population) == config.population_size:
                    break
        population = next_population

    if raw_requests != config.budget or global_best_fitness is None:
        raise AssertionError("Search did not consume the exact raw-request budget")
    if sorted(row["raw_requests"] for row in checkpoint_rows) != sorted(checkpoint_targets):
        raise AssertionError("One or more raw-request checkpoints were not recorded")
    return SearchOutcome(
        gene=global_best_gene,
        mean_gap_ppm=float(global_best_fitness[0]),
        raw_requests=raw_requests,
        unique_orfs=len(cache),
        candidate_instance_evaluations=candidate_instance_evaluations,
        checkpoints=tuple(checkpoint_rows),
        generations=tuple(generation_rows),
    )


def random_gene_search(
    gap_function: Callable[[str], np.ndarray],
    training_case_count: int,
    arm: str,
    seed: int,
    config: SearchConfig,
    checkpoints: Iterable[int] = CHECKPOINTS,
) -> SearchOutcome:
    rng = np.random.default_rng(np.random.SeedSequence(int(seed)).spawn(1)[0])
    cache: dict[str, float] = {}
    candidate_instance_evaluations = 0
    best_gene = ""
    best_fitness: tuple[float, int, str, str] | None = None
    checkpoint_targets = set(int(value) for value in checkpoints if value <= config.budget)
    rows: list[dict[str, int | float | str]] = []
    for request in range(1, config.budget + 1):
        gene = random_gene(rng, arm, config.head_length)
        key = phenotype_key(gene, arm)
        if key not in cache:
            gaps = np.asarray(gap_function(gene), dtype=np.float64)
            cache[key] = float(gaps.mean())
            candidate_instance_evaluations += training_case_count
        fitness = _fitness_tuple(cache[key], gene, arm)
        if best_fitness is None or fitness < best_fitness:
            best_fitness, best_gene = fitness, gene
        if request in checkpoint_targets:
            rows.append(
                _checkpoint_row(
                    request,
                    best_gene,
                    best_fitness[0],
                    arm,
                    len(cache),
                    candidate_instance_evaluations,
                )
            )
    if best_fitness is None:
        raise AssertionError("Random search evaluated no genes")
    return SearchOutcome(
        gene=best_gene,
        mean_gap_ppm=float(best_fitness[0]),
        raw_requests=config.budget,
        unique_orfs=len(cache),
        candidate_instance_evaluations=candidate_instance_evaluations,
        checkpoints=tuple(rows),
        generations=tuple(),
    )


def evolve_historical_ahdas(
    gap_function: Callable[[str], np.ndarray],
    training_case_count: int,
    seed: int,
    config: SearchConfig,
    checkpoints: Iterable[int] = CHECKPOINTS,
) -> SearchOutcome:
    """Reproduce the accepted notebook's BASE search as a labelled control.

    The historical code used one RNG stream and maximized mean quality plus
    0.1 times worst quality, with a 1e-5 ORF penalty.  It evaluated generation
    zero and 75 updates (280 * 76 = 21,280 raw requests).
    """

    arm = "BASE"
    if (
        config.head_length != 8
        or config.population_size != 280
        or config.tournament_size != 4
        or config.elite_count != 3
        or not np.isclose(config.crossover_rate, 0.70)
        or not np.isclose(config.mutation_rate, 2 / 17)
        or config.budget != 21_280
    ):
        raise ValueError("AHDAS continuity control requires the accepted settings")
    rng = np.random.default_rng(int(seed))
    population = [random_gene(rng, arm, config.head_length) for _ in range(280)]
    cache: dict[str, tuple[float, float]] = {}
    candidate_instance_evaluations = 0
    raw_requests = 0
    checkpoint_targets = set(int(value) for value in checkpoints if value <= config.budget)
    checkpoint_rows: list[dict[str, int | float | str]] = []
    generation_rows: list[dict[str, int | float | str]] = []
    global_best_gene = ""
    global_best_objective = -np.inf
    global_best_gap = np.inf

    def evaluate(gene: str) -> tuple[float, float]:
        nonlocal candidate_instance_evaluations
        key = phenotype_key(gene, arm)
        if key not in cache:
            gaps = np.asarray(gap_function(gene), dtype=np.float64)
            if not np.isfinite(gaps).all() or np.any(gaps < -1e-7):
                raise AssertionError("Historical search produced invalid gaps")
            qualities = 1.0 - gaps / 1e6
            objective = (
                float(qualities.mean())
                + 0.1 * float(qualities.min())
                - 1e-5 * len(key)
            )
            cache[key] = objective, float(gaps.mean())
            candidate_instance_evaluations += training_case_count
        return cache[key]

    for population_index in range(config.populations):
        objectives = np.empty(config.population_size, dtype=np.float64)
        mean_gaps = np.empty(config.population_size, dtype=np.float64)
        for index, gene in enumerate(population):
            objective, mean_gap = evaluate(gene)
            objectives[index] = objective
            mean_gaps[index] = mean_gap
            raw_requests += 1
            if objective > global_best_objective:
                global_best_objective = objective
                global_best_gap = mean_gap
                global_best_gene = gene
            if raw_requests in checkpoint_targets:
                row = _checkpoint_row(
                    raw_requests,
                    global_best_gene,
                    global_best_gap,
                    arm,
                    len(cache),
                    candidate_instance_evaluations,
                )
                row["historical_objective"] = float(global_best_objective)
                checkpoint_rows.append(row)
        order = np.argsort(-objectives)
        best_index = int(order[0])
        generation_rows.append(
            {
                "population_index": population_index,
                "raw_requests": raw_requests,
                "generation_best_gap_ppm": float(mean_gaps[best_index]),
                "historical_objective": float(objectives[best_index]),
                "global_best_gap_ppm": float(global_best_gap),
                "global_best_gene": global_best_gene,
                "unique_orfs": len(cache),
                "candidate_instance_evaluations": candidate_instance_evaluations,
            }
        )
        if population_index + 1 == config.populations:
            break
        next_population = [population[int(index)] for index in order[:3]]
        while len(next_population) < config.population_size:
            contenders_a = rng.integers(0, len(population), size=4)
            contenders_b = rng.integers(0, len(population), size=4)
            parent_a = population[int(contenders_a[np.argmax(objectives[contenders_a])])]
            parent_b = population[int(contenders_b[np.argmax(objectives[contenders_b])])]
            children = (
                _recombine(parent_a, parent_b, arm, config, rng)
                if rng.random() < config.crossover_rate
                else (parent_a, parent_b)
            )
            for child in children:
                next_population.append(_mutate(child, arm, config, rng))
                if len(next_population) == config.population_size:
                    break
        population = next_population

    if raw_requests != 21_280 or not global_best_gene:
        raise AssertionError("Historical search did not consume 21,280 requests")
    return SearchOutcome(
        gene=global_best_gene,
        mean_gap_ppm=float(global_best_gap),
        raw_requests=raw_requests,
        unique_orfs=len(cache),
        candidate_instance_evaluations=candidate_instance_evaluations,
        checkpoints=tuple(checkpoint_rows),
        generations=tuple(generation_rows),
    )


def pack_gene_independent(
    instance: KnapsackInstance, gene: str, arm: str
) -> PackingSolution:
    """Independent array decoder used only for semantic auditing."""

    terminals = TERMINAL_SETS[arm]

    def arity(symbol: str) -> int:
        if symbol in FUNCTIONS:
            return 2
        if symbol in terminals:
            return 0
        raise ValueError(symbol)

    symbols = [gene[0]]
    children: list[list[int]] = [[]]
    queue = [0] if arity(gene[0]) else []
    cursor = 1
    queue_cursor = 0
    while queue_cursor < len(queue):
        parent = queue[queue_cursor]
        queue_cursor += 1
        for _ in range(arity(symbols[parent])):
            index = len(symbols)
            symbols.append(gene[cursor])
            children.append([])
            children[parent].append(index)
            if arity(gene[cursor]):
                queue.append(index)
            cursor += 1
    environment = terminal_environment(instance, arm)

    def evaluate(index: int) -> np.ndarray:
        symbol = symbols[index]
        if arity(symbol) == 0:
            return environment[symbol]
        left, right = (evaluate(child) for child in children[index])
        if symbol == "+":
            return left + right
        if symbol == "-":
            return left - right
        if symbol == "*":
            return left * right
        output = np.ones(np.broadcast(left, right).shape, dtype=np.float64)
        np.divide(left, right, out=output, where=np.abs(right) > EPSILON)
        return output

    scores = sanitize_scores(evaluate(0), (instance.n,))
    order = sorted(range(instance.n), key=lambda item: (-float(scores[item]), item))
    selected = np.zeros(instance.n, dtype=bool)
    remaining = instance.capacity
    for item in order:
        weight = int(instance.weights[item])
        if weight <= remaining:
            selected[item] = True
            remaining -= weight
    return PackingSolution(
        selected,
        int(instance.weights[selected].sum(dtype=np.int64)),
        int(instance.profits[selected].sum(dtype=np.int64)),
        f"independent-{arm}",
    )
