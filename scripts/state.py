#!/usr/bin/env python3
"""Read and update the candidate queue.

Usage:
  python3 -I scripts/state.py next
  python3 -I scripts/state.py get <id>
  python3 -I scripts/state.py set-status <id> <status>
  python3 -I scripts/state.py append-decision <id> <status> [reason_code ...]
  python3 -I scripts/state.py summary
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "state" / "candidates.jsonl"
DECISIONS = ROOT / "state" / "decisions.jsonl"

ALLOWED = {
    "QUEUED",
    "SCOUTED",
    "AUTHORED",
    "VERIFIED",
    "REVIEWED",
    "ACCEPTED",
    "REVISE",
    "REJECTED",
    "HUMAN_QUEUE",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_queue() -> list[dict]:
    if not QUEUE.exists():
        raise SystemExit(f"missing queue: {QUEUE}")
    items = []
    for line_number, line in enumerate(QUEUE.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{QUEUE}:{line_number}: invalid JSON: {exc}") from exc
    return items


def save_queue(items: list[dict]) -> None:
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    tmp = QUEUE.with_suffix(".jsonl.tmp")
    tmp.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items),
        encoding="utf-8",
    )
    tmp.replace(QUEUE)


def find(items: list[dict], candidate_id: str) -> dict:
    for item in items:
        if item.get("id") == candidate_id:
            return item
    raise SystemExit(f"unknown candidate: {candidate_id}")


def append_decision(candidate_id: str, status: str, reason_codes: list[str]) -> None:
    DECISIONS.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "at": now(),
        "candidate_id": candidate_id,
        "status": status,
        "reason_codes": reason_codes,
    }
    with DECISIONS.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def cmd_next(_: argparse.Namespace) -> int:
    items = load_queue()
    for item in items:
        if item.get("status") == "QUEUED":
            print(json.dumps(item, ensure_ascii=False))
            return 0
    print("no QUEUED candidates", file=sys.stderr)
    return 1


def cmd_get(args: argparse.Namespace) -> int:
    print(json.dumps(find(load_queue(), args.id), ensure_ascii=False, indent=2))
    return 0


def cmd_set_status(args: argparse.Namespace) -> int:
    if args.status not in ALLOWED:
        raise SystemExit(f"invalid status: {args.status}; allowed: {sorted(ALLOWED)}")
    items = load_queue()
    item = find(items, args.id)
    item["status"] = args.status
    item["updated_at"] = now()
    if args.status == "REVISE":
        item["attempts"] = int(item.get("attempts", 0)) + 1
    save_queue(items)
    append_decision(args.id, args.status, [])
    print(f"{args.id} -> {args.status}")
    return 0


def cmd_append_decision(args: argparse.Namespace) -> int:
    append_decision(args.id, args.status, args.reason_codes)
    print(f"decision appended for {args.id}: {args.status} {args.reason_codes}")
    return 0


def cmd_summary(_: argparse.Namespace) -> int:
    items = load_queue()
    by_status: dict[str, int] = {}
    by_stratum: dict[str, int] = {}
    accepted_by_stratum: dict[str, int] = {}
    for item in items:
        status = item.get("status", "UNKNOWN")
        stratum = item.get("stratum", "UNKNOWN")
        by_status[status] = by_status.get(status, 0) + 1
        by_stratum[stratum] = by_stratum.get(stratum, 0) + 1
        if status == "ACCEPTED":
            accepted_by_stratum[stratum] = accepted_by_stratum.get(stratum, 0) + 1
    print(
        json.dumps(
            {
                "total": len(items),
                "by_status": dict(sorted(by_status.items())),
                "by_stratum": dict(sorted(by_stratum.items())),
                "accepted_by_stratum": dict(sorted(accepted_by_stratum.items())),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_next = sub.add_parser("next")
    p_next.set_defaults(func=cmd_next)

    p_get = sub.add_parser("get")
    p_get.add_argument("id")
    p_get.set_defaults(func=cmd_get)

    p_set = sub.add_parser("set-status")
    p_set.add_argument("id")
    p_set.add_argument("status")
    p_set.set_defaults(func=cmd_set_status)

    p_decision = sub.add_parser("append-decision")
    p_decision.add_argument("id")
    p_decision.add_argument("status")
    p_decision.add_argument("reason_codes", nargs="*")
    p_decision.set_defaults(func=cmd_append_decision)

    p_summary = sub.add_parser("summary")
    p_summary.set_defaults(func=cmd_summary)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
