# Jev 掷骰子吗？

**非确定性决策中的系统性偏差**

[English](README.md) · [阅读报告](https://qiangliu.net/jev-dice/zh/)

作者：Qiang Liu（[qiangliu.net](https://qiangliu.net)）· 实验与报告撰写由 AI 辅助完成

## 简介

我们之前研究过 GPT-4 生成随机数的能力（[*Does GPT-4 Play Dice?*](https://qiangliu.net/publications/Does_GPT_Play_Dice.pdf)），这次用类似的思路测试 TypeSafe 的 [Jev 模型](https://docs.typesafe.ai/introduction)（`jev-1.13.0`）。

结论：Jev 不能公平地掷骰子。在没有唯一正确答案的选择中，它的输出会受到选项位置和词语本身的影响，产生系统性偏差：同一道题请求 2000 次，每次都选排在第一的选项。在有唯一正确答案的任务里（根据描述猜动物），选项顺序几乎不影响结果。改成对每一面单独问是非题（Noul）后，概率不再集中到一项，但会向中间靠拢：大概率被低估，小概率被高估。

## 目录结构

```text
docs/            网页报告（英文 index.html 为主页，中文在 zh/）
scripts/         实验与绘图脚本
data/            猜动物实验的 72 条描述
results/         原始请求记录与汇总
  dice_numbers/            数字骰子
  dice_animals/            动物骰子
  dice_numbers_reshuffle/  再次打乱数字
  animal_guess/            根据描述猜动物
  animal_favorite/         最喜欢的动物
  noul_calibration/        Noul 校准：2–20 面公平骰
  noul_numbers/, noul_animals/, coin*/   Noul 骰子与抛硬币补充实验（报告中未使用）
```

骰子结果里的 `P3plus`、`P3altplus`（题目中额外强调“每一面概率相同”）结果与不强调时基本一致，报告中未使用，原始数据仍保留。

## 复现

```bash
pip install -r requirements.txt
export TYPESAFE_API_KEY=...        # 或写入 ~/.typesafe/api_key

# 数字骰子与动物骰子（每种题目 2000 次）
python scripts/dice_jev.py --labels numbers --prompts P1 P2 P3 P3plus
python scripts/dice_jev.py --labels animals --prompts P1 P2 P3 P3plus
python scripts/dice_jev.py --labels numbers --prompts P3alt P3altplus --out results/dice_numbers_reshuffle

# 根据描述猜动物（72 句 × 2 种顺序）
python scripts/build_animal_descriptions.py
python scripts/animal_decide_dataset.py

# 最喜欢的动物（全部 720 种排列）
python scripts/animal_favorite.py

# Noul 校准（8 种骰子 × 100 次）
python scripts/noul_calibration.py

# 补充实验（报告中未使用）
python scripts/dice_noul.py --labels numbers
python scripts/dice_noul.py --labels animals
python scripts/coin_jev.py --coin heads_tails   # 也可用：heads_tails_stated, tails_heads_stated, dog_cat, cat_dog

# 报告图表：先生成中文图，再翻译出英文图
python scripts/generate_report_charts.py
python scripts/translate_report_charts.py
```

## 引用

Qiang Liu. *Does Jev Play Dice? Systematic Bias in Non-deterministic Decisions*. Technical report, September 2026. https://qiangliu.net/jev-dice/

中文版：Qiang Liu. 《Jev 掷骰子吗？非确定性决策中的系统性偏差》. 技术报告, 2026 年 9 月. https://qiangliu.net/jev-dice/zh/

```bibtex
@techreport{liu2026jevdice,
  author      = {Qiang Liu},
  title       = {Does {Jev} Play Dice? Systematic Bias in Non-deterministic Decisions},
  institution = {qiangliu.net},
  type        = {Technical report},
  year        = {2026},
  month       = sep,
  url         = {https://qiangliu.net/jev-dice/},
  note        = {Code and data: \url{https://github.com/pobooo/jev-dice}}
}
```

## 本地预览

```bash
python3 -m http.server 8765 --directory docs
```
