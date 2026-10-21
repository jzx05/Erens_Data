#!/usr/bin/env python3
"""Profile AgentHLE seed tasks and propose a quota plan.

Read-only with respect to the seed root. Writes:
  - <out>/seed_profile.json
  - <out>/quotas.json
  - <queue-out> (optional, default state/candidates.jsonl)

The profile is intentionally heuristic: it gives the author and the difficulty
gate a shared starting point, not a ground-truth difficulty label.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

TIER_B_SOFTWARE = {
    "odoo",
    "metabase",
    "flowable",
    "docker",
    "libreoffice",
    "microsoft edge",
    "google chrome",
    "chrome",
    "growthbook",
    "postgresql",
}

QUOTA_20 = {
    "accounting": 4,
    "enterprise_analytics": 4,
    "compliance": 3,
    "sales_marketing": 3,
    "quant_finance": 2,
    "actuarial_risk": 1,
    "supply_chain": 1,
    "litigation": 1,
    "hr_pm": 1,
}

MODALITY_EXTENSIONS = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".json": "json",
    ".jsonl": "jsonl",
    ".md": "markdown",
    ".txt": "text",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".pdf": "pdf",
    ".py": "python",
    ".toml": "toml",
    ".lock": "lock",
    ".html": "html",
    ".xml": "xml",
    ".parquet": "parquet",
    ".arrow": "arrow",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".zip": "archive",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--target", type=int, default=20)
    parser.add_argument("--queue-out", type=Path, default=Path("state/candidates.jsonl"))
    parser.add_argument("--reset", action="store_true", help="Overwrite an existing queue")
    return parser.parse_args()


def safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def iter_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def modalities(files: list[Path]) -> list[str]:
    counts = Counter()
    for path in files:
        counts[MODALITY_EXTENSIONS.get(path.suffix.lower(), path.suffix.lower() or "other")] += 1
    return sorted(counts)


def tier_for(software: list[str], subdomain: str) -> str:
    if subdomain == "graphic_design":
        return "B"
    lowered = " ".join(software).lower()
    return "B" if any(name in lowered for name in TIER_B_SOFTWARE) else "A"


def difficulty_score(features: dict) -> float:
    score = 0.0
    score += min(features["software_count"], 6) * 8
    score += min(features["input_file_count"], 10) * 4
    score += min(features["modality_count"], 8) * 6
    score += min(features["reference_file_count"], 8) * 3
    score += min(features["must_do_count"], 8) * 5
    score += min(features["prompt_chars"] / 1000.0, 10) * 2
    score += 5 if features["has_main_py"] else 0
    score += 5 if features["has_scripts"] else 0
    score += min(features["timeout"] / 7200.0, 1.5) * 5
    return round(min(score, 100.0), 2)


def normalize_vectors(tasks: list[dict], keys: list[str]) -> dict[str, dict[str, float]]:
    values = {key: [task["features"][key] for task in tasks] for key in keys}
    stats = {}
    for key, vals in values.items():
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / len(vals)
        stats[key] = (mean, math.sqrt(var) or 1.0)
    normalized = {}
    for task in tasks:
        normalized[task["slug"]] = {
            key: round((task["features"][key] - stats[key][0]) / stats[key][1], 4)
            for key in keys
        }
    return normalized


def distance(a: dict[str, float], b: dict[str, float]) -> float:
    return round(math.sqrt(sum((a[k] - b[k]) ** 2 for k in a)), 4)


def build_quotas(profile: dict, target: int) -> dict:
    by_subdomain = profile["subdomains"]
    if target == 20:
        quotas = dict(QUOTA_20)
    else:
        tier_a = [name for name, info in by_subdomain.items() if info["count"] > 0]
        quotas = {name: 1 for name in tier_a}
        remaining = max(0, target - len(quotas))
        weights = {name: by_subdomain[name]["count"] for name in tier_a}
        total_weight = sum(weights.values()) or 1
        for name in tier_a:
            quotas[name] += int(round(remaining * weights[name] / total_weight))
        while sum(quotas.values()) > target:
            name = max(quotas, key=quotas.get)
            quotas[name] -= 1
        while sum(quotas.values()) < target:
            name = max(weights, key=weights.get)
            quotas[name] += 1
    return {
        "target": target,
        "strategy": "fixed-20" if target == 20 else "proportional-with-minimum-one",
        "quotas": [
            {
                "subdomain_code": name,
                "subdomain_name": by_subdomain[name]["name"],
                "count": count,
                "seed_count": by_subdomain[name]["count"],
                "tier_a_seeds": by_subdomain[name]["tier_a"],
                "tier_b_seeds": by_subdomain[name]["tier_b"],
            }
            for name, count in sorted(quotas.items(), key=lambda item: (-item[1], item[0]))
        ],
        "deferred": [
            {
                "subdomain_code": "graphic_design",
                "reason": "GUI-heavy; verify in a headless environment before scaling",
            }
        ],
    }


def build_queue(profile: dict, quotas: dict) -> list[dict]:
    tasks_by_subdomain = defaultdict(list)
    for task in profile["tasks"]:
        tasks_by_subdomain[task["subdomain_code"]].append(task)

    queue = []
    for quota in quotas["quotas"]:
        subdomain = quota["subdomain_code"]
        seeds = sorted(tasks_by_subdomain[subdomain], key=lambda t: t["difficulty_score"])
        for index in range(1, quota["count"] + 1):
            anchor = seeds[(index - 1) % len(seeds)]
            nearest = [anchor["slug"]] + [
                item["slug"] for item in anchor.get("nearest_seeds", [])[:1]
            ]
            queue.append(
                {
                    "id": f"bf-{subdomain.replace('_', '-')}-{index:02d}",
                    "status": "QUEUED",
                    "stratum": subdomain,
                    "seed_anchor": anchor["slug"],
                    "seed_refs": nearest,
                    "difficulty_target": anchor["difficulty_score"],
                    "attempts": 0,
                    "reason_codes": [],
                    "paths": {},
                }
            )
    return queue


def main() -> None:
    args = parse_args()
    seed_root = args.seeds.expanduser().resolve()
    out_dir = args.out.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    tasks = []
    for card_path in sorted(seed_root.glob("*/task_card.json")):
        card = json.loads(card_path.read_text(encoding="utf-8"))
        task_dir = card_path.parent
        input_files = iter_files(task_dir / "base" / "input")
        reference_files = iter_files(task_dir / "base" / "reference")
        software = card.get("software", [])
        taxonomy = card.get("taxonomy", {})
        features = {
            "software_count": len(software),
            "input_file_count": len(card.get("inputFiles", [])),
            "base_input_file_count": len(input_files),
            "base_input_bytes": sum(safe_size(path) for path in input_files),
            "reference_file_count": len(reference_files),
            "prompt_chars": len(card.get("taskPrompt", "")),
            "must_do_count": len(card.get("agentMustDo", [])),
            "evaluation_chars": len(card.get("evaluation", "")),
            "timeout": int(card.get("vm", {}).get("timeout", 0) or 0),
            "modality_count": len(modalities(input_files)),
            "has_main_py": int((task_dir / "main.py").is_file()),
            "has_scripts": int(any((task_dir / "scripts").glob("*.py"))),
        }
        features["log_input_bytes"] = round(math.log1p(features["base_input_bytes"]), 4)
        features["prompt_kchars"] = round(features["prompt_chars"] / 1000.0, 4)
        features["evaluation_kchars"] = round(features["evaluation_chars"] / 1000.0, 4)
        features["timeout_units"] = round(features["timeout"] / 7200.0, 4)
        subdomain = taxonomy.get("subdomain_code", "unknown")
        task = {
            "slug": task_dir.name,
            "task_id": card.get("taskId", task_dir.name),
            "title": card.get("title", ""),
            "subdomain_code": subdomain,
            "subdomain_name": taxonomy.get("subdomain_name", ""),
            "domain_code": taxonomy.get("domain_code", ""),
            "software": software,
            "tier": tier_for(software, subdomain),
            "features": features,
            "modalities": modalities(input_files),
            "difficulty_score": difficulty_score(features),
        }
        tasks.append(task)

    # Structural difficulty vector. Do not include metadata-completeness fields
    # (inputFiles count, agentMustDo count, evaluation prose length) because some
    # seed cards omit them entirely; including them measures card formatting,
    # not task difficulty.
    vector_keys = [
        "software_count",
        "base_input_file_count",
        "log_input_bytes",
        "reference_file_count",
        "timeout_units",
        "modality_count",
    ]
    vectors = normalize_vectors(tasks, vector_keys)
    for task in tasks:
        own = vectors[task["slug"]]
        neighbors = sorted(
            (
                {"slug": other["slug"], "distance": distance(own, vectors[other["slug"]])}
                for other in tasks
                if other["slug"] != task["slug"]
            ),
            key=lambda item: item["distance"],
        )[:3]
        task["nearest_seeds"] = neighbors

    subdomains = {}
    for task in tasks:
        info = subdomains.setdefault(
            task["subdomain_code"],
            {"name": task["subdomain_name"], "count": 0, "tier_a": 0, "tier_b": 0},
        )
        info["count"] += 1
        info[f"tier_{task['tier'].lower()}"] += 1

    profile = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed_root": str(seed_root),
        "target": args.target,
        "task_count": len(tasks),
        "subdomains": subdomains,
        "vector_keys": vector_keys,
        "tasks": sorted(tasks, key=lambda task: (task["subdomain_code"], task["slug"])),
    }
    (out_dir / "seed_profile.json").write_text(
        json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    quotas = build_quotas(profile, args.target)
    (out_dir / "quotas.json").write_text(
        json.dumps(quotas, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    queue_path = args.queue_out.expanduser().resolve()
    if args.reset or not queue_path.exists():
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        queue = build_queue(profile, quotas)
        queue_path.write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in queue),
            encoding="utf-8",
        )
        queue_note = f"wrote {queue_path} ({len(queue)} candidates)"
    else:
        queue_note = f"kept existing {queue_path} (use --reset to overwrite)"

    print(f"seeds: {len(tasks)} tasks under {seed_root}")
    print(f"{'subdomain':24} {'seeds':>5} {'tierA':>5} {'tierB':>5} {'quota':>5}")
    quota_map = {item["subdomain_code"]: item["count"] for item in quotas["quotas"]}
    for name, info in sorted(subdomains.items()):
        print(
            f"{name:24} {info['count']:>5} {info['tier_a']:>5} {info['tier_b']:>5}"
            f" {quota_map.get(name, 0):>5}"
        )
    print(f"wrote {out_dir / 'seed_profile.json'}")
    print(f"wrote {out_dir / 'quotas.json'}")
    print(queue_note)


if __name__ == "__main__":
    main()
