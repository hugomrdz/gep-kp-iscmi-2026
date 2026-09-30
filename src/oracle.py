"""Bounded HiGHS certification attempts for the 263 unresolved Jooken cases."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from time import perf_counter
import json
import math
import os

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csr_matrix

from .config import JOOKEN_ARCHIVE, RESULTS_ROOT, RUNS_ROOT, SPLIT_MANIFEST
from .dataset import KnapsackInstance, load_partitions
from .io_utils import (
    atomic_csv,
    atomic_run_directory,
    canonical_json,
    validate_run_directory,
)
from .protocol import verify_lock


TIME_LIMIT_SECONDS = 60.0
ORACLE_PATH = RESULTS_ROOT / "confirmatory" / "unresolved_highs_v2.csv"


def _solve(instance: KnapsackInstance) -> dict[str, object]:
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(variable, "1")
    destination = RUNS_ROOT / "oracle" / instance.name
    if destination.exists():
        validate_run_directory(destination)
        return json.loads((destination / "result.json").read_text(encoding="utf-8"))
    objective = -instance.profits.astype(np.float64)
    constraint = LinearConstraint(
        csr_matrix(instance.weights.reshape(1, -1).astype(np.float64)),
        -np.inf,
        float(instance.capacity),
    )
    started = perf_counter()
    result = milp(
        objective,
        integrality=np.ones(instance.n, dtype=np.int8),
        bounds=Bounds(np.zeros(instance.n), np.ones(instance.n)),
        constraints=constraint,
        options={
            "time_limit": TIME_LIMIT_SECONDS,
            "mip_rel_gap": 0.0,
            "presolve": True,
            "disp": False,
        },
    )
    elapsed = perf_counter() - started
    incumbent_profit: int | None = None
    incumbent_weight: int | None = None
    if result.x is not None:
        selected = np.asarray(result.x) >= 0.5
        incumbent_weight = int(instance.weights[selected].sum(dtype=np.int64))
        incumbent_profit = int(instance.profits[selected].sum(dtype=np.int64))
        if incumbent_weight > instance.capacity:
            raise AssertionError(f"HiGHS returned infeasible incumbent for {instance.name}")
    dual = getattr(result, "mip_dual_bound", None)
    upper_bound = (
        int(math.ceil(-float(dual) - 1e-9))
        if dual is not None and np.isfinite(float(dual))
        else None
    )
    certified = int(result.status) == 0 and incumbent_profit is not None
    if certified:
        upper_bound = incumbent_profit
    row: dict[str, object] = {
        "name": instance.name,
        "status": int(result.status),
        "status_message": str(result.message),
        "certified_optimal": certified,
        "certified_optimum": incumbent_profit if certified else None,
        "incumbent_profit_lower_bound": incumbent_profit,
        "objective_upper_bound": upper_bound,
        "incumbent_weight": incumbent_weight,
        "capacity": instance.capacity,
        "mip_gap": (
            float(result.mip_gap)
            if getattr(result, "mip_gap", None) is not None
            else None
        ),
        "mip_node_count": (
            int(result.mip_node_count)
            if getattr(result, "mip_node_count", None) is not None
            else None
        ),
        "time_limit_seconds": TIME_LIMIT_SECONDS,
        "elapsed_seconds": elapsed,
        "solver": "scipy.optimize.milp/HiGHS",
        "solver_threads": 1,
    }
    atomic_run_directory(destination, {"result.json": canonical_json(row)})
    print(
        f"HiGHS {instance.name}: status={row['status']} "
        f"lower={incumbent_profit} upper={upper_bound}",
        flush=True,
    )
    return row


def solve_unresolved(workers: int = 4) -> pd.DataFrame:
    verify_lock()
    cases = load_partitions(SPLIT_MANIFEST, ["unresolved"], JOOKEN_ARCHIVE)
    if len(cases) != 263:
        raise AssertionError(f"Expected 263 unresolved cases, found {len(cases)}")
    rows: list[dict[str, object]] = []
    if workers == 1:
        rows = [_solve(case) for case in cases]
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_solve, case): case.name for case in cases}
            for future in as_completed(futures):
                rows.append(future.result())
    frame = pd.DataFrame(rows).sort_values("name", kind="stable")
    if len(frame) != 263 or frame["name"].duplicated().any():
        raise AssertionError("Unresolved solver matrix is incomplete")
    atomic_csv(frame, ORACLE_PATH)
    return frame

