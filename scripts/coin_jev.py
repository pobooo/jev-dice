#!/usr/bin/env python3
"""Fair coin flip: one Choice over heads/tails (both orders) vs independent Nouls."""

from __future__ import annotations

import argparse
import json
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from dice_jev import MODEL, RateLimiter, load_api_key, post_once, ssl_context

N_PER_CONDITION = 200

COINS: dict[str, dict[str, Any]] = {
    "heads_tails": {
        "state": "A fair coin is flipped once.",
        "sides": ["heads", "tails"],
        "criterion": "The coin landed {} up.",
        "noul": "Did the coin land {} up?",
    },
    "heads_tails_stated": {
        "state": "A fair coin is flipped once. One side is heads, the other side is tails.",
        "sides": ["heads", "tails"],
        "criterion": "The coin landed {} up.",
        "noul": "Did the coin land {} up?",
    },
    "tails_heads_stated": {
        "state": "A fair coin is flipped once. One side is tails, the other side is heads.",
        "sides": ["heads", "tails"],
        "criterion": "The coin landed {} up.",
        "noul": "Did the coin land {} up?",
    },
    "dog_cat": {
        "state": "A fair coin is flipped once. One side shows a dog, the other side shows a cat.",
        "sides": ["dog", "cat"],
        "criterion": "The coin landed with the {} side up.",
        "noul": "Did the coin land with the {} side up?",
    },
    "cat_dog": {
        "state": "A fair coin is flipped once. One side shows a cat, the other side shows a dog.",
        "sides": ["dog", "cat"],
        "criterion": "The coin landed with the {} side up.",
        "noul": "Did the coin land with the {} side up?",
    },
}

COIN = COINS["heads_tails"]
STATE = COIN["state"]
SIDES = COIN["sides"]
CONDITIONS: dict[str, dict[str, Any]] = {}


def set_coin(name: str) -> None:
    global COIN, STATE, SIDES
    COIN = COINS[name]
    STATE = COIN["state"]
    SIDES = COIN["sides"]
    a, b = SIDES
    CONDITIONS.clear()
    CONDITIONS.update({
        f"choice_{a}_first": {"type": "choice", "order": [a, b]},
        f"choice_{b}_first": {"type": "choice", "order": [b, a]},
        "noul": {"type": "noul", "order": [a, b]},
    })


set_coin("heads_tails")


def payload_for(name: str) -> dict[str, Any]:
    spec = CONDITIONS[name]
    if spec["type"] == "choice":
        questions = {
            "side": {
                "type": "choice",
                "instructions": "Which side landed up?",
                "criteria": {s: COIN["criterion"].format(s) for s in spec["order"]},
            }
        }
    else:
        questions = {
            f"side_{s}": {"type": "noul", "instructions": COIN["noul"].format(s)}
            for s in spec["order"]
        }
    return {"model": MODEL, "state": STATE, "questions": questions}


def side_probs(rec: dict[str, Any], kind: str) -> dict[str, float]:
    answers = rec["response"]["answers"]
    if kind == "choice":
        return {s: answers["side"]["probabilities"][s] for s in SIDES}
    return {s: answers[f"side_{s}"]["noul"] for s in SIDES}


def run(name: str, n: int, key: str, out_dir: Path, workers: int, limiter: RateLimiter) -> None:
    path = out_dir / f"{name}.jsonl"
    if path.exists():
        print(f"{name}: exists, skip")
        return
    ctx = ssl_context()
    body = payload_for(name)
    with path.open("w") as f, ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(post_once, key, body, ctx, limiter) for _ in range(n)]
        for trial_id, fut in enumerate(as_completed(futs), 1):
            rec = fut.result()
            rec.update({"condition": name, "trial_id": trial_id, "request": body})
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def summarize(out_dir: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {"model": MODEL, "state": STATE, "conditions": {}}
    for name, spec in CONDITIONS.items():
        probs: dict[str, list[float]] = {s: [] for s in SIDES}
        picks = {s: 0 for s in SIDES}
        errors = 0
        for line in (out_dir / f"{name}.jsonl").open():
            rec = json.loads(line)
            if not rec.get("ok"):
                errors += 1
                continue
            p = side_probs(rec, spec["type"])
            for s in SIDES:
                probs[s].append(p[s])
            if spec["type"] == "choice":
                picks[rec["response"]["answers"]["side"]["choice"]] += 1
        summary["conditions"][name] = {
            "type": spec["type"],
            "order": spec["order"],
            "ok": len(probs[SIDES[0]]),
            "errors": errors,
            "mean_p": {s: round(statistics.fmean(v), 4) for s, v in probs.items()},
            "min_p": {s: min(v) for s, v in probs.items()},
            "max_p": {s: max(v) for s, v in probs.items()},
            **({"picks": picks} if spec["type"] == "choice" else {}),
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=N_PER_CONDITION)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--rps", type=float, default=12.0)
    parser.add_argument("--coin", choices=tuple(COINS), default="heads_tails")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    set_coin(args.coin)
    if args.out is None:
        results = Path(__file__).resolve().parent.parent / "results"
        args.out = results / ("coin" if args.coin == "heads_tails" else f"coin_{args.coin}")
    args.out.mkdir(parents=True, exist_ok=True)
    key = load_api_key()
    limiter = RateLimiter(args.rps)
    for name in CONDITIONS:
        run(name, args.n, key, args.out, args.workers, limiter)
    summary = summarize(args.out)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
