"""Build and optionally execute the cell-by-cell advisor notebook."""

from __future__ import annotations

from pathlib import Path
import argparse
import os

import nbformat as nbf

from .config import NOTEBOOKS_ROOT, PROJECT_ROOT


NOTEBOOK_PATH = NOTEBOOKS_ROOT / "gep_kp_iscmi2026_v2.ipynb"


def markdown(value: str) -> nbf.NotebookNode:
    if "\\[" in value or "\\]" in value:
        raise AssertionError("Notebook math must use $ or $$, never bracket delimiters")
    return nbf.v4.new_markdown_cell(value.strip())


def code(value: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(value.strip())


def build() -> Path:
    NOTEBOOKS_ROOT.mkdir(parents=True, exist_ok=True)
    cells = [
        markdown(
            r"""
# GEP for 0–1 knapsack: ISCMI 2026 confirmatory experiment

This notebook is the readable, cell-by-cell view of protocol V2. It does **not**
launch the multi-hour evolutionary experiment. It loads the frozen artifacts,
shows the data, exposes the important source functions, and rebuilds the advisor
tables and figures.

The knapsack problem chooses binary item decisions $x_i\in\{0,1\}$:

$$
\max \sum_i p_i x_i \qquad \text{subject to}\qquad
\sum_i w_i x_i\le c.
$$

For certified optimum $O_i$ and recovered profit $H_i$, the main error is

$$
g_i=10^6\frac{O_i-H_i}{O_i}.
$$

Lower gap is better, and $g_i=0$ means exact recovery.
"""
        ),
        markdown(
            """
## Module 1 — Use the project kernel and locate the experiment

Choose **Python (.venv — ISCMI 2026 V2)** in Jupyter. The first cell prints the
exact interpreter and package versions so a wrong kernel is obvious immediately.
"""
        ),
        code(
            """
from pathlib import Path
import os, sys, json, inspect

start = Path.cwd().resolve()
candidates = [start, *start.parents]
ROOT = next(path for path in candidates if (path / "src" / "config.py").is_file())
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import scipy
import sympy as sp
from IPython import get_ipython
get_ipython().run_line_magic("matplotlib", "inline")
import matplotlib.pyplot as plt
from IPython.display import Code, Image, Markdown, display

print("Experiment root:", ROOT)
print("Python kernel:", sys.executable)
print("Python:", sys.version.split()[0])
print("NumPy:", np.__version__, "pandas:", pd.__version__, "SciPy:", scipy.__version__)
print("SymPy:", sp.__version__)
assert ".venv" in Path(sys.executable).as_posix(), "Select the project .venv kernel"
"""
        ),
        markdown(
            r"""
## Module 2 — What is in the Jooken dataset?

The archive contains 3,240 generated 0–1 knapsack cases. Each name records:

- $n$: number of items;
- $c$: generator coefficient scale;
- $g$: correlation/generator setting;
- $f$: capacity fraction;
- $\epsilon$: perturbation level;
- $s$: perturbation bound (not a random seed).

There are 2,977 cases with supplied certified optima and 263 unresolved cases.
The in-distribution pool keeps the three $s$ siblings together, then makes a
reproducible group-random train/validation/ID split. The larger item-count and
coefficient levels form three explicit OOD regions.
"""
        ),
        code(
            """
from src.config import RESULTS_ROOT, SPLIT_MANIFEST, ARM_ORDER, TERMINAL_SETS
from src.dataset import validate_split_manifest

split = pd.read_csv(SPLIT_MANIFEST)
validate_split_manifest(split)
partition_table = (
    split.groupby(["partition", "region"], dropna=False)
    .agg(instances=("name", "size"), groups=("group_id", "nunique"), certified=("certified", "sum"))
    .reset_index()
)
display(partition_table)
assert len(split) == 3240
assert int(split["certified"].sum()) == 2977
"""
        ),
        markdown(
            """
## Module 3 — Look at actual knapsack items

Each point below is one item. The dashed line is not a feasibility boundary; it
simply helps show how profit and weight scales differ across example cases.
Color marks what the transparent MAXPW density rule packs.
"""
        ),
        code(
            """
from src.config import JOOKEN_ARCHIVE
from src.dataset import load_partitions
from src.baselines import baseline_scores
from src.gep import pack_by_scores

examples = []
for partition in ("train", "id_test", "ood_nc"):
    examples.append(load_partitions(SPLIT_MANIFEST, [partition], JOOKEN_ARCHIVE)[0])

fig, axes = plt.subplots(1, 3, figsize=(13, 3.6), constrained_layout=True)
for ax, instance in zip(axes, examples):
    solution = pack_by_scores(instance, baseline_scores(instance)["MAXPW"], "MAXPW")
    ax.scatter(instance.weights[~solution.selected], instance.profits[~solution.selected], s=9, alpha=.35, label="not packed")
    ax.scatter(instance.weights[solution.selected], instance.profits[solution.selected], s=12, alpha=.75, label="packed")
    ax.set_title(f"{instance.partition}: n={instance.n}, c-level={instance.c:,}")
    ax.set_xlabel("item weight")
    ax.set_ylabel("item profit")
axes[0].legend(frameon=False)
plt.show()
"""
        ),
        markdown(
            r"""
## Module 4 — The four terminal configurations

All arms share normalized profit $P$, normalized weight $W$, original row signal
$O$, and constants 1 and 0. `CAP` adds per-item capacity use $K=w_i/c$ and
instance tightness $T=c/\sum_jw_j$. `SCALE` adds log-normalized profit $L$.
`FULL` contains both feature groups. This is a $2\times2$ information ablation,
not four arbitrary formulas.
"""
        ),
        code(
            """
terminal_table = pd.DataFrame(
    [{"arm": arm, "terminals": " ".join(terminals)} for arm, terminals in TERMINAL_SETS.items()]
)
display(terminal_table)

from src import gep
display(Markdown("### Terminal construction used by every evaluation"))
display(Code(inspect.getsource(gep.terminal_environment), language="python"))
"""
        ),
        markdown(
            r"""
## Module 5 — How a gene becomes a feasible solution

A valid GEP gene decodes into one arithmetic priority expression. Its score is
computed for every item, scores are sanitized, and a stable descending sort is
scanned once. An item is accepted only when it still fits. The oracle optimum is
used for training and grading, never as a terminal.

Protected division returns 1 when $|b|\le10^{-12}$.
"""
        ),
        code(
            """
for function in (gep.decode_gene, gep.evaluate_tree, gep.pack_by_scores):
    display(Markdown(f"### `{function.__name__}`"))
    display(Code(inspect.getsource(function), language="python"))
"""
        ),
        markdown(
            r"""
## Module 6 — Evolution and the fair budget

Evolution lexicographically minimizes mean training gap and then ORF length:

$$
\left(\frac{1}{|S|}\sum_{i\in S}g_i,\;|\operatorname{ORF}|\right).
$$

All four arms use one configuration selected by `irace` on train/validation
only. Each final run receives 65,536 raw chromosome requests, and duplicate
phenotypes still consume a raw request. The final experiment has 75 paired
master seeds per arm.
"""
        ),
        code(
            """
from src.runs import SELECTED_CONFIG_PATH, MODELS_PATH, CHECKPOINTS_PATH

selected = json.loads(Path(SELECTED_CONFIG_PATH).read_text())
display(pd.DataFrame([selected["parameters"]]))
display(Markdown("### Exact evolutionary loop"))
display(Code(inspect.getsource(gep.evolve_priority_formula), language="python"))
"""
        ),
        markdown(
            """
## Module 7 — Frozen model audit

This checks that the expected 300 confirmatory GEP models, 300 matched random
search controls, and 75 accepted-notebook continuity models are present. It also
shows elapsed time and how many distinct expressed ORFs were actually scored.
"""
        ),
        code(
            """
models = pd.read_csv(MODELS_PATH, dtype={"master_seed": str})
display(models.groupby(["family", "arm"], dropna=False).agg(
    models=("model_id", "nunique"),
    mean_minutes=("elapsed_seconds", lambda x: x.mean()/60),
    median_unique_orfs=("unique_orfs", "median"),
    median_train_gap_ppm=("train_mean_gap_ppm", "median"),
).reset_index())
assert models.groupby("family").size().to_dict() == {"AHDAS_BASE": 75, "GEP": 300, "RANDOM": 300}
"""
        ),
        markdown(
            """
## Module 8 — Advisor headline: eight bars with honest error lines

The four GEP intervals resample both the 75 paired seed blocks and the 115 ID
sibling groups. The deterministic baselines have no fake repeated runs, so their
intervals resample only the sibling groups. Bar height is mean residual gap in
ppm; lower is better.
"""
        ),
        code(
            """
from src.analysis import HEADLINE_PATH, CONTRASTS_PATH, METHOD_SUMMARY_PATH
from src.config import FIGURES_ROOT

headline = pd.read_csv(HEADLINE_PATH)
display(headline)
display(Image(filename=str(FIGURES_ROOT / "headline_id_gap_v2.png")))
"""
        ),
        markdown(
            r"""
## Module 9 — What the planned tests actually say

The primary contrast is `FULL - BASE`; negative ppm favors `FULL`. The two
secondary contrasts are Holm-corrected. Equivalence is a separate question:
the 90% interval must fall completely inside $\pm872$ ppm.
"""
        ),
        code(
            """
contrasts = pd.read_csv(CONTRASTS_PATH)
display(contrasts)
display(Image(filename=str(FIGURES_ROOT / "run_distribution_id_v2.png")))
display(Image(filename=str(FIGURES_ROOT / "generalization_regions_v2.png")))
"""
        ),
        markdown(
            """
## Module 10 — Budget, row order, and external transfer checks

The next figures answer three different questions: whether the search has
saturated, whether an expression exploits incidental item order, and whether a
Jooken-trained formula transfers without retuning to Pisinger's certified
classes.
"""
        ),
        code(
            """
for filename in ("anytime_id_v2.png", "row_order_robustness_v2.png", "pisinger_transfer_v2.png"):
    path = FIGURES_ROOT / filename
    if path.is_file():
        display(Image(filename=str(path)))
"""
        ),
        markdown(
            """
## Module 11 — Recovered expressions

The representative is selected without looking at test outcomes: among models
within one development group-standard-error of the best development mean, take
the shortest ORF, then the lexicographically smallest simplified expression,
then the lowest run index. The full 75-expression list for every arm remains in
`results/expressions_v2.csv`.
"""
        ),
        code(
            """
representatives = pd.read_csv(RESULTS_ROOT / "representative_expressions_v2.csv")
ranking = pd.read_csv(RESULTS_ROOT / "ranking_equivalence_v2.csv")
representatives = representatives.merge(
    ranking[["model_id", "ranking_equivalent_to"]], on="model_id", how="left"
)
display(representatives[[
    "arm", "run", "simplified", "orf_length", "train_mean_gap_ppm",
    "eligibility_threshold_ppm", "eligible_models", "ranking_equivalent_to"
]])

all_expressions = pd.read_csv(RESULTS_ROOT / "expressions_v2.csv")
expression_counts = (
    all_expressions[all_expressions["family"] == "GEP"]
    .groupby(["arm", "simplified"])
    .size()
    .reset_index(name="runs")
    .sort_values(["arm", "runs", "simplified"], ascending=[True, False, True])
)
display(expression_counts.groupby("arm", group_keys=False).head(10))
"""
        ),
        markdown(
            """
## Bottom line

Use the effect estimates and intervals in the contrast table, not a single best
run. A null result is still useful: it says the extra terminal information did
not reliably beat the accepted representation under a much stronger, paired,
externally checked protocol. A positive result is credible only if it survives
the same locked analysis.
"""
        ),
    ]
    notebook = nbf.v4.new_notebook(
        cells=cells,
        metadata={
            "kernelspec": {
                "display_name": "Python (.venv — ISCMI 2026 V2)",
                "language": "python",
                "name": "iscmi2026-v2",
            },
            "language_info": {"name": "python", "version": "3.14"},
        },
    )
    nbf.write(notebook, NOTEBOOK_PATH)
    return NOTEBOOK_PATH


def execute(path: Path) -> None:
    from nbclient import NotebookClient

    notebook = nbf.read(path, as_version=4)
    os.environ.setdefault("JUPYTER_CONFIG_DIR", str(PROJECT_ROOT / "tmp" / "jupyter-config"))
    os.environ.setdefault("JUPYTER_PATH", str(PROJECT_ROOT / "jupyter" / "share" / "jupyter"))
    client = NotebookClient(
        notebook,
        timeout=600,
        kernel_name="iscmi2026-v2",
        resources={"metadata": {"path": str(PROJECT_ROOT)}},
    )
    client.execute()
    nbf.write(notebook, path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    path = build()
    if args.execute:
        execute(path)
    print(path)


if __name__ == "__main__":
    main()
