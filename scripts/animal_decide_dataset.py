#!/usr/bin/env python3
"""Run each varied animal description once under two criteria orders."""

from __future__ import annotations

import argparse
import json
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from dice_jev import (
    ANIMAL_NATURAL,
    ANIMAL_SHUFFLED,
    MODEL,
    RateLimiter,
    load_api_key,
    post_once,
    ssl_context,
)

ROOT = Path(__file__).resolve().parent.parent

ORDERS: dict[str, list[str]] = {
    "natural": list(ANIMAL_NATURAL),
    "shuffled": list(ANIMAL_SHUFFLED),
}

INSTRUCTIONS = "Which animal does this sentence describe?"


def criteria_for(order: list[str]) -> dict[str, str]:
    return {animal: f"The sentence describes a {animal}." for animal in order}


def payload(sentence: str, order: list[str]) -> dict[str, Any]:
    return {
        "model": MODEL,
        "state": sentence,
        "questions": {
            "animal": {
                "type": "choice",
                "instructions": INSTRUCTIONS,
                "criteria": criteria_for(order),
            }
        },
    }


def read_dataset(path: Path) -> list[dict[str, str]]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise SystemExit("dataset contains duplicate ids")
    texts = [row["text"] for row in rows]
    if len(texts) != len(set(texts)):
        raise SystemExit("dataset contains duplicate descriptions")
    return rows


def load_done(path: Path) -> set[str]:
    if not path.exists():
        return set()
    done: set[str] = set()
    with path.open() as fh:
        for line in fh:
            if line.strip():
                rec = json.loads(line)
                done.add(f"{rec['description_id']}:{rec['order']}")
    return done


def run(
    dataset: list[dict[str, str]],
    out_dir: Path,
    workers: int,
    rps: float,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "trials.jsonl"
    done = load_done(path)
    pending = [
        (row, order_name)
        for row in dataset
        for order_name in ORDERS
        if f"{row['id']}:{order_name}" not in done
    ]
    print(f"{len(done)} done, {len(pending)} to run")
    if not pending:
        return path

    key = load_api_key()
    context = ssl_context()
    limiter = RateLimiter(rps)
    lock = threading.Lock()

    def one(item: tuple[dict[str, str], str]) -> dict[str, Any]:
        row, order_name = item
        order = ORDERS[order_name]
        body = payload(row["text"], order)
        rec = post_once(key, body, context, limiter)
        rec.update(
            {
                "description_id": row["id"],
                "truth": row["target"],
                "clarity": row["clarity"],
                "sentence": row["text"],
                "order": order_name,
                "criteria_order": order,
                "request_state": body["state"],
                "request_instructions": INSTRUCTIONS,
                "request_criteria": criteria_for(order),
            }
        )
        return rec

    with path.open("a") as fh, ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, item) for item in pending]
        for index, future in enumerate(as_completed(futures), 1):
            rec = future.result()
            with lock:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
            if index % 50 == 0 or index == len(pending):
                print(f"  {len(done) + index}/{len(done) + len(pending)}")
    return path


def answer(rec: dict[str, Any]) -> dict[str, Any]:
    return rec["response"]["answers"]["animal"]


