"""Immutable protocol constants and repository paths."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PROJECT_ROOT
DATA_ROOT = PROJECT_ROOT / "data"
RESULTS_ROOT = PROJECT_ROOT / "results"
DEVELOPMENT_ROOT = RESULTS_ROOT / "development"
CONFIRMATORY_ROOT = RESULTS_ROOT / "confirmatory"
TRANSFER_ROOT = RESULTS_ROOT / "transfer"
RUNS_ROOT = RESULTS_ROOT / "runs"
PROTOCOL_ROOT = PROJECT_ROOT / "protocol"
FIGURES_ROOT = PROJECT_ROOT / "figures"
NOTEBOOKS_ROOT = PROJECT_ROOT / "notebooks"
TMP_ROOT = PROJECT_ROOT / "tmp"

JOOKEN_ARCHIVE = DATA_ROOT / "knapsack.zip"
JOOKEN_ARCHIVE_SHA256 = "68ef9b6be17fbc37f303a250aa79cacfcbe7167d5f0b83f8f96c60d666f0fb26"
SPLIT_MANIFEST = RESULTS_ROOT / "split_manifest_v2.csv"
SEEDS_MANIFEST = RESULTS_ROOT / "seeds_v2.csv"
POWER_PLAN = RESULTS_ROOT / "power_plan.md"
ENVIRONMENT_PATH = RESULTS_ROOT / "environment_v2.json"
ASSERTIONS_PATH = RESULTS_ROOT / "assertions_v2.log"
SELECTED_CONFIG_PATH = DEVELOPMENT_ROOT / "selected_config_v2.json"
PROTOCOL_LOCK_PATH = PROTOCOL_ROOT / "protocol_lock.json"

TERMINAL_SETS: dict[str, tuple[str, ...]] = {
    "BASE": ("P", "W", "O", "1", "0"),
    "CAP": ("P", "W", "O", "K", "T", "1", "0"),
    "SCALE": ("P", "W", "O", "L", "1", "0"),
    "FULL": ("P", "W", "O", "K", "T", "L", "1", "0"),
}
ARM_ORDER = tuple(TERMINAL_SETS)
BASELINE_ORDER = ("DEF", "MAXP", "MAXPW", "MINW")
HEADLINE_ORDER = ARM_ORDER + BASELINE_ORDER

SPLIT_SEED = 20260901
IRACE_SEED = 20260902
SURVIVOR_SEED = 20260903
FINAL_SEED = 20260904
PERMUTATION_SEED = 20260905
BOOTSTRAP_SEED = 20260906
RANKING_AUDIT_SEED = 20260907

FINAL_RUNS = 75
SURVIVOR_RUNS = 10
MAX_REQUESTS = 65_536
TUNING_REQUESTS = 16_384
CHECKPOINTS = (1_872, 4_096, 16_384, 21_280, 32_768, 65_536)
SESOI_PPM = 872.0
BOOTSTRAP_REPLICATES = 10_000
ROW_PERMUTATIONS = 10

SEARCH_SPACE = {
    "head_length": (6, 8, 10, 12),
    "population_size": (128, 256, 512),
    "tournament_size": (2, 4, 7),
    "elite_fraction": (0.005, 0.01, 0.02),
    "crossover_rate": (0.50, 0.70, 0.90),
    "expected_mutations": (1, 2, 3),
}

FALLBACK_CONFIG = {
    "head_length": 8,
    "population_size": 256,
    "tournament_size": 4,
    "elite_fraction": 0.01,
    "crossover_rate": 0.70,
    "expected_mutations": 2,
    "budget": MAX_REQUESTS,
}

# Exact operational settings from the accepted AHDAS notebook.  This is a
# continuity control, not a candidate in the V2 representation contrasts.
AHDAS_CONFIG = {
    "head_length": 8,
    "population_size": 280,
    "tournament_size": 4,
    "elite_fraction": 3 / 280,
    "crossover_rate": 0.70,
    "expected_mutations": 2,
    "budget": 21_280,
}


def ensure_directories() -> None:
    for path in (
        DATA_ROOT,
        RESULTS_ROOT,
        DEVELOPMENT_ROOT,
        CONFIRMATORY_ROOT,
        TRANSFER_ROOT,
        RUNS_ROOT,
        PROTOCOL_ROOT,
        FIGURES_ROOT,
        NOTEBOOKS_ROOT,
        TMP_ROOT,
    ):
        path.mkdir(parents=True, exist_ok=True)
