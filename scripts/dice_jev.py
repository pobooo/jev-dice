#!/usr/bin/env python3
"""Jev single-roll dice experiment (Does GPT-4 Play Dice? §2 analog)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import ssl
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

API_URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"
N_PER_PROMPT = 2000

PROMPTS: dict[str, dict[str, Any]] = {
    "P1": {
        "instructions": (
            "You are playing a game of dice. Please generate a random number "
            "between 1 and 6, which represents the outcome of rolling a "
            "standard six-sided die."
        ),
        "order": ["1", "2", "3", "4", "5", "6"],
    },
    "P2": {
        "instructions": (
            "You are playing a game of dice. Please generate a random number "
            "from [1, 2, 3, 4, 5, 6], which represents the outcome of rolling "
            "a standard six-sided die."
        ),
        "order": ["1", "2", "3", "4", "5", "6"],
    },
    "P3": {
        "instructions": (
            "You are playing a game of dice. Please generate a random number "
            "from [4, 2, 6, 1, 5, 3], which represents the outcome of rolling "
            "a standard six-sided die."
        ),
        "order": ["4", "2", "6", "1", "5", "3"],
    },
    "P3plus": {
        "instructions": (
            "You are playing a game of dice. Please generate a random number "
            "from [4, 2, 6, 1, 5, 3], which represents the outcome of rolling "
            "a standard six-sided die. The probability of selecting each "
            "number should be equal."
        ),
        "order": ["4", "2", "6", "1", "5", "3"],
    },
}

# Corrected System One layout: content in state, judgment in instructions.
PROTOCOL_PROMPTS: dict[str, dict[str, Any]] = {
    "P1": {
        "state": "A fair six-sided die is rolled once.",
        "instructions": "Which face landed up?",
        "order": ["1", "2", "3", "4", "5", "6"],
    },
    "P2": {
        "state": (
            "A fair six-sided die is rolled once. "
            "The faces are [1, 2, 3, 4, 5, 6]."
        ),
        "instructions": "Which face landed up?",
        "order": ["1", "2", "3", "4", "5", "6"],
    },
    "P3": {
        "state": (
            "A fair six-sided die is rolled once. "
            "The faces are [4, 2, 6, 1, 5, 3]."
        ),
        "instructions": "Which face landed up?",
        "order": ["4", "2", "6", "1", "5", "3"],
    },
    "P3plus": {
        "state": (
            "A fair six-sided die is rolled once. "
            "The faces are [4, 2, 6, 1, 5, 3]. "
            "Each face is equally likely."
        ),
        "instructions": "Which face landed up?",
        "order": ["4", "2", "6", "1", "5", "3"],
    },
    # New shuffle: 1 moves from list position 4 to position 5.
    "P3alt": {
        "state": (
            "A fair six-sided die is rolled once. "
            "The faces are [5, 3, 2, 6, 1, 4]."
        ),
        "instructions": "Which face landed up?",
        "order": ["5", "3", "2", "6", "1", "4"],
    },
    "P3altplus": {
        "state": (
            "A fair six-sided die is rolled once. "
            "The faces are [5, 3, 2, 6, 1, 4]. "
            "Each face is equally likely."
        ),
        "instructions": "Which face landed up?",
        "order": ["5", "3", "2", "6", "1", "4"],
    },
}


ANIMAL_NATURAL = ["cat", "dog", "bird", "fish", "horse", "cow"]
# Same permutation as numeric P3: 4,2,6,1,5,3
ANIMAL_SHUFFLED = ["fish", "dog", "cow", "cat", "horse", "bird"]
# Same permutation as numeric P3alt: 5,3,2,6,1,4
ANIMAL_SHUFFLED_ALT = ["horse", "bird", "dog", "cow", "cat", "fish"]

PROTOCOL_ANIMAL_PROMPTS: dict[str, dict[str, Any]] = {
    "P1": {
        "state": (
            "A fair six-sided die is rolled once. "
            "Each face shows a different animal."
        ),
        "instructions": "Which animal is the outcome?",
        "order": list(ANIMAL_NATURAL),
    },
    "P2": {
        "state": (
            "A fair six-sided die is rolled once. "
            "The faces are [cat, dog, bird, fish, horse, cow]."
        ),
        "instructions": "Which animal is the outcome?",
        "order": list(ANIMAL_NATURAL),
    },
    "P3": {
        "state": (
            "A fair six-sided die is rolled once. "
            "The faces are [fish, dog, cow, cat, horse, bird]."
        ),
        "instructions": "Which animal is the outcome?",
        "order": list(ANIMAL_SHUFFLED),
    },
    "P3plus": {
        "state": (
            "A fair six-sided die is rolled once. "
            "The faces are [fish, dog, cow, cat, horse, bird]. "
            "Each face is equally likely."
        ),
        "instructions": "Which animal is the outcome?",
        "order": list(ANIMAL_SHUFFLED),
    },
    "P3alt": {
        "state": (
            "A fair six-sided die is rolled once. "
            "The faces are [horse, bird, dog, cow, cat, fish]."
        ),
        "instructions": "Which animal is the outcome?",
        "order": list(ANIMAL_SHUFFLED_ALT),
    },
    "P3altplus": {
        "state": (
            "A fair six-sided die is rolled once. "
            "The faces are [horse, bird, dog, cow, cat, fish]. "
            "Each face is equally likely."
        ),
        "instructions": "Which animal is the outcome?",
        "order": list(ANIMAL_SHUFFLED_ALT),
    },
}


def protocol_spec(name: str, labels: str) -> dict[str, Any]:
    if labels == "animals":
        return PROTOCOL_ANIMAL_PROMPTS[name]
    return PROTOCOL_PROMPTS[name]


def known_prompt_names() -> set[str]:
    return set(PROMPTS) | set(PROTOCOL_PROMPTS) | set(PROTOCOL_ANIMAL_PROMPTS)


def load_api_key() -> str:
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if key:
        return key
    path = Path.home() / ".typesafe" / "api_key"
    if path.is_file():
        return path.read_text().strip()
    raise SystemExit("TYPESAFE_API_KEY is not set")


def option_labels(labels: str) -> list[str]:
    if labels == "animals":
        return list(ANIMAL_NATURAL)
    return ["1", "2", "3", "4", "5", "6"]


def ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def trial_hash(trial_id: int) -> str:
    """Opaque hash of the trial index only; never embed the raw index."""
    return hashlib.sha256(str(trial_id).encode("utf-8")).hexdigest()


def face_description(face: str, labels: str) -> str:
    """Symmetric per-option rubric so no option gets extra emphasis."""
    if labels == "animals":
        return f"The outcome is {face}."
    return f"The die came to rest with the {face} face pointing up."


def payload_for(
    name: str,
    trial_id: int | None = None,
    layout: str = "protocol",
    criteria_style: str = "describe",
    state_hash_chars: int = 0,
    labels: str = "numbers",
) -> dict[str, Any]:
    cache_bust_hash = trial_hash(trial_id) if trial_id is not None else None
    state_prefix = (
        cache_bust_hash[:state_hash_chars]
        if cache_bust_hash and state_hash_chars > 0
        else None
    )
    if layout == "protocol":
        spec = protocol_spec(name, labels)
        criteria = {k: face_description(k, labels) for k in spec["order"]}
        instructions = spec["instructions"]
        if state_prefix is not None:
            state: Any = f"{state_prefix} {spec['state']}"
        elif cache_bust_hash is not None:
            state = {
                "event": spec["state"],
                "nonce": cache_bust_hash,
            }
        else:
            state = spec["state"]
    else:
        spec = PROMPTS[name]
        criteria = {k: f"The roll is {k}." for k in spec["order"]}
        instructions = spec["instructions"]
        if cache_bust_hash is not None and state_hash_chars <= 0:
            instructions = f"{cache_bust_hash}\n{instructions}"
        state = ""
        if state_prefix is not None:
            state = state_prefix
    return {
        "model": MODEL,
        "state": state,
        "questions": {
            "face": {
                "type": "choice",
                "instructions": instructions,
                "criteria": criteria,
            }
        },
        "_meta": {
            "cache_bust_hash": cache_bust_hash,
            "state_prefix": state_prefix,
            "trial_id": trial_id,
            "layout": layout,
            "criteria_style": criteria_style,
            "labels": labels,
        },
    }


class RateLimiter:
    def __init__(self, rps: float) -> None:
        self.min_interval = 1.0 / rps
        self.lock = threading.Lock()
        self.next_t = 0.0

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            t = max(now, self.next_t)
            self.next_t = t + self.min_interval
            delay = t - now
        if delay > 0:
            time.sleep(delay)


def post_once(
    key: str,
    body: dict[str, Any],
    ctx: ssl.SSLContext,
    limiter: RateLimiter | None = None,
) -> dict[str, Any]:
    if limiter is not None:
        limiter.wait()
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    last_err = None
    for attempt in range(8):
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
                raw = json.loads(resp.read().decode())
                return {"ok": True, "http_status": resp.status, "response": raw}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode(errors="replace")
            if e.code in (429, 520, 529):
                wait = 2**attempt
                try:
                    wait = float(e.headers.get("Retry-After") or wait)
                except ValueError:
                    pass
                time.sleep(min(wait, 30))
                last_err = {"http_status": e.code, "error": err_body[:1500]}
                continue
            return {"ok": False, "http_status": e.code, "error": err_body[:2000]}
        except Exception as e:
            last_err = {"error": f"{type(e).__name__}: {e}"}
            time.sleep(min(2**attempt, 16))
    return {"ok": False, **(last_err or {"error": "unknown"})}


def extract_choice(record: dict[str, Any]) -> str | None:
    if not record.get("ok"):
        return None
    answers = (record.get("response") or {}).get("answers") or {}
    face = answers.get("face") or {}
    choice = face.get("choice")
    return str(choice) if choice is not None else None


def load_done_trials(path: Path) -> set[int]:
    done: set[int] = set()
    if not path.exists():
        return done
    with path.open() as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            tid = rec.get("trial_id")
            if tid is None:
                tid = rec.get("trial")
            if tid is not None:
                done.add(int(tid))
    return done


def run_condition(
    name: str,
    n: int,
    key: str,
    out_dir: Path,
    workers: int,
    limiter: RateLimiter,
    hash_prefix: bool,
    layout: str,
    criteria_style: str,
    state_hash_chars: int,
    labels: str,
) -> Path:
    path = out_dir / f"{name}.jsonl"
    done_ids = load_done_trials(path)
    # Trial indices are 1..n so the hash is of the experiment sequence number.
    pending = [tid for tid in range(1, n + 1) if tid not in done_ids]
    if not pending:
        print(f"{name}: already have {len(done_ids)} lines, skip")
        return path

    ctx = ssl_context()
    print(
        f"{name}: {len(done_ids)} done, {len(pending)} to run"
        f" layout={layout} criteria={criteria_style}"
        f" labels={labels}"
        f"{' hash-bust' if hash_prefix else ''}"
        f"{f' state-hash-{state_hash_chars}' if state_hash_chars else ''}"
    )

    write_lock = threading.Lock()

    def one(trial_id: int) -> dict[str, Any]:
        use_trial = hash_prefix or state_hash_chars > 0
        wrapped = payload_for(
            name,
            trial_id if use_trial else None,
            layout=layout,
            criteria_style=criteria_style,
            state_hash_chars=state_hash_chars,
            labels=labels,
        )
        meta = wrapped.pop("_meta")
        rec = post_once(key, wrapped, ctx, limiter)
        rec["prompt"] = name
        rec["trial_id"] = trial_id
        rec["trial"] = trial_id
        rec["layout"] = layout
        rec["criteria_style"] = criteria_style
        rec["labels"] = labels
        rec["request_state"] = wrapped["state"]
        rec["request_instructions"] = wrapped["questions"]["face"]["instructions"]
        rec["request_criteria"] = wrapped["questions"]["face"]["criteria"]
        if use_trial:
            rec["cache_bust_hash"] = meta["cache_bust_hash"]
            rec["state_prefix"] = meta.get("state_prefix")
            rec["cache_bust"] = True
        else:
            rec["cache_bust"] = False
        return rec

    with path.open("a") as f, ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(one, tid): tid for tid in pending}
        finished = 0
        for fut in as_completed(futs):
            rec = fut.result()
            with write_lock:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
            finished += 1
            if finished % 100 == 0 or finished == len(pending):
                print(f"  {name} {len(done_ids) + finished}/{n}")
    return path


def summarize(
    out_dir: Path,
    n: int,
    labels: str = "numbers",
    names: list[str] | None = None,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "model": MODEL,
        "n_target": n,
        "prompts": {},
    }
    valid = set(option_labels(labels))
    order = option_labels(labels)
    if names is None:
        names = [p.stem for p in sorted(out_dir.glob("*.jsonl"))]
    for name in names:
        path = out_dir / f"{name}.jsonl"
        counts: Counter[str] = Counter()
        errors = 0
        invalid = 0
        identical_p = None
        n_ok = 0
        hash_bust_count = 0
        if path.exists():
            with path.open() as f:
                for line in f:
                    rec = json.loads(line)
                    if rec.get("cache_bust"):
                        hash_bust_count += 1
                    choice = extract_choice(rec)
                    if choice is None:
                        errors += 1
                        continue
                    if choice not in valid:
                        invalid += 1
                        continue
                    counts[choice] += 1
                    n_ok += 1
                    probs = (
                        ((rec.get("response") or {}).get("answers") or {})
                        .get("face") or {}
                    ).get("probabilities")
                    if identical_p is None:
                        identical_p = probs
                    elif probs != identical_p:
                        identical_p = "VARIED"
        summary["prompts"][name] = {
            "ok": n_ok,
            "errors": errors,
            "invalid": invalid,
            "freq": {k: counts[k] for k in order},
            "probabilities_identical_across_ok_trials": identical_p != "VARIED"
            and identical_p is not None,
            "cache_bust_records": hash_bust_count,
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=N_PER_PROMPT)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--rps", type=float, default=12.0)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Defaults to results/dice_numbers or results/dice_animals",
    )
    parser.add_argument(
        "--prompts",
        nargs="*",
        default=["P1", "P2", "P3", "P3plus"],
    )
    parser.add_argument(
        "--layout",
        choices=("protocol",),
        default="protocol",
        help="state=event, ask which face landed up",
    )
    parser.add_argument(
        "--criteria-style",
        choices=("describe",),
        default="describe",
        help="protocol layout only: one symmetric description per face",
    )
    parser.add_argument(
        "--state-hash-chars",
        type=int,
        default=0,
        help="Prefix state with the first N hex chars of sha256(trial_id); 0 disables",
    )
    parser.add_argument(
        "--labels",
        choices=("numbers", "animals"),
        default="numbers",
        help="Choice option set: 1-6 or cat/dog/bird/fish/horse/cow",
    )
    parser.add_argument(
        "--hash-prefix",
        action="store_true",
        help=(
            "Prefix instructions with sha256(trial_id) hex only "
            "(trial ids 1..n; raw index never included) to bust caches"
        ),
    )
    args = parser.parse_args()

    key = load_api_key()

    if args.out is None:
        root = Path(__file__).resolve().parent.parent
        args.out = root / "results" / f"dice_{args.labels}"
    args.out.mkdir(parents=True, exist_ok=True)
    limiter = RateLimiter(args.rps)
    known = known_prompt_names()
    for name in args.prompts:
        if name not in known:
            raise SystemExit(f"unknown prompt {name}")
        run_condition(
            name,
            args.n,
            key,
            args.out,
            args.workers,
            limiter,
            args.hash_prefix,
            args.layout,
            args.criteria_style,
            args.state_hash_chars,
            args.labels,
        )

    summary = summarize(
        args.out, args.n, labels=args.labels, names=list(args.prompts)
    )
    summary["layout"] = args.layout
    summary["criteria_style"] = args.criteria_style
    summary["state_hash_chars"] = args.state_hash_chars
    summary["labels"] = args.labels
    summary["hash_prefix"] = bool(args.hash_prefix)
    if args.hash_prefix:
        summary["cache_bust"] = {
            "method": "sha256(str(trial_id)).hexdigest() prefixed to instructions",
            "trial_id_range": f"1..{args.n}",
            "raw_index_in_prompt": False,
        }
    summary_path = args.out / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