def summarize(
    path: Path,
    dataset: list[dict[str, str]],
) -> dict[str, Any]:
    records: dict[tuple[str, str], dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    with path.open() as fh:
        for line in fh:
            rec = json.loads(line)
            if not rec.get("ok"):
                errors.append(rec)
                continue
            records[(rec["description_id"], rec["order"])] = rec

    by_order: dict[str, Any] = {}
    for order_name, order in ORDERS.items():
        rows = [rec for (desc_id, name), rec in records.items() if name == order_name]
        correct = sum(str(answer(rec)["choice"]) == rec["truth"] for rec in rows)
        clarity: dict[str, Any] = {}
        for level in ("clear", "medium", "ambiguous"):
            subset = [rec for rec in rows if rec["clarity"] == level]
            hits = sum(str(answer(rec)["choice"]) == rec["truth"] for rec in subset)
            clarity[level] = {
                "n": len(subset),
                "correct": hits,
                "accuracy": hits / len(subset) if subset else None,
                "mean_p_correct": (
                    sum(float(answer(rec)["probabilities"][rec["truth"]]) for rec in subset)
                    / len(subset)
                    if subset
                    else None
                ),
                "first_choice_count": sum(
                    str(answer(rec)["choice"]) == order[0] for rec in subset
                ),
            }
        by_order[order_name] = {
            "criteria_order": order,
            "first_key": order[0],
            "n": len(rows),
            "correct": correct,
            "accuracy": correct / len(rows) if rows else None,
            "by_clarity": clarity,
        }

    pairs: list[dict[str, Any]] = []
    for row in dataset:
        natural = records.get((row["id"], "natural"))
        shuffled = records.get((row["id"], "shuffled"))
        if not natural or not shuffled:
            continue
        natural_answer = answer(natural)
        shuffled_answer = answer(shuffled)
        truth = row["target"]
        pairs.append(
            {
                **row,
                "natural_choice": str(natural_answer["choice"]),
                "shuffled_choice": str(shuffled_answer["choice"]),
                "choice_changed": natural_answer["choice"] != shuffled_answer["choice"],
                "natural_p_correct": float(natural_answer["probabilities"][truth]),
                "shuffled_p_correct": float(shuffled_answer["probabilities"][truth]),
                "delta_p_correct_shuffled_minus_natural": (
                    float(shuffled_answer["probabilities"][truth])
                    - float(natural_answer["probabilities"][truth])
                ),
            }
        )

    changed = sum(row["choice_changed"] for row in pairs)
    deltas = [row["delta_p_correct_shuffled_minus_natural"] for row in pairs]
    by_target: dict[str, Any] = {}
    for target in ANIMAL_NATURAL:
        subset = [row for row in pairs if row["target"] == target]
        natural_pos = ORDERS["natural"].index(target) + 1
        shuffled_pos = ORDERS["shuffled"].index(target) + 1
        by_target[target] = {
            "n": len(subset),
            "natural_position": natural_pos,
            "shuffled_position": shuffled_pos,
            "mean_delta_p_correct": (
                sum(row["delta_p_correct_shuffled_minus_natural"] for row in subset)
                / len(subset)
                if subset
                else None
            ),
            "choice_changed": sum(row["choice_changed"] for row in subset),
        }

    return {
        "model": MODEL,
        "instructions": INSTRUCTIONS,
        "dataset_size": len(dataset),
        "request_count": len(records),
        "errors": len(errors),
        "orders": by_order,
        "paired": {
            "n": len(pairs),
            "choice_changed": changed,
            "choice_changed_rate": changed / len(pairs) if pairs else None,
            "mean_delta_p_correct_shuffled_minus_natural": (
                sum(deltas) / len(deltas) if deltas else None
            ),
            "by_target": by_target,
            "rows": pairs,
        },
    }


def write_record(out_dir: Path, summary: dict[str, Any]) -> None:
    record = {
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "experiment": "jev_animal_varied_description_guess",
        "dir": out_dir.name,
        "design": (
            "72 unique descriptions (6 animals × 3 clarity levels × 4), "
            "each tested once under natural and shuffled criteria orders."
        ),
        **summary,
    }
    (out_dir / "EXPERIMENT_RECORD.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n"
    )
    lines = [
        "# Jev 不同动物描述数据集",
        "",
        f"- 时间：{record['recorded_at']}",
        f"- 目录：`{out_dir.name}/`",
        f"- 数据集：{summary['dataset_size']} 条不重复描述；每条按两种顺序各测一次。",
        f"- 请求：{summary['request_count']} 成功，{summary['errors']} 失败。",
        "",
        "## 总体",
        "",
        "| 顺序 | 首位 | 准确率 |",
        "|---|---|---:|",
    ]
    for name, block in summary["orders"].items():
        lines.append(f"| {name} | {block['first_key']} | {block['accuracy']:.3f} |")
    paired = summary["paired"]
    lines += [
        "",
        f"- 同一句换顺序后 choice 改变：{paired['choice_changed']}/{paired['n']}。",
        (
            "- 平均 Δp(正确)（shuffled − natural）："
            f"{paired['mean_delta_p_correct_shuffled_minus_natural']:+.4f}。"
        ),
        "",
        "## 按难度",
        "",
        "| 顺序 | 难度 | n | 准确率 | 平均 p(正确) | 选择首位次数 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for name, block in summary["orders"].items():
        for level, stats in block["by_clarity"].items():
            lines.append(
                f"| {name} | {level} | {stats['n']} | {stats['accuracy']:.3f} | "
                f"{stats['mean_p_correct']:.3f} | {stats['first_choice_count']} |"
            )
    lines += [
        "",
        "## 动物移动位置与 Δp(正确)",
        "",
        "| 动物 | natural 位置 | shuffled 位置 | n | 平均 Δp | choice 改变 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for target, stats in paired["by_target"].items():
        lines.append(
            f"| {target} | {stats['natural_position']} | "
            f"{stats['shuffled_position']} | {stats['n']} | "
            f"{stats['mean_delta_p_correct']:+.4f} | {stats['choice_changed']} |"
        )
    (out_dir / "EXPERIMENT_RECORD.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "data" / "animal_descriptions.jsonl",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "results" / "animal_guess",
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--rps", type=float, default=12.0)
    args = parser.parse_args()
    dataset = read_dataset(args.dataset)
    path = run(dataset, args.out, args.workers, args.rps)
    summary = summarize(path, dataset)
    (args.out / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    )
    write_record(args.out, summary)
    print(
        json.dumps(
            {
                "dataset_size": summary["dataset_size"],
                "request_count": summary["request_count"],
                "errors": summary["errors"],
                "accuracy": {
                    name: block["accuracy"]
                    for name, block in summary["orders"].items()
                },
                "choice_changed": summary["paired"]["choice_changed"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
