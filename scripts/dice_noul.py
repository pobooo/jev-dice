#!/usr/bin/env python3
"""Dice experiment with one independent Noul question per face instead of one Choice."""

from __future__ import annotations

import argparse
import json
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from dice_jev import (
    MODEL,
    RateLimiter,
    load_api_key,
    load_done_trials,
    option_labels,
    post_once,
    protocol_spec,
    ssl_context,
)

N_PER_PROMPT = 200


def noul_instructions(face: str, labels: str) -> str:
    if labels == "animals":
        return f"Is the outcome {face}?"
    return f"Did the die come to rest with the {face} face pointing up?"


def payload_for(name: str, labels: str) -> dict[str, Any]:
    spec = protocol_spec(name, labels)
    return {
        "model": MODEL,
        "state": spec["state"],
        "questions": {
            f"face_{face}": {
                "type": "noul",
                "instructions": noul_instructions(face, labels),
            }
            for face in spec["order"]
        },
    }


def run_condition(
    name: str,
    n: int,
    labels: str,
    key: str,
    out_dir: Path,
    workers: int,
    limiter: RateLimiter,
) -> None:
    path = out_dir / f"{name}.jsonl"
    pending = [t for t in range(1, n + 1) if t not in load_done_trials(path)]
    if not pending:
        print(f"{name}: done, skip")
        return
    ctx = ssl_context()
    body = payload_for(name, labels)
    lock = threading.Lock()

    def one(trial_id: int) -> dict[str, Any]:
        rec = post_once(key, body, ctx, limiter)
        rec["prompt"] = name
        rec["trial_id"] = trial_id
        rec["labels"] = labels
        rec["request"] = body
        return rec

    with path.open("a") as f, ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(one, t) for t in pending]
        for i, fut in enumerate(as_completed(futs), 1):
            with lock:
                f.write(json.dumps(fut.result(), ensure_ascii=False) + "\n")
                f.flush()
            if i % 50 == 0 or i == len(pending):
                print(f"  {name} {i}/{len(pending)}")


def summarize(out_dir: Path, labels: str, names: list[str]) -> dict[str, Any]:
    faces = option_labels(labels)
    summary: dict[str, Any] = {"model": MODEL, "labels": labels, "prompts": {}}
    for name in names:
        values: dict[str, list[float]] = {k: [] for k in faces}
        errors = 0
        for line in (out_dir / f"{name}.jsonl").open():
            rec = json.loads(line)
            if not rec.get("ok"):
                errors += 1
                continue
            answers = rec["response"]["answers"]
            for k in faces:
                values[k].append(answers[f"face_{k}"]["noul"])
        mean = {k: round(statistics.fmean(v), 4) for k, v in values.items()}
        summary["prompts"][name] = {
            "ok": len(values[faces[0]]),
            "errors": errors,
            "order": protocol_spec(name, labels)["order"],
            "mean_noul": mean,
            "min_noul": {k: min(v) for k, v in values.items()},
            "max_noul": {k: max(v) for k, v in values.items()},
            "sum_of_means": round(sum(mean.values()), 4),
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=N_PER_PROMPT)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--rps", type=float, default=12.0)
    parser.add_argument("--labels", choices=("numbers", "animals"), default="numbers")
    parser.add_argument("--prompts", nargs="*", default=["P1", "P3", "P3alt"])
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.out is None:
        root = Path(__file__).resolve().parent.parent
        args.out = root / "results" / f"noul_{args.labels}"
    args.out.mkdir(parents=True, exist_ok=True)
    key = load_api_key()
    limiter = RateLimiter(args.rps)
    for name in args.prompts:
        run_condition(name, args.n, args.labels, key, args.out, args.workers, limiter)

    summary = summarize(args.out, args.labels, args.prompts)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
