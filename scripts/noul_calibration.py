#!/usr/bin/env python3
"""Noul calibration: fair N-sided dice, one Noul per face, compare to 1/N."""

from __future__ import annotations

import argparse
import json
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from dice_jev import MODEL, RateLimiter, load_api_key, post_once, ssl_context

SIDES = [2, 3, 4, 6, 8, 10, 12, 20]
N_PER_DIE = 100


def payload_for(n_sides: int) -> dict[str, Any]:
    return {
        "model": MODEL,
        "state": (
            f"A fair {n_sides}-sided die with faces numbered 1 to {n_sides} "
            "is rolled once."
        ),
        "questions": {
            f"face_{k}": {
                "type": "noul",
                "instructions": f"Did the die land on {k}?",
            }
            for k in range(1, n_sides + 1)
        },
    }


def run(n_sides: int, n: int, key: str, out_dir: Path, workers: int, limiter: RateLimiter) -> None:
    path = out_dir / f"d{n_sides}.jsonl"
    if path.exists():
        print(f"d{n_sides}: exists, skip")
        return
    ctx = ssl_context()
    body = payload_for(n_sides)
    with path.open("w") as f, ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(post_once, key, body, ctx, limiter) for _ in range(n)]
        for trial_id, fut in enumerate(as_completed(futs), 1):
            rec = fut.result()
            rec.update({"n_sides": n_sides, "trial_id": trial_id, "request": body})
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"d{n_sides}: done")


def summarize(out_dir: Path, sides: list[int]) -> dict[str, Any]:
    summary: dict[str, Any] = {"model": MODEL, "dice": {}}
    for n_sides in sides:
        per_face: dict[int, list[float]] = {k: [] for k in range(1, n_sides + 1)}
        errors = 0
        for line in (out_dir / f"d{n_sides}.jsonl").open():
            rec = json.loads(line)
            if not rec.get("ok"):
                errors += 1
                continue
            answers = rec["response"]["answers"]
            for k in per_face:
                per_face[k].append(answers[f"face_{k}"]["noul"])
        face_means = {k: statistics.fmean(v) for k, v in per_face.items()}
        summary["dice"][f"d{n_sides}"] = {
            "n_sides": n_sides,
            "true_p": round(1 / n_sides, 4),
            "ok": len(per_face[1]),
            "errors": errors,
            "mean_noul": round(statistics.fmean(face_means.values()), 4),
            "min_face_mean": round(min(face_means.values()), 4),
            "max_face_mean": round(max(face_means.values()), 4),
            "sum_of_means": round(sum(face_means.values()), 4),
            "face_means": {k: round(v, 4) for k, v in face_means.items()},
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=N_PER_DIE)
    parser.add_argument("--sides", type=int, nargs="*", default=SIDES)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--rps", type=float, default=12.0)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.out is None:
        args.out = Path(__file__).resolve().parent.parent / "results" / "noul_calibration"
    args.out.mkdir(parents=True, exist_ok=True)
    key = load_api_key()
    limiter = RateLimiter(args.rps)
    for n_sides in args.sides:
        run(n_sides, args.n, key, args.out, args.workers, limiter)
    summary = summarize(args.out, args.sides)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    for name, d in summary["dice"].items():
        print(
            f"{name:>4} true={d['true_p']:.3f} mean={d['mean_noul']:.3f} "
            f"faces=[{d['min_face_mean']:.3f}, {d['max_face_mean']:.3f}] "
            f"sum={d['sum_of_means']:.2f} ok={d['ok']} err={d['errors']}"
        )


if __name__ == "__main__":
    main()
