"""Jooken archive parser and V2 blocked train/validation/test allocator."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Sequence
import csv
import hashlib
import io
import re
import zipfile

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csr_matrix, vstack

from .config import JOOKEN_ARCHIVE, SPLIT_SEED


ARCHIVE_ROOT = "knapsackProblemInstances-master/"
NAME_PATTERN = re.compile(
    r"^n_(?P<n>\d+)_c_(?P<c>\d+)_g_(?P<g>\d+)"
    r"_f_(?P<f>[0-9.]+)_eps_(?P<eps>[0-9.e\-]+)_s_(?P<s>\d+)$"
)
EXPECTED_LEVELS = {
    "n": {400, 600, 800, 1000, 1200},
    "c": {10**6, 10**8, 10**10},
    "g": {2, 6, 10, 14},
    "f": {0.1, 0.2, 0.3},
    "eps": {0.0, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1},
    "s": {100, 200, 300},
}
PARTITION_COUNTS = {
    "train": 1038,
    "validation": 345,
    "id_test": 345,
    "ood_n": 432,
    "ood_c": 667,
    "ood_nc": 150,
    "unresolved": 263,
}


@dataclass(frozen=True, slots=True)
class KnapsackInstance:
    name: str
    n: int
    c: int
    g: int
    f: float
    eps: float
    s: int
    optimum: int
    capacity: int
    profits: np.ndarray
    weights: np.ndarray
    partition: str = "unassigned"
    region: str = "unassigned"
    group_id: str = ""
    fold: str = ""
    dataset: str = "Jooken"

    @property
    def certified(self) -> bool:
        return self.optimum >= 0


def parse_design_name(name: str) -> dict[str, int | float]:
    match = NAME_PATTERN.fullmatch(name)
    if match is None:
        raise ValueError(f"Invalid Jooken instance name: {name!r}")
    values = match.groupdict()
    return {
        "n": int(values["n"]),
        "c": int(values["c"]),
        "g": int(values["g"]),
        "f": float(values["f"]),
        "eps": float(values["eps"]),
        "s": int(values["s"]),
    }


def group_id_for(values: dict[str, int | float]) -> str:
    return (
        f"n={values['n']}|c={values['c']}|g={values['g']}|"
        f"f={values['f']:.12g}|eps={values['eps']:.12g}"
    )


def _read_optima(zf: zipfile.ZipFile) -> dict[str, int]:
    text = zf.read(f"{ARCHIVE_ROOT}optima.csv").decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(text)))
    if len(rows) != 3240:
        raise AssertionError(f"Expected 3240 optimum rows, found {len(rows)}")
    result = {row["name"]: int(row["optimum"]) for row in rows}
    if len(result) != len(rows):
        raise AssertionError("Duplicate names in optima.csv")
    return result


def _instance_names(zf: zipfile.ZipFile) -> list[str]:
    prefix = f"{ARCHIVE_ROOT}problemInstances/"
    suffix = "/test.in"
    names = sorted(
        member[len(prefix) : -len(suffix)]
        for member in zf.namelist()
        if member.startswith(prefix) and member.endswith(suffix)
    )
    if len(names) != 3240 or len(set(names)) != 3240:
        raise AssertionError(f"Expected 3240 unique instance files, found {len(names)}")
    return names


def _load_instance(zf: zipfile.ZipFile, name: str, optimum: int) -> KnapsackInstance:
    tokens = zf.read(f"{ARCHIVE_ROOT}problemInstances/{name}/test.in").decode().split()
    n = int(tokens[0])
    if len(tokens) != 2 + 3 * n:
        raise AssertionError(f"{name}: malformed token count")
    rows = np.asarray(tokens[1 : 1 + 3 * n], dtype=np.int64).reshape(n, 3)
    if not np.array_equal(rows[:, 0], np.arange(n, dtype=np.int64)):
        raise AssertionError(f"{name}: item ids are not 0..n-1")
    capacity = int(tokens[-1])
    factors = parse_design_name(name)
    if n != factors["n"]:
        raise AssertionError(f"{name}: declared n disagrees with directory")
    profits = rows[:, 1].copy()
    weights = rows[:, 2].copy()
    if capacity <= 0 or np.any(profits <= 0) or np.any(weights <= 0):
        raise AssertionError(f"{name}: non-positive capacity/profit/weight")
    return KnapsackInstance(
        name=name,
        n=n,
        c=int(factors["c"]),
        g=int(factors["g"]),
        f=float(factors["f"]),
        eps=float(factors["eps"]),
        s=int(factors["s"]),
        optimum=int(optimum),
        capacity=capacity,
        profits=profits,
        weights=weights,
        group_id=group_id_for(factors),
    )


def load_collection(path: Path | str = JOOKEN_ARCHIVE) -> list[KnapsackInstance]:
    path = Path(path)
    with zipfile.ZipFile(path) as zf:
        names = _instance_names(zf)
        optima = _read_optima(zf)
        if set(names) != set(optima):
            raise AssertionError("Instance files and optima.csv names differ")
        instances = [_load_instance(zf, name, optima[name]) for name in names]
    validate_raw_collection(instances)
    return instances


def validate_raw_collection(instances: Sequence[KnapsackInstance]) -> None:
    if len(instances) != 3240 or len({item.name for item in instances}) != 3240:
        raise AssertionError("Collection is not exactly 3240 unique instances")
    certified = sum(item.certified for item in instances)
    if certified != 2977:
        raise AssertionError(f"Expected 2977 certified cases, found {certified}")
    factor_rows = [parse_design_name(item.name) for item in instances]
    for factor, expected in EXPECTED_LEVELS.items():
        actual = {row[factor] for row in factor_rows}
        if actual != expected:
            raise AssertionError(f"Unexpected {factor} levels: {actual}")


def _balanced_assignment(
    groups: pd.DataFrame,
    partition_sizes: dict[str, int],
    *,
    factors: Sequence[str],
    seed: int,
) -> dict[str, str]:
    """Solve exact capacities, minimum marginal L1 imbalance, then seeded tie-break."""

    groups = groups.sort_values("group_id", kind="stable").reset_index(drop=True)
    group_count = len(groups)
    partition_names = tuple(partition_sizes)
    if sum(partition_sizes.values()) != group_count:
        raise ValueError("Partition sizes do not cover all groups")
    partition_count = len(partition_names)
    marginal_terms: list[tuple[int, str, object, np.ndarray, int]] = []
    for partition_index, partition in enumerate(partition_names):
        for factor in factors:
            for level in sorted(groups[factor].unique()):
                mask = np.flatnonzero(groups[factor].to_numpy() == level)
                marginal_terms.append((partition_index, factor, level, mask, len(mask)))

    x_count = group_count * partition_count
    term_count = len(marginal_terms)
    variable_count = x_count + 2 * term_count
    rows: list[dict[int, float]] = []
    lower: list[float] = []
    upper: list[float] = []

    for group_index in range(group_count):
        rows.append({group_index * partition_count + p: 1.0 for p in range(partition_count)})
        lower.append(1.0)
        upper.append(1.0)
    for partition_index, partition in enumerate(partition_names):
        rows.append(
            {
                group_index * partition_count + partition_index: 1.0
                for group_index in range(group_count)
            }
        )
        target = float(partition_sizes[partition])
        lower.append(target)
        upper.append(target)
    for term_index, (partition_index, _factor, _level, mask, level_count) in enumerate(
        marginal_terms
    ):
        row = {
            int(group_index) * partition_count + partition_index: float(group_count)
            for group_index in mask
        }
        row[x_count + term_index] = -1.0
        row[x_count + term_count + term_index] = 1.0
        rows.append(row)
        target = float(partition_sizes[partition_names[partition_index]] * level_count)
        lower.append(target)
        upper.append(target)

    row_indices: list[int] = []
    column_indices: list[int] = []
    values: list[float] = []
    for row_index, row in enumerate(rows):
        for column_index, value in row.items():
            row_indices.append(row_index)
            column_indices.append(column_index)
            values.append(value)
    matrix = csr_matrix((values, (row_indices, column_indices)), shape=(len(rows), variable_count))
    constraint = LinearConstraint(matrix, np.asarray(lower), np.asarray(upper))
    bounds = Bounds(
        np.zeros(variable_count),
        np.concatenate((np.ones(x_count), np.full(2 * term_count, np.inf))),
    )
    integrality = np.concatenate((np.ones(x_count, dtype=int), np.zeros(2 * term_count, dtype=int)))
    primary = np.zeros(variable_count, dtype=float)
    for term_index, (partition_index, _factor, _level, _mask, level_count) in enumerate(
        marginal_terms
    ):
        target = partition_sizes[partition_names[partition_index]] * level_count
        weight = 1.0 / max(float(target), 1.0)
        primary[x_count + term_index] = weight
        primary[x_count + term_count + term_index] = weight
    first = milp(
        primary,
        integrality=integrality,
        bounds=bounds,
        constraints=constraint,
        options={"time_limit": 120.0, "mip_rel_gap": 0.0},
    )
    if not first.success or first.x is None:
        raise RuntimeError(f"Marginal split optimization failed: {first.message}")

    rng = np.random.Generator(np.random.PCG64(seed))
    secondary = np.zeros(variable_count, dtype=float)
    secondary[:x_count] = rng.random(x_count)
    optimality = LinearConstraint(csr_matrix(primary.reshape(1, -1)), -np.inf, first.fun + 1e-8)
    combined = LinearConstraint(
        vstack((matrix, optimality.A), format="csr"),
        np.concatenate((np.asarray(lower), np.atleast_1d(optimality.lb))),
        np.concatenate((np.asarray(upper), np.atleast_1d(optimality.ub))),
    )
    second = milp(
        secondary,
        integrality=integrality,
        bounds=bounds,
        constraints=combined,
        options={"time_limit": 120.0, "mip_rel_gap": 0.0},
    )
    solution = second.x if second.success and second.x is not None else first.x
    assignments: dict[str, str] = {}
    for group_index, group_id in enumerate(groups["group_id"].astype(str)):
        values_for_group = solution[
            group_index * partition_count : (group_index + 1) * partition_count
        ]
        assignments[group_id] = partition_names[int(np.argmax(values_for_group))]
    actual = pd.Series(assignments.values()).value_counts().to_dict()
    if actual != partition_sizes:
        raise AssertionError(f"Balanced assignment counts differ: {actual}")
    return assignments


def build_split_manifest(instances: Sequence[KnapsackInstance]) -> pd.DataFrame:
    raw = pd.DataFrame(
        [
            {
                "name": item.name,
                "n": item.n,
                "c": item.c,
                "g": item.g,
                "f": item.f,
                "eps": item.eps,
                "s": item.s,
                "group_id": item.group_id,
                "certified": item.certified,
                "optimum": item.optimum,
                "capacity": item.capacity,
                "instance_sha256": hashlib.sha256(
                    item.profits.tobytes() + item.weights.tobytes() + str(item.capacity).encode()
                ).hexdigest(),
            }
            for item in instances
        ]
    )
    id_mask = (
        raw["certified"]
        & raw["n"].isin([400, 600, 800, 1000])
        & raw["c"].isin([10**6, 10**8])
    )
    id_rows = raw.loc[id_mask]
    group_sizes = id_rows.groupby("group_id").size()
    if len(id_rows) != 1728 or len(group_sizes) != 576 or not (group_sizes == 3).all():
        raise AssertionError("ID pool is not 576 complete groups of three")
    groups = id_rows.drop_duplicates("group_id")[
        ["group_id", "n", "c", "g", "f", "eps"]
    ]
    assignment = _balanced_assignment(
        groups,
        {"train": 346, "validation": 115, "id_test": 115},
        factors=("n", "c", "g", "f", "eps"),
        seed=SPLIT_SEED,
    )
    train_groups = groups[groups["group_id"].map(assignment) == "train"]
    fold_assignment = _balanced_assignment(
        train_groups,
        {"fold_0": 87, "fold_1": 87, "fold_2": 86, "fold_3": 86},
        factors=("n", "c", "g", "f", "eps"),
        seed=SPLIT_SEED + 1,
    )

    partitions: list[str] = []
    regions: list[str] = []
    folds: list[str] = []
    for row in raw.itertuples(index=False):
        if not bool(row.certified):
            partition = "unresolved"
            region = "OOD-nc" if row.n == 1200 else "OOD-c"
        elif row.group_id in assignment:
            partition = assignment[row.group_id]
            region = "ID"
        elif row.n == 1200 and row.c in (10**6, 10**8):
            partition, region = "ood_n", "OOD-n"
        elif row.n in (400, 600, 800, 1000) and row.c == 10**10:
            partition, region = "ood_c", "OOD-c"
        elif row.n == 1200 and row.c == 10**10:
            partition, region = "ood_nc", "OOD-nc"
        else:
            raise AssertionError(f"Unassigned certified case: {row.name}")
        partitions.append(partition)
        regions.append(region)
        folds.append(fold_assignment.get(row.group_id, ""))
    raw["partition"] = partitions
    raw["region"] = regions
    raw["fold"] = folds
    raw["split_seed"] = SPLIT_SEED
    raw = raw[
        [
            "name", "n", "c", "g", "f", "eps", "s", "group_id", "region",
            "partition", "fold", "certified", "optimum", "capacity",
            "instance_sha256", "split_seed",
        ]
    ].sort_values("name", kind="stable").reset_index(drop=True)
    validate_split_manifest(raw)
    return raw


def validate_split_manifest(manifest: pd.DataFrame) -> None:
    if len(manifest) != 3240 or manifest["name"].duplicated().any():
        raise AssertionError("Split manifest must contain 3240 unique names")
    counts = manifest.groupby("partition").size().to_dict()
    if counts != PARTITION_COUNTS:
        raise AssertionError(f"Partition counts differ: {counts}")
    id_rows = manifest[manifest["partition"].isin(["train", "validation", "id_test"])]
    crossing = id_rows.groupby("group_id")["partition"].nunique()
    if not (crossing == 1).all():
        raise AssertionError("An ID sibling group crosses partitions")
    if id_rows.groupby("group_id").size().ne(3).any():
        raise AssertionError("An ID group does not contain exactly three s siblings")
    train = manifest[manifest["partition"] == "train"]
    if train["fold"].eq("").any():
        raise AssertionError("A training case has no development fold")
    fold_groups = train.drop_duplicates("group_id").groupby("fold").size().to_dict()
    if fold_groups != {"fold_0": 87, "fold_1": 87, "fold_2": 86, "fold_3": 86}:
        raise AssertionError(f"Development fold counts differ: {fold_groups}")


def attach_manifest(
    instances: Iterable[KnapsackInstance], manifest: pd.DataFrame
) -> list[KnapsackInstance]:
    metadata = manifest.set_index("name")
    output = []
    for item in instances:
        row = metadata.loc[item.name]
        output.append(
            replace(
                item,
                partition=str(row["partition"]),
                region=str(row["region"]),
                group_id=str(row["group_id"]),
                fold="" if pd.isna(row["fold"]) else str(row["fold"]),
            )
        )
    return output


def load_partitions(
    manifest_path: Path | str,
    partitions: Iterable[str],
    archive_path: Path | str = JOOKEN_ARCHIVE,
) -> list[KnapsackInstance]:
    manifest = pd.read_csv(manifest_path)
    validate_split_manifest(manifest)
    wanted = manifest[manifest["partition"].isin(tuple(partitions))]
    metadata = wanted.set_index("name")
    archive_path = Path(archive_path)
    with zipfile.ZipFile(archive_path) as zf:
        optima = _read_optima(zf)
        values = [_load_instance(zf, name, optima[name]) for name in sorted(metadata.index)]
    return attach_manifest(values, wanted)


def load_manifest_rows(
    rows: pd.DataFrame,
    archive_path: Path | str = JOOKEN_ARCHIVE,
) -> list[KnapsackInstance]:
    """Load only explicitly supplied manifest rows, avoiding full-archive parsing."""

    if rows.empty:
        raise ValueError("No manifest rows were selected")
    if rows["name"].duplicated().any():
        raise ValueError("Selected manifest rows contain duplicate names")
    metadata = rows.set_index("name")
    with zipfile.ZipFile(Path(archive_path)) as zf:
        optima = _read_optima(zf)
        values = [_load_instance(zf, name, optima[name]) for name in sorted(metadata.index)]
    return attach_manifest(values, rows)


def instances_for_partition(
    instances: Iterable[KnapsackInstance], *partitions: str
) -> list[KnapsackInstance]:
    allowed = set(partitions)
    return [item for item in instances if item.partition in allowed]
