#!/usr/bin/env python3
"""Ask Jev for a favorite animal under every option order.

Each of the 720 permutations is requested once. Every animal therefore
appears 120 times in every criteria position, separating a stable
preference from a preference for the first listed option.
"""

from __future__ import annotations

import argparse
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from itertools import permutations
from pathlib import Path
from typing import Any

from dice_jev import (
    ANIMAL_NATURAL,
    MODEL,
    RateLimiter,
    load_api_key,
    post_once,
    ssl_context,
)

ROOT = Path(__file__).resolve().parent.parent
ANIMALS = list(ANIMAL_NATURAL)
INSTRUCTIONS = "Which animal do you like best?"


def all_orders() -> list[list[str]]:
    return [list(order) for order in permutations(ANIMALS)]


def payload(order: list[str]) -> dict[str, Any]:
    listed = ", ".join(order)
    return {
        "model": MODEL,
        "state": f"The animals are [{listed}].",
        "questions": {
            "animal": {
                "type": "choice",
                "instructions": INSTRUCTIONS,
                "criteria": {
                    animal: f"The favorite animal is {animal}."
                    for animal in order
                },
            }
        },
    }


def load_done(path: Path) -> set[str]:
    done: set[str] = set()
    if not path.exists():
        return done
    with path.open() as fh:
        for line in fh:
            if line.strip():
                done.add(json.loads(line)["order_key"])
    return done


def run(out_dir: Path, workers: int, rps: float, limit: int | None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "trials.jsonl"
    done = load_done(path)
    orders = all_orders()[:limit] if limit else all_orders()
    pending = [order for order in orders if ",".join(order) not in done]
    print(f"{len(done)} done, {len(pending)} to run")
    if not pending:
        return path

    key = load_api_key()
    context = ssl_context()
    limiter = RateLimiter(rps)
    lock = threading.Lock()

    def one(order: list[str]) -> dict[str, Any]:
        body = payload(order)
        rec = post_once(key, body, context, limiter)
        rec.update(
            {
                "order_key": ",".join(order),
                "order": order,
                "request_state": body["state"],
                "request_instructions": INSTRUCTIONS,
                "request_criteria": body["questions"]["animal"]["criteria"],
            }
        )
        return rec

    with path.open("a") as fh, ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, order) for order in pending]
        for index, future in enumerate(as_completed(futures), 1):
            rec = future.result()
            with lock:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
            if index % 100 == 0 or index == len(pending):
                print(f"  {len(done) + index}/{len(done) + len(pending)}")
    return path


def summarize(path: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    errors = 0
    with path.open() as fh:
        for line in fh:
            rec = json.loads(line)
            if not rec.get("ok"):
                errors += 1
                continue
            rows.append(rec)

    choice_by_animal = {animal: 0 for animal in ANIMALS}
    choice_by_position = [0] * 6
    p_by_position = [0.0] * 6
    p_by_animal_position = [[0.0] * 6 for _ in ANIMALS]
    chosen_by_animal_position = [[0] * 6 for _ in ANIMALS]
    count_by_animal_position = [[0] * 6 for _ in ANIMALS]

    for rec in rows:
        order = rec["order"]
        face = rec["response"]["answers"]["animal"]
        choice = str(face["choice"])
        probabilities = face["probabilities"]
        choice_by_animal[choice] += 1
        choice_by_position[order.index(choice)] += 1
        for position, animal in enumerate(order):
            probability = float(probabilities[animal])
            p_by_position[position] += probability
            animal_index = ANIMALS.index(animal)
            p_by_animal_position[animal_index][position] += probability
            count_by_animal_position[animal_index][position] += 1
            if choice == animal:
                chosen_by_animal_position[animal_index][position] += 1

    n = len(rows) or 1
    return {
        "model": MODEL,
        "instructions": INSTRUCTIONS,
        "n": len(rows),
        "errors": errors,
        "choice_by_animal": choice_by_animal,
        "choice_rate_by_position": [count / n for count in choice_by_position],
        "mean_p_by_position": [total / n for total in p_by_position],
        "by_animal_and_position": {
            animal: {
                "times_at_position": count_by_animal_position[index],
                "choice_rate_when_at_position": [
                    chosen / count if count else None
                    for chosen, count in zip(
                        chosen_by_animal_position[index],
                        count_by_animal_position[index],
                    )
                ],
                "mean_p_when_at_position": [
                    total / count if count else None
                    for total, count in zip(
                        p_by_animal_position[index],
                        count_by_animal_position[index],
                    )
                ],
            }
            for index, animal in enumerate(ANIMALS)
        },
    }


def write_record(out_dir: Path, summary: dict[str, Any]) -> None:
    recorded_at = datetime.now().astimezone().isoformat(timespec="seconds")
    record = {
        "recorded_at": recorded_at,
        "experiment": "jev_favorite_animal_all_permutations",
        "dir": out_dir.name,
        "design": "All 720 animal orders, one request each.",
        **summary,
    }
    (out_dir / "EXPERIMENT_RECORD.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n"
    )
    lines = [
        "# Jev 最喜欢的动物（全部 720 种顺序）",
        "",
        f"- 时间：{recorded_at}",
        f"- 目录：`{out_dir.name}/`",
        f"- 问题：`{INSTRUCTIONS}`",
        "- state 列出当前顺序；criteria 使用相同顺序。每种排列只请求一次。",
        f"- 成功 {summary['n']}，失败 {summary['errors']}。",
        "",
        "## choice 落在第几位",
        "",
        "| 位置 | choice 比例 | 平均 p |",
        "|---:|---:|---:|",
    ]
    for position in range(6):
        lines.append(
            f"| {position + 1} | {summary['choice_rate_by_position'][position]:.3f} | "
            f"{summary['mean_p_by_position'][position]:.3f} |"
        )
    lines += [
        "",
        "## 各动物在各位置上的平均 p",
        "",
        "| 动物 | 位置1 | 位置2 | 位置3 | 位置4 | 位置5 | 位置6 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for animal, block in summary["by_animal_and_position"].items():
        cells = " | ".join(
            "—" if value is None else f"{value:.3f}"
            for value in block["mean_p_when_at_position"]
        )
        lines.append(f"| {animal} | {cells} |")
    (out_dir / "EXPERIMENT_RECORD.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "results" / "animal_favorite")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--rps", type=float, default=12.0)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    path = run(args.out, args.workers, args.rps, args.limit or None)
    summary = summarize(path)
    (args.out / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    )
    write_record(args.out, summary)
    print(json.dumps({
        "n": summary["n"],
        "errors": summary["errors"],
        "choice_rate_by_position": [
            round(value, 4) for value in summary["choice_rate_by_position"]
        ],
        "choice_by_animal": summary["choice_by_animal"],
    }, indent=2))


if __name__ == "__main__":
    main()
