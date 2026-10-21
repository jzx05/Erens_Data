#!/usr/bin/env python3
"""Write the gold outputs for the audience-segmentation task."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from pathlib import Path


def load_stats():
    path = Path(__file__).with_name("stats.py")
    spec = importlib.util.spec_from_file_location("segmentation_stats", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--candidate-root", type=Path, default=None)
    args = parser.parse_args()
    root = (args.candidate_root or Path(__file__).resolve().parent.parent).resolve()
    stats = load_stats()
    result = stats.compute(root)
    args.out.mkdir(parents=True, exist_ok=True)

    (args.out / "segment_definition.json").write_text(
        json.dumps(result["segment_definition"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with (args.out / "audience_roster.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=stats.ROSTER_COLUMNS)
        writer.writeheader()
        writer.writerows(result["roster"])
    with (args.out / "overlap_report.tsv").open("w", encoding="utf-8", newline="") as handle:
        columns = [
            "existing_audience_id",
            "existing_audience_name",
            "overlap_count",
            "overlap_pct",
            "flag_high_overlap",
        ]
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in result["overlaps"]:
            writer.writerow(
                {
                    "existing_audience_id": row["existing_audience_id"],
                    "existing_audience_name": row["existing_audience_name"],
                    "overlap_count": row["overlap_count"],
                    "overlap_pct": row["overlap_pct"],
                    "flag_high_overlap": "True" if row["flag_high_overlap"] else "False",
                }
            )
    print(f"wrote gold outputs to {args.out}")


if __name__ == "__main__":
    main()
