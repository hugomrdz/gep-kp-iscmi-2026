from pathlib import Path

import pandas as pd

from src.config import SPLIT_MANIFEST
from src.dataset import PARTITION_COUNTS, validate_split_manifest


def test_locked_split_manifest_counts_and_blocking() -> None:
    assert Path(SPLIT_MANIFEST).is_file()
    manifest = pd.read_csv(SPLIT_MANIFEST)
    validate_split_manifest(manifest)
    assert manifest.groupby("partition").size().to_dict() == PARTITION_COUNTS
    id_rows = manifest[manifest.partition.isin(["train", "validation", "id_test"])]
    assert id_rows.groupby("group_id").partition.nunique().max() == 1
    assert set(id_rows.groupby("group_id").size()) == {3}


def test_no_unresolved_case_is_used_for_development() -> None:
    manifest = pd.read_csv(SPLIT_MANIFEST)
    development = manifest[manifest.partition.isin(["train", "validation"])]
    assert development.certified.astype(bool).all()
    assert (development.optimum > 0).all()
