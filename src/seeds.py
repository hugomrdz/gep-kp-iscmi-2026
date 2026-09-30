"""Published seed schedules and deterministic row-permutation seeds."""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from .config import (
    FINAL_RUNS,
    FINAL_SEED,
    IRACE_SEED,
    PERMUTATION_SEED,
    SURVIVOR_RUNS,
    SURVIVOR_SEED,
)


STREAM_NAMES = ("initialization", "selection", "crossover", "mutation")


def _phase_rows(phase: str, root_seed: int, count: int) -> list[dict[str, int | str]]:
    masters = np.random.SeedSequence(root_seed).generate_state(count, dtype=np.uint64)
    rows: list[dict[str, int | str]] = []
    for run, master_value in enumerate(masters, start=1):
        master = int(master_value)
        streams = np.random.SeedSequence(master).spawn(4)
        row: dict[str, int | str] = {
            "phase": phase,
            "run": run,
            "root_seed": root_seed,
            "master_seed": str(master),
        }
        for name, stream in zip(STREAM_NAMES, streams, strict=True):
            row[f"{name}_seed"] = str(int(stream.generate_state(1, dtype=np.uint64)[0]))
        rows.append(row)
    return rows


def seed_manifest() -> pd.DataFrame:
    rows = _phase_rows("survivor", SURVIVOR_SEED, SURVIVOR_RUNS)
    rows.extend(_phase_rows("final", FINAL_SEED, FINAL_RUNS))
    frame = pd.DataFrame(rows)
    if frame.duplicated(["phase", "run"]).any():
        raise AssertionError("Duplicate phase/run seed rows")
    if frame["master_seed"].duplicated().any():
        raise AssertionError("Master seeds overlap across phases")
    return frame


def irace_seed() -> int:
    return IRACE_SEED


def permutation_seed(instance_name: str, permutation_index: int) -> int:
    if permutation_index < 1:
        raise ValueError("Permutation index is one-based")
    material = f"{PERMUTATION_SEED}|{instance_name}|{permutation_index}".encode()
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "little", signed=False)


def permutation_manifest(instance_names: list[str], count: int) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "name": name,
                "permutation_index": index,
                "seed": str(permutation_seed(name, index)),
            }
            for name in sorted(instance_names)
            for index in range(1, count + 1)
        ]
    )
