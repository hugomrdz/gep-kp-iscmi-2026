"""Regenerate advisor-facing and publication figures from locked source tables."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
mpl.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .analysis import (
    ANYTIME_PATH,
    GENERALIZATION_PATH,
    HEADLINE_PATH,
    ROW_ORDER_PATH,
    RUN_SUMMARY_PATH,
    TRANSFER_SUMMARY_PATH,
)
from .config import ARM_ORDER, FIGURES_ROOT, HEADLINE_ORDER


COLORS = {
    "BASE": "#4C78A8",
    "CAP": "#59A14F",
    "SCALE": "#F28E2B",
    "FULL": "#B279A2",
    "DEF": "#B8B8B8",
    "MAXP": "#969696",
    "MAXPW": "#4D4D4D",
    "MINW": "#737373",
}
REGION_LABELS = {
    "id_test": "ID",
    "ood_n": "OOD-$n$",
    "ood_c": "OOD-$c$",
    "ood_nc": "OOD-$nc$",
}


def _style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": False,
            "svg.hashsalt": "iscmi2026-v2",
        }
    )


def _save(fig: plt.Figure, stem: str) -> None:
    FIGURES_ROOT.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        FIGURES_ROOT / f"{stem}.pdf",
        bbox_inches="tight",
        metadata={"Creator": "GEP-KP ISCMI 2026 V2", "CreationDate": None},
    )
    fig.savefig(
        FIGURES_ROOT / f"{stem}.svg",
        bbox_inches="tight",
        metadata={"Creator": "GEP-KP ISCMI 2026 V2", "Date": None},
    )
    fig.savefig(
        FIGURES_ROOT / f"{stem}.png",
        dpi=240,
        bbox_inches="tight",
        metadata={"Software": "GEP-KP ISCMI 2026 V2"},
    )
    plt.close(fig)


def headline_bar() -> None:
    frame = pd.read_csv(HEADLINE_PATH).set_index("method").loc[list(HEADLINE_ORDER)].reset_index()
    x = np.arange(len(frame))
    y = frame["mean_gap_ppm"].to_numpy()
    errors = np.vstack(
        (
            y - frame["ci95_low_ppm"].to_numpy(),
            frame["ci95_high_ppm"].to_numpy() - y,
        )
    )
    fig, ax = plt.subplots(figsize=(7.2, 4.1))
    bars = ax.bar(
        x,
        y,
        color=[COLORS[value] for value in frame["method"]],
        edgecolor="white",
        linewidth=0.7,
        width=0.72,
        zorder=2,
    )
    ax.errorbar(
        x,
        y,
        yerr=errors,
        fmt="none",
        ecolor="#222222",
        elinewidth=1.1,
        capsize=3,
        capthick=1.1,
        zorder=3,
    )
    ax.axvline(3.5, color="#BDBDBD", linewidth=0.8)
    ax.set_xticks(x, frame["method"])
    ax.set_ylabel("Mean residual optimality gap (ppm; lower is better)")
    ax.set_title("GEP terminal ablation and deterministic rankers on the locked ID test")
    ax.yaxis.grid(True, color="#E1E1E1", linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    span = max(frame["ci95_high_ppm"].max(), y.max())
    for bar, value in zip(bars, y, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.025 * span,
            f"{value:,.0f}",
            ha="center",
            va="bottom",
            fontsize=7,
        )
    ax.text(
        0,
        -0.23,
        "345 instances in 115 sibling groups; 75 paired GEP seeds; 65,536 raw requests. "
        "GEP: 95% crossed seed/group bootstrap; fixed rules: 95% group bootstrap.",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=7.5,
    )
    _save(fig, "headline_id_gap_v2")


def anytime_plot() -> None:
    frame = pd.read_csv(ANYTIME_PATH)
    frame = frame[frame["partition"] == "id_test"]
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    for arm in ARM_ORDER:
        subset = frame[frame["arm"] == arm].sort_values("checkpoint")
        ax.plot(
            subset["checkpoint"],
            subset["median_run_mean_gap_ppm"],
            marker="o",
            linewidth=1.8,
            markersize=4,
            color=COLORS[arm],
            label=arm,
        )
        ax.fill_between(
            subset["checkpoint"].to_numpy(),
            subset["ci95_low_ppm"].to_numpy(),
            subset["ci95_high_ppm"].to_numpy(),
            color=COLORS[arm],
            alpha=0.12,
            linewidth=0,
        )
    ax.set_xscale("log", base=2)
    ax.set_xlabel("Raw chromosome requests")
    ax.set_ylabel("Median run mean ID gap (ppm)")
    ax.set_title("Anytime performance on the locked ID test")
    ax.grid(True, axis="y", color="#E1E1E1", linewidth=0.7)
    ax.legend(ncol=4, frameon=False, loc="best")
    _save(fig, "anytime_id_v2")


def generalization_plot() -> None:
    frame = pd.read_csv(GENERALIZATION_PATH)
    frame = frame[frame["label"].isin(HEADLINE_ORDER)].copy()
    frame["region_label"] = frame["partition"].map(REGION_LABELS)
    region_order = list(REGION_LABELS.values())
    x = np.arange(len(region_order))
    offsets = np.linspace(-0.30, 0.30, len(HEADLINE_ORDER))
    fig, ax = plt.subplots(figsize=(8.0, 4.4))
    for offset, method in zip(offsets, HEADLINE_ORDER, strict=True):
        subset = frame[frame["label"] == method].set_index("region_label").reindex(region_order)
        ax.plot(
            x + offset,
            subset["mean_gap_ppm"],
            marker="o",
            linewidth=0,
            markersize=5,
            color=COLORS[method],
            label=method,
        )
    ax.set_xticks(x, region_order)
    ax.set_ylabel("Mean residual optimality gap (ppm)")
    ax.set_title("Generalization by locked Jooken region")
    ax.yaxis.grid(True, color="#E1E1E1", linewidth=0.7)
    ax.legend(ncol=4, frameon=False, loc="upper left")
    _save(fig, "generalization_regions_v2")


def run_distribution_plot() -> None:
    frame = pd.read_csv(RUN_SUMMARY_PATH)
    frame = frame[(frame["family"] == "GEP") & (frame["partition"] == "id_test")]
    values = [frame.loc[frame["arm"] == arm, "gap_mean_ppm"].to_numpy() for arm in ARM_ORDER]
    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    box = ax.boxplot(values, tick_labels=ARM_ORDER, patch_artist=True, showfliers=False)
    for patch, arm in zip(box["boxes"], ARM_ORDER, strict=True):
        patch.set_facecolor(COLORS[arm])
        patch.set_alpha(0.35)
        patch.set_edgecolor(COLORS[arm])
    rng = np.random.default_rng(20260906)
    for index, (arm, array) in enumerate(zip(ARM_ORDER, values, strict=True), start=1):
        jitter = rng.uniform(-0.12, 0.12, size=len(array))
        ax.scatter(
            index + jitter,
            array,
            s=10,
            color=COLORS[arm],
            alpha=0.55,
            linewidth=0,
        )
    ax.set_ylabel("Mean ID gap per evolutionary run (ppm)")
    ax.set_title("All 75 locked runs per terminal arm")
    ax.yaxis.grid(True, color="#E1E1E1", linewidth=0.7)
    _save(fig, "run_distribution_id_v2")


def row_order_plot() -> None:
    frame = pd.read_csv(ROW_ORDER_PATH)
    frame = frame[
        frame["label"].isin(HEADLINE_ORDER) & frame["partition"].eq("id_test")
    ]
    summary = frame.groupby("label", sort=False).agg(
        mean_sd=("permutation_sd_gap_ppm", "mean"),
        p95_sd=("permutation_sd_gap_ppm", lambda value: np.quantile(value, 0.95)),
    ).reindex(HEADLINE_ORDER)
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    x = np.arange(len(summary))
    ax.bar(x, summary["mean_sd"], color=[COLORS[value] for value in summary.index], width=0.72)
    ax.scatter(x, summary["p95_sd"], marker="_", color="#222222", s=80, label="95th percentile")
    ax.set_xticks(x, summary.index)
    ax.set_ylabel("SD across original + 10 row orders (ppm)")
    ax.set_title("Sensitivity to incidental item-row order")
    ax.yaxis.grid(True, color="#E1E1E1", linewidth=0.7)
    ax.legend(frameon=False)
    _save(fig, "row_order_robustness_v2")


def transfer_plot() -> None:
    if not TRANSFER_SUMMARY_PATH.is_file():
        return
    frame = pd.read_csv(TRANSFER_SUMMARY_PATH)
    frame = frame[frame["label"].isin([*ARM_ORDER, "MAXPW"])]
    classes = sorted(frame["region"].unique())
    x = np.arange(len(classes))
    fig, ax = plt.subplots(figsize=(9.0, 4.5))
    offsets = np.linspace(-0.24, 0.24, 5)
    for offset, method in zip(offsets, [*ARM_ORDER, "MAXPW"], strict=True):
        subset = frame[frame["label"] == method].set_index("region").reindex(classes)
        ax.scatter(
            x + offset,
            subset["mean_gap_ppm"],
            s=20,
            color=COLORS[method],
            label=method,
        )
    ax.set_xticks(x, [value.replace("type_", "").replace("_", " ") for value in classes], rotation=40, ha="right")
    ax.set_ylabel("Mean transfer gap (ppm)")
    ax.set_title("Frozen Jooken-trained rankers on Pisinger classes")
    ax.yaxis.grid(True, color="#E1E1E1", linewidth=0.7)
    ax.legend(ncol=5, frameon=False)
    _save(fig, "pisinger_transfer_v2")


def main() -> None:
    _style()
    headline_bar()
    anytime_plot()
    generalization_plot()
    run_distribution_plot()
    row_order_plot()
    transfer_plot()
    print(f"Figures written to {FIGURES_ROOT}")


if __name__ == "__main__":
    main()
