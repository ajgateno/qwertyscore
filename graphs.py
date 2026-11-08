"""Plot qwertyscore against the other scorers, one PNG per dataset, into ./graphs.

The scorers use unrelated units (beats, cost points, carpalx effort, ms), so
each is plotted as its percentile within the vocabulary on one shared axis:
0 = the easiest word in the vocabulary by that scorer, 100 = the hardest.
"""

import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

from datasets import DATA, ROOT, ensure_datasets  # noqa: E402

GRAPHS = ROOT / "graphs"

# Validated categorical palette (light), fixed order; marker shapes are the
# secondary encoding so identity never rests on color alone.
SERIES = {
    "qwertyscore": dict(label="qwertyscore (beats)", color="#2a78d6", marker="o"),
    "word_cost": dict(label="word-cost (cost points)", color="#eb6834", marker="s"),
    "carpalx": dict(label="carpalx (triad effort; needs 3+ letters)", color="#1baf7a", marker="^"),
    "typeracer": dict(label="TypeRacer1000 (median ms typed)", color="#eda100", marker="D"),
}
SURFACE, INK, INK_2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"

CHARTS = {
    "common": ("The 100 most common English words",
               "in frequency order (google-10000-english)"),
    "qwertyscore": ("The 100 words with the lowest qwertyscore",
                    "easiest first; ties go to the more common word"),
    "word_cost": ("The 100 words with the lowest word-cost score",
                  "easiest first; ties go to the more common word"),
    "carpalx": ("The 100 words with the lowest carpalx effort",
                "easiest first; words of 3+ letters only"),
    "typeracer": ("The 100 fastest-typed words in TypeRacer1000",
                  "lowest median ms first; words with 20+ timings only"),
}


def _pct(value: str) -> float:
    return float(value) if value != "" else math.nan


def plot(name: str, csv_path: Path, out: Path, vocab_size: int) -> None:
    with csv_path.open() as f:
        rows = list(csv.DictReader(f))
    words = [r["word"] for r in rows]
    x = range(len(words))
    title, subtitle = CHARTS[name]

    fig, ax = plt.subplots(figsize=(22, 7.5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    # Draw the series that ordered this chart last, so it sits on top.
    order = [k for k in SERIES if k != name] + ([name] if name in SERIES else [])
    values = {k: [_pct(r[f"{k}_pct"]) for r in rows] for k in SERIES}
    y_max = max(v for vs in values.values() for v in vs if not math.isnan(v))
    for key in order:
        s = SERIES[key]
        lead = key == name
        ax.plot(
            x, values[key],
            color=s["color"], marker=s["marker"], label=s["label"],
            linewidth=2.2 if lead else 1.2, alpha=1 if lead else 0.75,
            markersize=6 if lead else 5,
            markeredgecolor=SURFACE, markeredgewidth=0.8, zorder=3 if lead else 2,
        )

    ax.set_xticks(list(x), words, rotation=90, fontsize=8.5, color=INK_2)
    ax.set_xlim(-0.8, len(words) - 0.2)
    # Fit the axis to the data: highest point plus a 10% buffer (at least 2
    # points), capped at 100 since percentiles cannot go higher.
    top = min(100, y_max + max(2, 0.1 * y_max))
    ax.set_ylim(-0.02 * top, top)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6, steps=[1, 2, 2.5, 5, 10]))
    ax.tick_params(axis="y", labelsize=9, colors=MUTED)
    ax.tick_params(axis="x", length=0)
    ax.tick_params(axis="y", length=0)
    ax.set_ylabel("Percentile within vocabulary  (0 = easiest, 100 = hardest)",
                  fontsize=10, color=INK_2)
    ax.grid(axis="y", color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)

    # Legend in the original series order, so it reads the same on every chart.
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(
        [by_label[SERIES[k]["label"]] for k in SERIES],
        [SERIES[k]["label"] for k in SERIES],
        loc="lower left", bbox_to_anchor=(0, 1.0), ncol=4, frameon=False,
        fontsize=10, labelcolor=INK, handlelength=2.5,
    )
    fig.suptitle(title, x=0.01, y=0.985, ha="left", fontsize=15,
                 fontweight="bold", color=INK)
    fig.text(0.01, 0.94, f"{subtitle}. Each scorer's score ranked across "
             f"{vocab_size:,} common English words; gaps mean that scorer has "
             "no value.", ha="left", fontsize=10, color=INK_2)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)
    print(f"wrote {out.relative_to(ROOT)}")


def main() -> None:
    paths = ensure_datasets()
    with (DATA / "scores.csv").open() as f:
        vocab_size = sum(1 for _ in f) - 1
    GRAPHS.mkdir(exist_ok=True)
    for name, csv_path in paths.items():
        plot(name, csv_path, GRAPHS / f"{csv_path.stem}.png", vocab_size)


if __name__ == "__main__":
    main()
