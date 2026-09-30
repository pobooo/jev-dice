# Does Jev Play Dice?

**Systematic bias in non-deterministic decisions**

[中文](README.zh.md) · [Read the report](https://qiangliu.net/jev-dice/)

Author: Qiang Liu ([qiangliu.net](https://qiangliu.net)) · Experiments and writing assisted by AI

## Summary

We previously studied GPT-4’s ability to generate random numbers ([*Does GPT-4 Play Dice?*](https://qiangliu.net/publications/Does_GPT_Play_Dice.pdf)). This project applies a similar approach to TypeSafe’s [Jev model](https://docs.typesafe.ai/introduction) (`jev-1.13.0`).

Finding: Jev cannot roll a fair die. When a choice has no single correct answer, its output is influenced by option position and by the words themselves: across 2,000 identical requests it picks the first-listed option every time. On a task with a single correct answer (guessing an animal from a description), option order barely matters. When each face is instead judged by a separate yes/no question (Noul), probability no longer piles onto one option, but it is pulled toward the middle: large probabilities are underestimated and small ones overestimated.

## Layout

```text
docs/            HTML report (GitHub Pages; English home page, Chinese in zh/)
scripts/         experiment and chart scripts
data/            the 72 animal descriptions
results/         raw request logs and summaries
  dice_numbers/            number die
  dice_animals/            animal die
  dice_numbers_reshuffle/  number die, reshuffled
  animal_guess/            guess the animal
  animal_favorite/         favorite animal
  noul_calibration/        Noul calibration on fair 2–20-sided dice
  noul_numbers/, noul_animals/, coin*/   extra Noul dice and coin runs (not used in the report)
```

The `P3plus` and `P3altplus` dice runs (which add “each face is equally likely”) gave essentially the same results as without it; they are kept as raw data but not used in the report.

## Reproduce

```bash
pip install -r requirements.txt
export TYPESAFE_API_KEY=...        # or put it in ~/.typesafe/api_key

# number and animal dice (2,000 requests per prompt)
python scripts/dice_jev.py --labels numbers --prompts P1 P2 P3 P3plus
python scripts/dice_jev.py --labels animals --prompts P1 P2 P3 P3plus
python scripts/dice_jev.py --labels numbers --prompts P3alt P3altplus --out results/dice_numbers_reshuffle

# guess the animal (72 sentences × 2 orders)
python scripts/build_animal_descriptions.py
python scripts/animal_decide_dataset.py

# favorite animal (all 720 orderings)
python scripts/animal_favorite.py

# Noul calibration (8 dice × 100 requests)
python scripts/noul_calibration.py

# extra runs (not used in the report)
python scripts/dice_noul.py --labels numbers
python scripts/dice_noul.py --labels animals
python scripts/coin_jev.py --coin heads_tails   # also: heads_tails_stated, tails_heads_stated, dog_cat, cat_dog

# report charts: Chinese first, then English copies
python scripts/generate_report_charts.py
python scripts/translate_report_charts.py
```

## Citation

Qiang Liu. *Does Jev Play Dice? Systematic Bias in Non-deterministic Decisions*. Technical report, September 2026. https://qiangliu.net/jev-dice/

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

## Preview

```bash
python3 -m http.server 8765 --directory docs
```
