#!/usr/bin/env python3
"""Score a blind dsh run on a seed task, using the seed's own scorer.

The scorer runs inside the data image with the seed root and the blind output
mounted read-only. The solver container never saw base/reference.

Usage:
  sg docker -c 'python3 -I scripts/blind_seed_score.py --seed <slug>'
  # or: DOCKER_CMD='sudo docker' python3 -I scripts/blind_seed_score.py --seed <slug>
  # custom roots:
  python3 -I scripts/blind_seed_score.py --seed <slug> --seed-root "$SEED_ROOT" \
    --blind-root "$BLIND_ROOT"
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEED_ROOT = Path(
    os.environ.get(
        "SEED_ROOT",
        str(Path.home() / "下载" / "business_finance_extracted" / "business_finance"),
    )
).expanduser()
DEFAULT_BLIND_ROOT = Path.home() / "ale-blind"
IMAGE = "ale-blind-dsh-data"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--seed-root", type=Path, default=DEFAULT_SEED_ROOT)
    parser.add_argument("--blind-root", type=Path, default=DEFAULT_BLIND_ROOT)
    return parser.parse_args()


def docker_prefix() -> list[str]:
    return os.environ.get("DOCKER_CMD", "docker").split()


def image_exists(image: str) -> bool:
    completed = subprocess.run(
        docker_prefix() + ["image", "inspect", image],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode == 0


def run_container(seed: Path, blind: Path, args: list[str], wrapper: Path | None = None) -> subprocess.CompletedProcess:
    command = docker_prefix() + [
        "run",
        "--rm",
        "--entrypoint",
        "python3",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,exec,size=256m",
        "-v",
        f"{seed}:/seed:ro",
        "-v",
        f"{blind}:/blind:ro",
        "-w",
        "/seed",
    ]
    if wrapper is not None:
        command += ["-v", f"{wrapper}:/scorer.py:ro"]
    command += [IMAGE] + args
    return subprocess.run(command, capture_output=True, text=True, check=False)


def extract_json(text: str) -> dict:
    decoder = json.JSONDecoder()
    start = text.find("{")
    while start != -1:
        try:
            value, _ = decoder.raw_decode(text[start:])
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
        start = text.find("{", start + 1)
    return {}


def write_wrapper(blind: Path, body: str) -> Path:
    path = blind / "eval" / "seed_score_wrapper.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


SEGMENTATION_WRAPPER = """
import importlib.util, json
from pathlib import Path

spec = importlib.util.spec_from_file_location("seed_seg", "/seed/scripts/evaluate_segmentation.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

out = Path("/blind/base/output")
ref = Path("/seed/base/reference")
def read(path):
    return path.read_text(encoding="utf-8", errors="replace")
try:
    result = mod.score_segmentation(
        read(out / "segment_definition.json"),
        read(out / "audience_roster.csv"),
        read(out / "overlap_report.tsv"),
        read(ref / "segment_definition.json"),
        read(ref / "audience_roster.csv"),
        read(ref / "overlap_report.tsv"),
    )
except Exception as exc:
    result = {"score": 0.0, "error": str(exc)}
print(json.dumps(result))
"""

AMERICAN_WRAPPER = """
import importlib.util, json, sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("seed_quant", "/seed/scripts/score_american_option_outputs.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["seed_quant"] = mod
spec.loader.exec_module(mod)

def payloads(root):
    result = {}
    for name in ("results.json", "exercise_boundary_tier2.npy"):
        path = root / name
        if path.is_file():
            result[name] = path.read_bytes()
    return result

try:
    report = mod.score_submission(payloads(Path("/blind/base/output")), payloads(Path("/seed/base/reference")))
    print(json.dumps(report.to_dict()))
except Exception as exc:
    print(json.dumps({"score": 0.0, "error": str(exc)}))
"""


def main() -> int:
    args = parse_args()
    slug = args.seed
    seed = args.seed_root.expanduser() / slug
    blind = args.blind_root.expanduser().resolve() / f"seed-{slug}"
    if not seed.is_dir():
        raise SystemExit(f"unknown seed: {seed}")
    if not blind.is_dir():
        raise SystemExit(f"missing blind workspace: {blind}")
    output_dir = blind / "base" / "output"
    if not output_dir.is_dir() or not any(output_dir.iterdir()):
        raise SystemExit(
            f"blind output is empty: {output_dir}; rerun the seed blind solve first"
        )
    if not image_exists(IMAGE):
        raise SystemExit(
            f"missing scoring image {IMAGE}; build it with "
            f"scripts/blind_docker.sh --seed {slug} --data --build"
        )

    wrapper: Path | None = None
    if slug == "sse_northbound_programmatic_trading_01":
        command = [
            "/seed/scripts/score_research_answers.py",
            "--submission-file",
            "/blind/base/output/research_answers.json",
            "--answer-key-file",
            "/seed/base/reference/answer_key.json",
            "--documents-file",
            "/seed/base/reference/evaluator_documents.json",
            "--manifest-file",
            "/seed/base/input/document_manifest.json",
        ]
    elif slug == "digital_marketing_ab_test_analysis_1":
        command = [
            "/seed/scripts/verify_ab_test_outputs.py",
            "--input-dir",
            "/seed/base/input",
            "--reference-dir",
            "/seed/base/reference",
            "--output-dir",
            "/blind/base/output",
        ]
    elif slug == "digital_marketing_audience_segmentation_1":
        wrapper = write_wrapper(blind, SEGMENTATION_WRAPPER)
        command = ["/scorer.py"]
    elif slug == "american_option_pricing_ls":
        wrapper = write_wrapper(blind, AMERICAN_WRAPPER)
        command = ["/scorer.py"]
    elif slug == "basel_operational_risk_bia_cn":
        command = [
            "/seed/scripts/score_outputs.py",
            "--output",
            "/blind/base/output",
            "--reference",
            "/seed/base/reference",
        ]
    else:
        raise SystemExit(
            f"no blind scorer adapter for seed {slug!r}; "
            "supported: sse, ab_test, segmentation, american_option, basel_bia"
        )

    completed = run_container(seed, blind, command, wrapper)
    parsed = extract_json(completed.stdout)
    score = float(parsed.get("score", 0.0) or 0.0)
    run_meta = {}
    for name in ("model.txt", "image.txt", "started_at.txt"):
        path = blind / "run" / name
        if path.is_file():
            run_meta[name.removesuffix(".txt")] = path.read_text(
                encoding="utf-8"
            ).strip()
    report = {
        "seed": slug,
        "scored_at": datetime.now(timezone.utc).isoformat(),
        "blind_output_dir": str(blind / "base" / "output"),
        "score": score,
        "passed": score >= 1.0,
        "scoring_image": IMAGE,
        "run_meta": run_meta,
        "scorer_returncode": completed.returncode,
        "scorer_result": parsed,
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
    }
    (blind / "eval").mkdir(exist_ok=True)
    (blind / "eval" / "score.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
