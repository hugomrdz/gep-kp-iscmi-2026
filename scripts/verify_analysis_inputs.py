#!/usr/bin/env python3
"""Require complete frozen inputs before analysis, including transfer records."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.protocol import verify_lock
from src.verification import _verify_evaluations, _verify_models, _verify_pisinger
from src.config import JOOKEN_ARCHIVE, JOOKEN_ARCHIVE_SHA256, RESULTS_ROOT
from src.io_utils import sha256_file
from src.evaluation import EVALUATION_MANIFEST_PATH
import pandas as pd


def main() -> None:
    verify_lock()
    if sha256_file(JOOKEN_ARCHIVE) != JOOKEN_ARCHIVE_SHA256:
        raise AssertionError("Jooken archive differs from the frozen source")
    expected = {"confirmatory/evaluations_jooken_v2.csv.gz", "transfer/evaluations_pisinger_v2.csv.gz"}
    expected.update(f"confirmatory/row_order/permutation_{i:02d}.csv.gz" for i in range(1, 11))
    actual = set(pd.read_csv(EVALUATION_MANIFEST_PATH)["path"])
    if expected != actual:
        raise AssertionError(f"Incomplete evaluation manifest: missing={sorted(expected - actual)}, extra={sorted(actual - expected)}")
    for relative in ("confirmatory/unresolved_highs_v2.csv", "models_v2.csv.gz", "checkpoints_v2.csv.gz"):
        if not (RESULTS_ROOT / relative).is_file():
            raise FileNotFoundError(RESULTS_ROOT / relative)
    print(_verify_models())
    print(_verify_pisinger())
    print(_verify_evaluations())


if __name__ == "__main__":
    main()
