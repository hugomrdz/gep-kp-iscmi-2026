from __future__ import annotations

from pathlib import Path

import pandas as pd
import nbformat
import numpy as np

from src.analysis import crossed_bootstrap
from src.config import AHDAS_CONFIG, NOTEBOOKS_ROOT
from src.dataset import KnapsackInstance
from src.evaluation import EVALUATION_COLUMNS, _result_frame
from src.gep import SearchConfig, evolve_historical_ahdas
from src.io_utils import (
    atomic_csv,
    atomic_csv_stream,
    atomic_run_directory,
    sha256_file,
    validate_run_directory,
)
from src.pisinger import _parse_block
from src.gep import BatchEvaluator
from src.runs import _run_search
from src.ranking import audit_ranking_equivalence
from src.config import HEADLINE_ORDER
from src.figures import _style, headline_bar


def test_streamed_csv_is_deterministic(tmp_path: Path) -> None:
    frames = [pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}), pd.DataFrame({"a": [3], "b": ["z"]})]
    first = tmp_path / "first.csv.gz"
    second = tmp_path / "second.csv.gz"
    assert atomic_csv_stream(iter(frames), first) == 3
    assert atomic_csv_stream(iter(frames), second) == 3
    assert sha256_file(first) == sha256_file(second)
    assert pd.read_csv(first).to_dict("records") == [
        {"a": 1, "b": "x"},
        {"a": 2, "b": "y"},
        {"a": 3, "b": "z"},
    ]
    atomic_first = tmp_path / "atomic-first.csv.gz"
    atomic_second = tmp_path / "atomic-second.csv.gz"
    atomic_csv(pd.concat(frames, ignore_index=True), atomic_first)
    atomic_csv(pd.concat(frames, ignore_index=True), atomic_second)
    assert sha256_file(atomic_first) == sha256_file(atomic_second)


def test_atomic_run_marker_detects_complete_directory(tmp_path: Path) -> None:
    destination = tmp_path / "run_001"
    atomic_run_directory(destination, {"meta.json": "{}\n", "trace.csv": "a\n1\n"})
    hashes = validate_run_directory(destination)
    assert set(hashes) == {"meta.json", "trace.csv"}


def test_historical_control_consumes_exact_accepted_budget() -> None:
    config = SearchConfig.from_dict(AHDAS_CONFIG)

    def gaps(gene: str):
        return [float(len(gene) % 5)]

    outcome = evolve_historical_ahdas(gaps, 1, 12345, config)
    assert outcome.raw_requests == 21_280
    assert [row["raw_requests"] for row in outcome.checkpoints] == [
        1_872,
        4_096,
        16_384,
        21_280,
    ]


def test_pisinger_supplied_solution_is_audited() -> None:
    block = """
knapPI_1_2_10_1
n 2
c 5
z 7
time 0.01
1,7,5,1
2,3,4,0
"""
    instance, row = _parse_block(
        block,
        archive_name="smallcoeff_pisinger.tgz",
        member_name="knapPI_1_2_10.csv",
        archive_hash="abc",
    )
    assert instance.optimum == 7
    assert row["supplied_solution_profit"] == 7
    assert row["supplied_solution_weight"] == 5


def test_advisor_notebook_uses_dollar_math_and_project_kernel() -> None:
    path = NOTEBOOKS_ROOT / "gep_kp_iscmi2026_v2.ipynb"
    notebook = nbformat.read(path, as_version=4)
    markdown = "\n".join(
        cell.source for cell in notebook.cells if cell.cell_type == "markdown"
    )
    assert "\\[" not in markdown
    assert "\\]" not in markdown
    assert notebook.metadata.kernelspec.name == "iscmi2026-v2"


def test_crossed_bootstrap_preserves_constant_method_values() -> None:
    stochastic = np.stack(
        [np.full((3, 2), value, dtype=float) for value in (1, 2, 3, 4)]
    )
    deterministic = np.stack(
        [np.full(2, value, dtype=float) for value in (5, 6, 7, 8)]
    )
    gep, fixed = crossed_bootstrap(stochastic, deterministic)
    assert np.allclose(gep, [1, 2, 3, 4])
    assert np.allclose(fixed, [5, 6, 7, 8])


