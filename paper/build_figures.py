"""Build the three corrected ISCMI 2026 manuscript PDFs from frozen results.

Outputs are ``fig01.pdf``, ``fig02.pdf``, and ``fig03.pdf`` in the repository
root, or in the directory specified by ``--output-dir``. This script is
separate from the protocol-locked experiment code.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.text import Text
from matplotlib.transforms import Bbox
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"

ARM_ORDER = ["BASE", "CAP", "SCALE", "FULL"]
METHOD_ORDER = ARM_ORDER + ["DEF", "MAXP", "MAXPW", "MINW"]
REGION_ORDER = ["ID", "OOD-n", "OOD-c", "OOD-nc"]

COLORS = {
    "BASE": "#4C78A8",
    "CAP": "#59A14F",
    "SCALE": "#F28E2B",
    "FULL": "#B07AA1",
    "DEF": "#BAB0AC",
    "MAXP": "#969696",
    "MAXPW": "#4D4D4D",
    "MINW": "#7A7A7A",
}


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "font.size": 7.2,
            "axes.titlesize": 7.6,
            "axes.labelsize": 7.2,
            "xtick.labelsize": 6.6,
            "ytick.labelsize": 6.6,
            "legend.fontsize": 6.2,
            "axes.linewidth": 0.7,
            "lines.linewidth": 1.25,
            "lines.markersize": 3.4,
            "xtick.major.width": 0.7,
            "ytick.major.width": 0.7,
            "xtick.major.size": 2.5,
            "ytick.major.size": 2.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.axisbelow": True,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "grid.color": "#D9D9D9",
            "grid.linewidth": 0.45,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def save_figure(
    fig: mpl.figure.Figure, stem: str, filename: str, output_dir: Path,
    *, bbox_inches: str | Bbox = "tight", pad_inches: float = 0.025,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "Title": stem.replace("_", " "),
        "Author": "Hugo Abel Moreno-Rodriguez and Jose Carlos Ortiz-Bayliss",
        "Subject": "ISCMI 2026 GEP knapsack experiment",
    }
    fig.savefig(
        output_dir / filename,
        bbox_inches=bbox_inches,
        pad_inches=pad_inches,
        metadata=metadata,
    )
    plt.close(fig)


def add_panel_labels(fig: mpl.figure.Figure, fontsize: float) -> None:
    """Align panel letters beneath the existing axis and tick labels."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    bottom = min(ax.get_tightbbox(renderer).y0 for ax in fig.axes)
    bottom_fraction = (bottom - 6 * fig.dpi / 72) / fig.bbox.height
    for ax, letter in zip(fig.axes, "abc"):
        position = ax.get_position()
        fig.text(
            position.x0 + position.width / 2, bottom_fraction, f"({letter})",
            ha="center", va="top", fontsize=fontsize, fontweight="bold",
        )


def build_study_flow(output_dir: Path = ROOT) -> None:
    fig, ax = plt.subplots(figsize=(7.05, 1.40))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    labels = [
        "Development data\n1,038 train\n345 validation",
        "Short irace race\n2,000 trials\n16,384 requests",
        "Full-budget check\n5 settings, 4 arms\n10 fresh seeds",
        "Locked final training\n75 runs per arm\n65,536 requests",
        "Sealed Jooken tests\n345 ID cases\n1,249 OOD cases",
    ]
    fills = ["#E8F1F8", "#E8F1F8", "#E8F1F8", "#F3EAF1", "#EEEEEE"]
    edges = [COLORS["BASE"], COLORS["BASE"], COLORS["BASE"], COLORS["FULL"], "#555555"]
    centers = np.linspace(0.1, 0.9, len(labels))
    width, height = 0.165, 0.50

    for idx, (x, label, fill, edge) in enumerate(zip(centers, labels, fills, edges)):
        box = FancyBboxPatch(
            (x - width / 2, 0.33),
            width,
            height,
            boxstyle="round,pad=0.012,rounding_size=0.015",
            linewidth=0.85,
            edgecolor=edge,
            facecolor=fill,
        )
        ax.add_patch(box)
        ax.text(x, 0.58, label, ha="center", va="center", fontsize=6.25, linespacing=1.12)
        if idx < len(labels) - 1:
            arrow = FancyArrowPatch(
                (x + width / 2 + 0.006, 0.58),
                (centers[idx + 1] - width / 2 - 0.006, 0.58),
                arrowstyle="-|>",
                mutation_scale=7,
                linewidth=0.8,
                color="#666666",
            )
            ax.add_patch(arrow)

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    original_bounds = fig.get_tightbbox(renderer)
    artwork_bounds = Bbox.union([
        artist.get_window_extent(renderer)
        for artist in list(ax.patches) + list(ax.texts)
    ]).transformed(fig.dpi_scale_trans.inverted())
    # Preserve the approved width and diagram scale, trimming only vertical
    # whitespace. The 2.5 pt margin includes the 0.425 pt half-width stroke.
    margin = 2.5 / 72
    crop = Bbox.from_extents(
        original_bounds.x0 - 0.025,
        artwork_bounds.y0 - margin,
        original_bounds.x1 + 0.025,
        artwork_bounds.y1 + margin,
    )
    save_figure(fig, "study_flow", "fig01.pdf", output_dir, bbox_inches=crop, pad_inches=0)


