# Jev 抛硬币吗？ / Does Jev Flip Coins?

**非确定性决策中的系统性偏差 · Systematic bias in non-deterministic decisions**

作者 / Author: Qiang Liu ([qiangliu.net](https://qiangliu.net)) · 实验与报告撰写由 AI 辅助完成 / Experiments and writing assisted by AI

- English report: [`docs/index.html`](docs/index.html)
- 中文报告：[`docs/zh/index.html`](docs/zh/index.html)

## 简介

我们之前研究过 GPT-4 生成随机数的能力（[*Does GPT-4 Play Dice?*](https://qiangliu.net/publications/Does_GPT_Play_Dice.pdf)），这次用类似的思路测试 TypeSafe 的 [Jev 模型](https://docs.typesafe.ai/introduction)（`jev-1.13.0`）。

结论：Jev 不能公平地掷骰子。在没有唯一正确答案的选择中，它的输出会受到选项位置和词语本身的影响，产生系统性偏差：同一道题请求 2000 次，每次都选排在第一的选项。在有唯一正确答案的任务里（根据描述猜动物），选项顺序几乎不影响结果。

## Summary

We previously studied GPT-4’s ability to generate random numbers ([*Does GPT-4 Play Dice?*](https://qiangliu.net/publications/Does_GPT_Play_Dice.pdf)). This project applies a similar approach to TypeSafe’s [Jev model](https://docs.typesafe.ai/introduction) (`jev-1.13.0`).

Finding: Jev cannot roll a fair die. When a choice has no single correct answer, its output is influenced by option position and by the words themselves: across 2,000 identical requests it picks the first-listed option every time. On a task with a single correct answer (guessing an animal from a description), option order barely matters.

## 目录结构 / Layout

```text
docs/            网页报告（英文 index.html 为主页，中文 zh/）/ HTML report (GitHub Pages; English home page, Chinese in zh/)
scripts/         实验与绘图脚本 / experiment and chart scripts
data/            猜动物实验的 72 条描述 / the 72 animal descriptions
results/         原始请求记录与汇总 / raw request logs and summaries
  dice_numbers/            数字骰子 / number die
  dice_animals/            动物骰子 / animal die
  dice_numbers_reshuffle/  再次打乱数字 / number die, reshuffled
  animal_guess/            根据描述猜动物 / guess the animal
  animal_favorite/         最喜欢的动物 / favorite animal
```

骰子结果里的 `P3plus`、`P3altplus`（题目中额外强调“每一面概率相同”）结果与不强调时基本一致，报告中未使用，原始数据仍保留。
The `P3plus` and `P3altplus` dice runs (which add “each face is equally likely”) gave essentially the same results as without it; they are kept as raw data but not used in the report.

## 复现 / Reproduce

```bash
pip install -r requirements.txt
export TYPESAFE_API_KEY=...        # 或写入 ~/.typesafe/api_key / or put it in ~/.typesafe/api_key

# 数字骰子与动物骰子 / number and animal dice (2,000 requests per prompt)
python scripts/dice_jev.py --labels numbers --prompts P1 P2 P3 P3plus
python scripts/dice_jev.py --labels animals --prompts P1 P2 P3 P3plus
python scripts/dice_jev.py --labels numbers --prompts P3alt P3altplus --out results/dice_numbers_reshuffle

# 根据描述猜动物 / guess the animal (72 sentences × 2 orders)
python scripts/build_animal_descriptions.py
python scripts/animal_decide_dataset.py

# 最喜欢的动物 / favorite animal (all 720 orderings)
python scripts/animal_favorite.py

# 报告图表：先生成中文图，再翻译出英文图 / report charts: Chinese first, then English copies
python scripts/generate_report_charts.py
python scripts/translate_report_charts.py
```

本地预览报告 / Preview locally:

```bash
python3 -m http.server 8765 --directory docs
```