def test_unified_evaluation_row_keeps_integer_exactness() -> None:
    instance = KnapsackInstance(
        name="tiny",
        n=2,
        c=10,
        g=1,
        f=0.1,
        eps=0.0,
        s=1,
        optimum=7,
        capacity=5,
        profits=np.asarray([7, 3], dtype=np.int64),
        weights=np.asarray([5, 4], dtype=np.int64),
        partition="id_test",
        region="ID",
        group_id="tiny-group",
    )
    frame = _result_frame(
        [instance],
        np.asarray([7]),
        np.asarray([5]),
        model_id="GEP-BASE-001",
        method="BASE",
        family="GEP",
        arm="BASE",
        run=1,
        master_seed="123",
        checkpoint=65_536,
        gene="P0000000000000000",
        permutation_index=0,
    )
    assert list(frame.columns) == EVALUATION_COLUMNS
    assert bool(frame.loc[0, "exact"])
    assert frame.loc[0, "gap_ppm"] == 0.0


def test_resumable_run_writes_human_readable_csv(
    tmp_path: Path, monkeypatch
) -> None:
    instance = KnapsackInstance(
        name="train-tiny",
        n=2,
        c=10,
        g=1,
        f=0.1,
        eps=0.0,
        s=1,
        optimum=7,
        capacity=5,
        profits=np.asarray([7, 3], dtype=np.int64),
        weights=np.asarray([5, 4], dtype=np.int64),
        partition="train",
        region="ID",
        group_id="tiny-group",
    )
    destination = tmp_path / "run_001"
    monkeypatch.setattr("src.runs._run_directory", lambda *args, **kwargs: destination)
    config = SearchConfig(
        head_length=6,
        population_size=128,
        tournament_size=2,
        elite_fraction=0.01,
        crossover_rate=0.5,
        expected_mutations=1,
        budget=128,
    )
    evaluator = BatchEvaluator([instance], "BASE")
    first = _run_search(
        phase="unit",
        family="GEP",
        arm="BASE",
        run=1,
        master_seed=123,
        config=config,
        training=[instance],
        train_evaluator=evaluator,
    )
    second = _run_search(
        phase="unit",
        family="GEP",
        arm="BASE",
        run=1,
        master_seed=123,
        config=config,
        training=[instance],
        train_evaluator=evaluator,
    )
    assert first["gene"] == second["gene"]
    assert first["raw_requests"] == second["raw_requests"] == 128
    assert (destination / "model.csv").is_file()
    assert pd.read_csv(destination / "model.csv").loc[0, "model_id"] == "GEP-BASE-001"


def test_probe_audit_recovers_named_rankings(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "src.ranking.RANKING_EQUIVALENCE_PATH", tmp_path / "ranking.csv"
    )
    models = pd.DataFrame(
        [
            {"model_id": "def", "family": "GEP", "arm": "BASE", "run": 1, "gene": "O" + "0" * 12},
            {"model_id": "maxp", "family": "GEP", "arm": "BASE", "run": 2, "gene": "P" + "0" * 12},
            {"model_id": "maxpw", "family": "GEP", "arm": "BASE", "run": 3, "gene": "/PW" + "0" * 10},
            {"model_id": "minw", "family": "GEP", "arm": "BASE", "run": 4, "gene": "-0W" + "0" * 10},
        ]
    )
    audited = audit_ranking_equivalence(models).set_index("model_id")
    assert audited.loc["def", "ranking_equivalent_to"] == "DEF"
    assert audited.loc["maxp", "ranking_equivalent_to"] == "MAXP"
    assert audited.loc["maxpw", "ranking_equivalent_to"] == "MAXPW"
    assert audited.loc["minw", "ranking_equivalent_to"] == "MINW"


def test_headline_figure_exports_three_formats(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "headline.csv"
    pd.DataFrame(
        {
            "method": HEADLINE_ORDER,
            "mean_gap_ppm": np.arange(1, 9, dtype=float) * 1000,
            "ci95_low_ppm": np.arange(1, 9, dtype=float) * 1000 - 100,
            "ci95_high_ppm": np.arange(1, 9, dtype=float) * 1000 + 100,
        }
    ).to_csv(source, index=False)
    monkeypatch.setattr("src.figures.HEADLINE_PATH", source)
    monkeypatch.setattr("src.figures.FIGURES_ROOT", tmp_path)
    _style()
    headline_bar()
    for suffix in ("pdf", "svg", "png"):
        assert (tmp_path / f"headline_id_gap_v2.{suffix}").stat().st_size > 0