def build_headline_effects(output_dir: Path = ROOT) -> None:
    headline = pd.read_csv(RESULTS / "figure_data" / "headline_bar_v2.csv")
    contrasts = pd.read_csv(RESULTS / "confirmatory" / "contrasts_v2.csv")
    headline["method"] = pd.Categorical(headline["method"], METHOD_ORDER, ordered=True)
    headline = headline.sort_values("method")

    fig = plt.figure(figsize=(7.05, 3.05))
    grid = fig.add_gridspec(1, 2, width_ratios=[1.58, 1.0], wspace=0.29)
    ax = fig.add_subplot(grid[0, 0])
    fx = fig.add_subplot(grid[0, 1])

    x = np.arange(len(headline))
    means = headline["mean_gap_ppm"].to_numpy()
    low = means - headline["ci95_low_ppm"].to_numpy()
    high = headline["ci95_high_ppm"].to_numpy() - means
    colors = [COLORS[str(method)] for method in headline["method"]]
    ax.bar(x, means, color=colors, width=0.72, edgecolor="white", linewidth=0.35)
    ax.errorbar(
        x,
        means,
        yerr=np.vstack([low, high]),
        fmt="none",
        ecolor="#202020",
        elinewidth=0.85,
        capsize=2.2,
        capthick=0.85,
    )
    for xpos, value in zip(x, means):
        ax.text(xpos, value + 510, f"{value:,.0f}", ha="center", va="bottom", fontsize=5.9)
    ax.axvline(3.5, color="#BDBDBD", linewidth=0.7)
    ax.set_xticks(x, [str(v) for v in headline["method"]], rotation=25, ha="right")
    ax.set_ylabel("Mean ID optimality gap (ppm; lower is better)")
    ax.set_ylim(0, 25_000)
    ax.text(
        0.02,
        0.95,
        "GEP",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=6.2,
        color="#555555",
    )
    ax.text(
        0.59,
        0.95,
        "Fixed rules",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=6.2,
        color="#555555",
    )

    labels = ["FULL - BASE", "FULL - CAP", "FULL - SCALE"]
    d = contrasts.set_index("contrast").loc[labels].reset_index()
    y = np.arange(len(d))[::-1]
    fx.axvspan(-872, 872, color="#EFEFEF", zorder=0)
    fx.axvline(0, color="#555555", linewidth=0.75)
    fx.axvline(-872, color="#AAAAAA", linewidth=0.55, linestyle="--")
    fx.axvline(872, color="#AAAAAA", linewidth=0.55, linestyle="--")
    estimates = d["estimate_ppm"].to_numpy()
    err_low = estimates - d["ci95_low_ppm"].to_numpy()
    err_high = d["ci95_high_ppm"].to_numpy() - estimates
    fx.errorbar(
        estimates,
        y,
        xerr=np.vstack([err_low, err_high]),
        fmt="o",
        color=COLORS["FULL"],
        ecolor="#333333",
        elinewidth=0.9,
        capsize=2.4,
        markersize=4.0,
    )
    for estimate, ypos in zip(estimates, y):
        fx.text(estimate, ypos + 0.22, f"{estimate:+.0f}", ha="center", va="bottom", fontsize=5.9)
    fx.set_yticks(y, [value.replace("FULL - ", "vs. ") for value in labels])
    fx.set_xlabel("Paired mean difference (ppm)")
    fx.set_xlim(-1_450, 1_050)
    fx.set_ylim(-0.65, 2.65)
    fx.text(
        0.02,
        0.04,
        "negative favors FULL; gray = +/-872 ppm",
        transform=fx.transAxes,
        fontsize=5.8,
        ha="left",
        va="bottom",
        color="#555555",
    )

    fig.subplots_adjust(left=0.075, right=0.992, bottom=0.19, top=0.91)
    # Materialize tick labels before enlarging every text artist. Keep axes
    # positions, data, and all other plot geometry identical to the original.
    fig.canvas.draw()
    for text in fig.findobj(Text):
        text.set_fontsize(text.get_fontsize() * 1.2)
    add_panel_labels(fig, fontsize=9.12)
    save_figure(fig, "headline_effects", "fig02.pdf", output_dir)


