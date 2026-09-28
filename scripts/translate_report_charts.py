#!/usr/bin/env python3
"""Create English copies of the report SVG charts by translating their labels."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "zh" / "img"
DST = ROOT / "docs" / "img"

LABELS = {
    "按骰面内容比较平均概率（横轴表示骰面内容；虚线 = 1/6）": "Mean probability by die face (x-axis = face; dashed line = 1/6)",
    "骰面内容": "Die face",
    "数字骰子": "Number die",
    "动物骰子": "Animal die",
    "平均概率": "Mean probability",
    "基础题": "Base",
    "自然顺序": "Natural order",
    "打乱顺序": "Shuffled order",
    "按选项位置比较平均概率": "Mean probability by option position",
    "选项在题目中的位置": "Position in the option list",
    "把数字 1 从第 4 位移到第 5 位后，概率高点是否跟着移动": "Does the second peak follow the number 1 from position 4 to 5?",
    "数字 1": "number 1",
    "原顺序 [4,2,6,1,5,3]": "Original [4,2,6,1,5,3]",
    "新顺序 [5,3,2,6,1,4]": "New [5,3,2,6,1,4]",
    "根据描述猜动物（72 句 × 2 种顺序）": "Guess the animal from a description (72 sentences × 2 orders)",
    "不同描述难度的准确率": "Accuracy by clarity",
    "准确率": "Accuracy",
    "清晰": "Clear",
    "中等": "Medium",
    "模糊": "Vague",
    "正确答案得到的概率": "Probability of the correct answer",
    "正确动物的平均概率": "Mean p(correct animal)",
    "换顺序后的变化": "Change after reordering",
    "正确动物的概率变化": "Change in p(correct animal)",
    "“你最喜欢哪种动物？”（全部 720 种排列）": "“Which animal do you like best?” (all 720 orderings)",
    "位置怎样改变动物的概率": "How position changes each animal’s probability",
    "动物在列表中的位置": "Position in the list",
    "全部排列下的最终选择": "Final choices across all orderings",
    "720 次中被选次数": "Times chosen (of 720)",
}

TEXT = re.compile(r"(<text\b[^>]*>)([^<]+)(</text>)")
CJK = re.compile(r"[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef“”]")


def translate(svg: str, name: str) -> str:
    def repl(match: re.Match[str]) -> str:
        label = match.group(2)
        if label in LABELS:
            return match.group(1) + LABELS[label] + match.group(3)
        if CJK.search(label):
            raise SystemExit(f"{name}: no translation for {label!r}")
        return match.group(0)

    return TEXT.sub(repl, svg)


def main() -> None:
    DST.mkdir(parents=True, exist_ok=True)
    for src in sorted(SRC.glob("*.svg")):
        out = DST / src.name
        out.write_text(translate(src.read_text(), src.name))
        print(out)


if __name__ == "__main__":
    main()
