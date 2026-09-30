"""Streaming parser and certificate audit for Pisinger's 2005 instances."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator
import hashlib
import io
import re
import tarfile

import numpy as np
import pandas as pd

from .config import DATA_ROOT, RESULTS_ROOT
from .dataset import KnapsackInstance
from .io_utils import atomic_csv, sha256_file


PISINGER_ROOT = DATA_ROOT / "pisinger"
PISINGER_MANIFEST = RESULTS_ROOT / "pisinger_manifest_v2.csv"
ARCHIVE_NAMES = (
    "smallcoeff_pisinger.tgz",
    "largecoeff_pisinger.tgz",
    "hardinstances_pisinger.tgz",
)
ARCHIVE_SPECS = {
    "smallcoeff_pisinger.tgz": {
        "bytes": 148_168_396,
        "cases": 10_400,
        "sha256": "e31a402af0609fe053afa56533f79cd15fa54c20172345829d65245068acf63d",
    },
    "largecoeff_pisinger.tgz": {
        "bytes": 324_559_299,
        "cases": 16_000,
        "sha256": "cd4827c74bbd0b988bf5aaefe4919004730e6ddcdb66b57a1f96f9a6c812f4a8",
    },
    "hardinstances_pisinger.tgz": {
        "bytes": 46_359_335,
        "cases": 5_400,
        "sha256": "e30971629f84bbd020a6de4fa9cd70e462ef6a9291ae65cb601cc79dc64bd097",
    },
}
MEMBER_PATTERN = re.compile(r"^knapPI_(?P<type>\d+)_(?P<n>\d+)_(?P<range>\d+)\.csv$")
INSTANCE_PATTERN = re.compile(
    r"^knapPI_(?P<type>\d+)_(?P<n>\d+)_(?P<range>\d+)_(?P<replicate>\d+)$"
)
TYPE_LABELS = {
    1: "uncorrelated",
    2: "weakly_correlated",
    3: "strongly_correlated",
    4: "inverse_strongly_correlated",
    5: "almost_strongly_correlated",
    6: "subset_sum",
    9: "similar_weights",
    11: "uncorrelated_span",
    12: "weakly_correlated_span",
    13: "strongly_correlated_span",
    14: "multiple_strongly_correlated",
    15: "profit_ceiling",
    16: "circle",
}


def _value(line: str, key: str, cast: type[int] | type[float]) -> int | float:
    pieces = line.split()
    if len(pieces) != 2 or pieces[0] != key:
        raise ValueError(f"Expected `{key} value`, found {line!r}")
    return cast(pieces[1])


def _instance_hash(
    n: int, capacity: int, optimum: int, profits: np.ndarray, weights: np.ndarray
) -> str:
    digest = hashlib.sha256()
    digest.update(np.asarray([n, capacity, optimum], dtype="<i8").tobytes())
    digest.update(np.asarray(profits, dtype="<i8").tobytes())
    digest.update(np.asarray(weights, dtype="<i8").tobytes())
    return digest.hexdigest()


def _parse_block(
    block: str,
    *,
    archive_name: str,
    member_name: str,
    archive_hash: str,
) -> tuple[KnapsackInstance, dict[str, object]]:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    if len(lines) < 6:
        raise ValueError(f"Malformed Pisinger block in {member_name}")
    match = INSTANCE_PATTERN.fullmatch(lines[0])
    member_match = MEMBER_PATTERN.fullmatch(member_name)
    if match is None or member_match is None:
        raise ValueError(f"Unexpected Pisinger name {lines[0]!r} / {member_name!r}")
    values = {key: int(value) for key, value in match.groupdict().items()}
    member_values = {key: int(value) for key, value in member_match.groupdict().items()}
    if any(values[key] != member_values[key] for key in ("type", "n", "range")):
        raise AssertionError(f"Instance and member metadata differ for {lines[0]}")
    n = int(_value(lines[1], "n", int))
    capacity = int(_value(lines[2], "c", int))
    optimum = int(_value(lines[3], "z", int))
    solution_time = float(_value(lines[4], "time", float))
    if n != values["n"] or len(lines) != n + 5:
        raise AssertionError(f"Malformed item count for {lines[0]}")
    items = np.empty((n, 4), dtype=np.int64)
    for index, line in enumerate(lines[5:]):
        pieces = [piece.strip() for piece in line.split(",")]
        if len(pieces) != 4:
            raise ValueError(f"Malformed item row in {lines[0]}: {line!r}")
        items[index] = [int(piece) for piece in pieces]
    if not np.array_equal(items[:, 0], np.arange(1, n + 1, dtype=np.int64)):
        raise AssertionError(f"Item identifiers are not 1..n in {lines[0]}")
    profits = items[:, 1].copy()
    weights = items[:, 2].copy()
    selected = items[:, 3].astype(bool)
    if (
        capacity <= 0
        or optimum <= 0
        or np.any(profits <= 0)
        or np.any(weights <= 0)
        or not np.isin(items[:, 3], [0, 1]).all()
    ):
        raise AssertionError(f"Invalid coefficient or solution value in {lines[0]}")
    solution_profit = int(profits[selected].sum(dtype=np.int64))
    solution_weight = int(weights[selected].sum(dtype=np.int64))
    if solution_profit != optimum or solution_weight > capacity:
        raise AssertionError(
            f"Supplied certificate fails for {lines[0]}: "
            f"profit={solution_profit}, z={optimum}, weight={solution_weight}, c={capacity}"
        )
    kind = values["type"]
    label = TYPE_LABELS.get(kind, f"type_{kind}")
    digest = _instance_hash(n, capacity, optimum, profits, weights)
    instance = KnapsackInstance(
        name=lines[0],
        n=n,
        c=values["range"],
        g=kind,
        f=float("nan"),
        eps=float("nan"),
        s=values["replicate"],
        optimum=optimum,
        capacity=capacity,
        profits=profits,
        weights=weights,
        partition="transfer",
        region=f"type_{kind:02d}_{label}",
        group_id=member_name.removesuffix(".csv"),
        dataset="Pisinger",
    )
    metadata = {
        "archive": archive_name,
        "archive_sha256": archive_hash,
        "member": member_name,
        "name": lines[0],
        "type": kind,
        "class_label": label,
        "n": n,
        "coefficient_range": values["range"],
        "replicate": values["replicate"],
        "capacity": capacity,
        "optimum": optimum,
        "supplied_solution_time_seconds": solution_time,
        "supplied_solution_profit": solution_profit,
        "supplied_solution_weight": solution_weight,
        "supplied_selected_items": int(selected.sum()),
        "instance_sha256": digest,
    }
    return instance, metadata


def iter_archive_batches(path: Path) -> Iterator[tuple[str, list[KnapsackInstance], list[dict[str, object]]]]:
    """Yield one 100-instance member at a time to bound memory use."""

    spec = ARCHIVE_SPECS.get(path.name)
    if spec is None:
        raise AssertionError(f"Unrecognized Pisinger archive: {path.name}")
    if path.stat().st_size != spec["bytes"]:
        raise AssertionError(
            f"Pisinger archive size mismatch for {path.name}: "
            f"{path.stat().st_size} != {spec['bytes']}"
        )
    archive_hash = sha256_file(path)
    if archive_hash != spec["sha256"]:
        raise AssertionError(f"Pisinger archive SHA-256 mismatch for {path.name}")
    with tarfile.open(path, mode="r:gz") as archive:
        members = sorted(
            (
                member
                for member in archive.getmembers()
                if member.isfile() and MEMBER_PATTERN.fullmatch(Path(member.name).name)
            ),
            key=lambda member: member.name,
        )
        if not members:
            raise AssertionError(f"No instance CSV members in {path}")
        for member in members:
            handle = archive.extractfile(member)
            if handle is None:
                raise OSError(f"Could not read {member.name} from {path}")
            text = io.TextIOWrapper(handle, encoding="ascii").read()
            blocks = [value.strip() for value in text.split("-----") if value.strip()]
            if len(blocks) != 100:
                raise AssertionError(
                    f"Expected 100 instances in {member.name}, found {len(blocks)}"
                )
            instances: list[KnapsackInstance] = []
            metadata: list[dict[str, object]] = []
            for block in blocks:
                instance, row = _parse_block(
                    block,
                    archive_name=path.name,
                    member_name=Path(member.name).name,
                    archive_hash=archive_hash,
                )
                instances.append(instance)
                metadata.append(row)
            yield Path(member.name).name, instances, metadata


def prepare_pisinger() -> pd.DataFrame:
    """Audit every supplied solution and freeze byte-level duplicate handling."""

    paths = [PISINGER_ROOT / name for name in ARCHIVE_NAMES]
    missing = [path.name for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing Pisinger archives: {missing}")
    records: list[dict[str, object]] = []
    seen_names: set[str] = set()
    first_by_hash: dict[str, str] = {}
    for path in paths:
        for _member, _instances, metadata in iter_archive_batches(path):
            for row in metadata:
                name = str(row["name"])
                if name in seen_names:
                    raise AssertionError(f"Duplicate Pisinger instance name: {name}")
                seen_names.add(name)
                digest = str(row["instance_sha256"])
                duplicate_of = first_by_hash.get(digest, "")
                row["retained"] = duplicate_of == ""
                row["duplicate_of"] = duplicate_of
                if not duplicate_of:
                    first_by_hash[digest] = name
                records.append(row)
    frame = pd.DataFrame(records).sort_values(
        ["archive", "type", "n", "coefficient_range", "replicate"], kind="stable"
    )
    if frame.empty or not frame["supplied_solution_profit"].eq(frame["optimum"]).all():
        raise AssertionError("Pisinger certificate audit did not complete")
    actual_counts = frame.groupby("archive", sort=False).size().to_dict()
    expected_counts = {
        name: int(ARCHIVE_SPECS[name]["cases"]) for name in ARCHIVE_NAMES
    }
    if actual_counts != expected_counts:
        raise AssertionError(
            f"Pisinger case counts differ: {actual_counts} != {expected_counts}"
        )
    atomic_csv(frame, PISINGER_MANIFEST)
    return frame


def iter_retained_batches() -> Iterator[tuple[str, list[KnapsackInstance]]]:
    if not PISINGER_MANIFEST.is_file():
        raise FileNotFoundError("Run the Pisinger manifest audit before transfer evaluation")
    manifest = pd.read_csv(PISINGER_MANIFEST)
    retained = set(manifest.loc[manifest["retained"].astype(bool), "name"].astype(str))
    yielded: set[str] = set()
    for archive_name in ARCHIVE_NAMES:
        path = PISINGER_ROOT / archive_name
        for member, instances, _metadata in iter_archive_batches(path):
            values = [item for item in instances if item.name in retained]
            yielded.update(item.name for item in values)
            if values:
                yield member, values
    if yielded != retained:
        raise AssertionError(
            f"Transfer batch names differ from manifest: missing={sorted(retained - yielded)[:5]}"
        )