def build_generalization_budget_robustness(output_dir: Path = ROOT) -> None:
    generalization = pd.read_csv(RESULTS / "figure_data" / "generalization_v2.csv")
    anytime = pd.read_csv(RESULTS / "figure_data" / "anytime_v2.csv")
    row_order = pd.read_csv(RESULTS / "confirmatory" / "row_order_summary_v2.csv")
    method_summary = pd.read_csv(RESULTS / "confirmatory" / "method_summary_v2.csv")

    fig = plt.figure(figsize=(7.05, 2.72))
    grid = fig.add_gridspec(1, 3, width_ratios=[1.22, 1.25, 0.86], wspace=0.36)
    ax_g = fig.add_subplot(grid[0, 0])
    ax_a = fig.add_subplot(grid[0, 1])
    ax_r = fig.add_subplot(grid[0, 2])

    # (a) Within-Jooken generalization, focusing on GEP and the strongest
    # deterministic mean-gap baseline from the ID test.
    methods = ARM_ORDER + ["MAXPW"]
    for method in methods:
        family = "GEP" if method in ARM_ORDER else "baseline"
        part = generalization[(generalization["label"] == method) & (generalization["family"] == family)].copy()
        part["region"] = pd.Categorical(part["region"], REGION_ORDER, ordered=True)
        part = part.sort_values("region")
        ax_g.plot(
            np.arange(len(part)),
            part["mean_gap_ppm"],
            marker="o" if method in ARM_ORDER else "s",
            linestyle="-" if method in ARM_ORDER else "--",
            color=COLORS[method],
            label=method,
        )
    ax_g.set_xticks(np.arange(4), REGION_ORDER, rotation=24, ha="right")
    ax_g.set_ylabel("Mean gap (ppm)")
    ax_g.set_ylim(2_500, 13_200)
    ax_g.legend(ncol=2, loc="upper left", frameon=False, handlelength=1.7, columnspacing=0.8)

    # (b) Development of the ID result as the raw request budget grows.
    id_anytime = anytime[anytime["partition"] == "id_test"].copy()
    checkpoints = sorted(id_anytime["checkpoint"].unique())
    xpos = np.arange(len(checkpoints))
    for arm in ARM_ORDER:
        part = id_anytime[id_anytime["arm"] == arm].set_index("checkpoint").loc[checkpoints]
        ax_a.plot(
            xpos,
            part["median_run_mean_gap_ppm"],
            marker="o",
            color=COLORS[arm],
            label=arm,
        )
    ax_a.axhline(
        7_695.286,
        color=COLORS["MAXPW"],
        linestyle="--",
        linewidth=0.8,
        label="MAXPW",
    )
    ax_a.set_xticks(xpos, ["1.9k", "4.1k", "16.4k", "21.3k", "32.8k", "65.5k"], rotation=30, ha="right")
    ax_a.set_xlabel("Raw chromosome requests")
    ax_a.set_ylabel("Median run mean gap (ppm)")
    ax_a.set_ylim(4_300, 8_050)

    # (c) Change in the mean when ten deterministic row permutations are
    # combined with the canonical order.
    percent_changes: list[float] = []
    for arm in ARM_ORDER:
        all_orders = row_order[
            (row_order["family"] == "GEP")
            & (row_order["arm"] == arm)
            & (row_order["partition"] == "id_test")
        ]["permutation_mean_gap_ppm"].mean()
        original = method_summary[
            (method_summary["family"] == "GEP")
            & (method_summary["arm"] == arm)
            & (method_summary["partition"] == "id_test")
        ]["mean_gap_ppm"].iloc[0]
        percent_changes.append(100.0 * (all_orders / original - 1.0))
    bars = ax_r.bar(
        np.arange(4),
        percent_changes,
        color=[COLORS[arm] for arm in ARM_ORDER],
        width=0.7,
        edgecolor="white",
        linewidth=0.3,
    )
    for bar, value in zip(bars, percent_changes):
        ax_r.text(bar.get_x() + bar.get_width() / 2, value + 0.7, f"+{value:.1f}%", ha="center", va="bottom", fontsize=5.8)
    ax_r.axhline(0, color="#555555", linewidth=0.65)
    ax_r.set_xticks(np.arange(4), ARM_ORDER, rotation=28, ha="right")
    ax_r.set_ylabel("Gap increase over original order")
    ax_r.set_ylim(0, 29)

    fig.subplots_adjust(left=0.07, right=0.995, bottom=0.23, top=0.91)
    add_panel_labels(fig, fontsize=7.6)
    save_figure(fig, "generalization_budget_robustness", "fig03.pdf", output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT,
        help="Directory for fig01.pdf, fig02.pdf, and fig03.pdf (default: repository root).",
    )
    args = parser.parse_args()
    configure_style()
    build_study_flow(args.output_dir)
    build_headline_effects(args.output_dir)
    build_generalization_budget_robustness(args.output_dir)
    print(f"Wrote fig01.pdf, fig02.pdf, and fig03.pdf to {args.output_dir}")


if __name__ == "__main__":
    main()
