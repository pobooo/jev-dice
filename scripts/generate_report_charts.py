#!/usr/bin/env python3
"""Generate the Chinese charts used by the HTML report (pass chart names to build a subset)."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "docs" / "zh" / "img"
NUMBERS = ["1", "2", "3", "4", "5", "6"]
ANIMALS = ["cat", "dog", "bird", "fish", "horse", "cow"]
PROMPTS = ["P1", "P2", "P3"]
TITLES = {"P1": "基础题", "P2": "自然顺序", "P3": "打乱顺序"}
ORDERS = {
    "numbers": {
        "P1": NUMBERS,
        "P2": NUMBERS,
        "P3": ["4", "2", "6", "1", "5", "3"],
    },
    "animals": {
        "P1": ANIMALS,
        "P2": ANIMALS,
        "P3": ["fish", "dog", "cow", "cat", "horse", "bird"],
    },
}

plt.rcParams.update(
    {
        "font.family": "Arial Unicode MS",
        "svg.fonttype": "none",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.unicode_minus": False,
    }
)


def load(dirname: str) -> dict:
    path = ROOT / "results" / dirname / "EXPERIMENT_RECORD.json"
    return json.loads(path.read_text())


def save(fig: plt.Figure, name: str) -> None:
    fig.savefig(IMG / name, format="svg", bbox_inches="tight")
    plt.close(fig)


def by_content() -> None:
    rows = [
        ("数字骰子", NUMBERS, load("dice_numbers")),
        ("动物骰子", ANIMALS, load("dice_animals")),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(11, 5.6), sharey=True)
    x = np.arange(6)
    for row, (row_name, labels, data) in enumerate(rows):
        for col, prompt in enumerate(PROMPTS):
            ax = axes[row, col]
            values = [data["prompts"][prompt]["mean_p"][label] for label in labels]
            colors = ["#2c648a"] * 6
            colors[int(np.argmax(values))] = "#991f1f"
            ax.bar(x, values, width=0.72, color=colors)
            ax.axhline(1 / 6, color="#888", linestyle="--", linewidth=0.8)
            ax.set_xticks(x, labels, fontsize=8)
            ax.set_ylim(0, 1)
            ax.set_title(TITLES[prompt], fontsize=10)
            ax.set_xlabel("骰面内容", fontsize=9)
            if col == 0:
                ax.set_ylabel(f"{row_name}\n平均概率", fontsize=9)
    fig.suptitle("按骰面内容比较平均概率（横轴表示骰面内容；虚线 = 1/6）", fontsize=12)
    fig.tight_layout()
    save(fig, "by-key.svg")


def by_position() -> None:
    specs = [
        ("数字骰子", "numbers", load("dice_numbers")),
        ("动物骰子", "animals", load("dice_animals")),
    ]
    colors = {"P1": "#2c648a", "P2": "#d1842b", "P3": "#9b2424"}
    fig, axes = plt.subplots(1, 2, figsize=(9, 4.5), sharey=True)
    positions = np.arange(1, 7)
    for ax, (title, kind, data) in zip(axes, specs):
        for prompt in PROMPTS:
            order = ORDERS[kind][prompt]
            values = [data["prompts"][prompt]["mean_p"][label] for label in order]
            ax.plot(
                positions,
                values,
                marker="o",
                linewidth=1.8,
                color=colors[prompt],
                label=TITLES[prompt],
            )
        ax.axhline(1 / 6, color="#888", linestyle=":", linewidth=0.9)
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("选项在题目中的位置", fontsize=9)
        ax.set_xticks(positions)
        ax.set_ylim(0, 1)
    axes[0].set_ylabel("平均概率", fontsize=9)
    axes[1].legend(frameon=False, fontsize=8)
    fig.suptitle("按选项位置比较平均概率", fontsize=12)
    fig.tight_layout()
    save(fig, "by-position.svg")


def moved_one() -> None:
    original = load("dice_numbers")["prompts"]["P3"]["mean_p"]
    alternate = load("dice_numbers_reshuffle")["prompts"]["P3alt"]["mean_p"]
    original_order = ["4", "2", "6", "1", "5", "3"]
    alternate_order = ["5", "3", "2", "6", "1", "4"]
    positions = np.arange(1, 7)

    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(
        positions,
        [original[label] for label in original_order],
        marker="o",
        linewidth=2,
        color="#2c5f8a",
        label="原顺序 [4,2,6,1,5,3]",
    )
    ax.plot(
        positions,
        [alternate[label] for label in alternate_order],
        marker="o",
        linewidth=2,
        color="#b33a3a",
        label="新顺序 [5,3,2,6,1,4]",
    )
    ax.axhline(1 / 6, color="#888", linestyle=":", linewidth=0.9)
    ax.annotate("数字 1", (4, original["1"]), xytext=(0, 10), textcoords="offset points",
                ha="center", color="#2c5f8a", fontsize=9)
    ax.annotate("数字 1", (5, alternate["1"]), xytext=(0, 10), textcoords="offset points",
                ha="center", color="#b33a3a", fontsize=9)
    ax.set_title("把数字 1 从第 4 位移到第 5 位后，概率高点是否跟着移动", fontsize=12)
    ax.set_xlabel("选项在题目中的位置", fontsize=9)
    ax.set_ylabel("平均概率", fontsize=9)
    ax.set_xticks(positions)
    ax.set_ylim(0, 0.6)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    save(fig, "p3alt.svg")


def descriptions() -> None:
    data = load("animal_guess")
    natural = data["orders"]["natural"]["by_clarity"]
    shuffled = data["orders"]["shuffled"]["by_clarity"]
    by_target = data["paired"]["by_target"]
    levels = ["clear", "medium", "ambiguous"]
    level_names = ["清晰", "中等", "模糊"]
    x = np.arange(3)
    w = 0.36

    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.2))
    for ax, field, ylabel, title in [
        (axes[0], "accuracy", "准确率", "不同描述难度的准确率"),
        (axes[1], "mean_p_correct", "正确动物的平均概率", "正确答案得到的概率"),
    ]:
        ax.bar(x - w / 2, [natural[lv][field] for lv in levels], w,
               color="#2c5f8a", label="自然顺序")
        ax.bar(x + w / 2, [shuffled[lv][field] for lv in levels], w,
               color="#b33a3a", label="打乱顺序")
        ax.set_xticks(x, level_names)
        ax.set_ylim(0, 1.08)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
    axes[0].legend(frameon=False, fontsize=8)

    labels = [
        f"{animal}\n{by_target[animal]['natural_position']}→{by_target[animal]['shuffled_position']}"
        for animal in ANIMALS
    ]
    delta = [by_target[animal]["mean_delta_p_correct"] for animal in ANIMALS]
    axes[2].bar(labels, delta, color=["#2c5f8a" if v >= 0 else "#b33a3a" for v in delta])
    axes[2].axhline(0, color="#555", lw=1)
    axes[2].set_ylabel("正确动物的概率变化")
    axes[2].set_title("换顺序后的变化")

    fig.suptitle("根据描述猜动物（72 句 × 2 种顺序）", fontsize=12)
    fig.tight_layout()
    save(fig, "descriptions.svg")


def favorite() -> None:
    data = load("animal_favorite")
    palette = {
        "cat": "#c47a12",
        "dog": "#1f4e79",
        "bird": "#2a7a4b",
        "fish": "#3d7ea6",
        "horse": "#8a5a2c",
        "cow": "#9b2c2c",
    }
    positions = range(1, 7)

    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.4))
    for animal in ANIMALS:
        axes[0].plot(
            positions,
            data["by_animal_and_position"][animal]["mean_p_when_at_position"],
            "-o",
            ms=4,
            color=palette[animal],
            label=animal,
        )
    axes[0].axhline(1 / 6, color="#666", ls=":", lw=1)
    axes[0].set_xticks(list(positions))
    axes[0].set_ylim(0, 1)
    axes[0].set_xlabel("动物在列表中的位置")
    axes[0].set_ylabel("平均概率")
    axes[0].set_title("位置怎样改变动物的概率")
    axes[0].legend(frameon=False, ncol=2, fontsize=8)

    counts = [data["choice_by_animal"][animal] for animal in ANIMALS]
    axes[1].bar(ANIMALS, counts, color=[palette[animal] for animal in ANIMALS])
    axes[1].set_ylabel("720 次中被选次数")
    axes[1].set_title("全部排列下的最终选择")
    axes[1].set_ylim(0, 720)
    for i, count in enumerate(counts):
        axes[1].text(i, count + 12, str(count), ha="center", fontsize=8)

    fig.suptitle("“你最喜欢哪种动物？”（全部 720 种排列）", fontsize=12)
    fig.tight_layout()
    save(fig, "favorite.svg")


def noul_calibration() -> None:
    path = ROOT / "results" / "noul_calibration" / "summary.json"
    dice = list(json.loads(path.read_text())["dice"].values())
    x = np.arange(len(dice))
    labels = [str(d["n_sides"]) for d in dice]
    mean = np.array([d["mean_noul"] for d in dice])
    err = [mean - [d["min_face_mean"] for d in dice], [d["max_face_mean"] for d in dice] - mean]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    ax = axes[0]
    ax.plot(x, [d["true_p"] for d in dice], "--o", color="#888", ms=4, label="真实概率 1/N")
    ax.errorbar(x, mean, yerr=err, fmt="-o", color="#991f1f", capsize=3, lw=1.8, label="Jev 给出的平均概率")
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 0.55)
    ax.set_xlabel("骰子面数 N")
    ax.set_ylabel("每一面的概率")
    ax.set_title("真实概率与 Jev 的估计")
    ax.legend(frameon=False, fontsize=8)

    ax = axes[1]
    sums = [d["sum_of_means"] for d in dice]
    ax.bar(x, sums, width=0.66, color=["#2c648a" if s < 1 else "#991f1f" for s in sums])
    ax.axhline(1, color="#555", ls="--", lw=1)
    for i, s in enumerate(sums):
        ax.text(i, s + 0.03, f"{s:.2f}", ha="center", fontsize=8)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 2.1)
    ax.set_xlabel("骰子面数 N")
    ax.set_ylabel("各面概率之和")
    ax.set_title("各面概率加起来（公平时应为 1）")

    fig.suptitle("Noul 校准：公平 N 面骰每一面朝上的概率（每种骰子 100 次）", fontsize=12)
    fig.tight_layout()
    save(fig, "noul-calibration.svg")


CHARTS = {
    "by-key": by_content,
    "by-position": by_position,
    "p3alt": moved_one,
    "descriptions": descriptions,
    "favorite": favorite,
    "noul-calibration": noul_calibration,
}


if __name__ == "__main__":
    import sys

    for name in sys.argv[1:] or CHARTS:
        CHARTS[name]()
