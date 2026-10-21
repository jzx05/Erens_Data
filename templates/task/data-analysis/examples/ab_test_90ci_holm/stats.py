"""Shared statistics for the 90% CI + Holm A/B test task."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from statistics import NormalDist

N = NormalDist()
Z90 = N.inv_cdf(0.95)
METRICS = [
    ("opened_rate", "opened", True),
    ("clicked_rate", "clicked", False),
    ("converted_rate", "converted", False),
    ("unsubscribed_rate", "unsubscribed", False),
]
SECONDARY = ["clicked_rate", "converted_rate", "unsubscribed_rate"]


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def compute(root: Path) -> dict:
    root = Path(root)
    raw = read_csv(root / "base" / "input" / "experiment_results_raw.csv")
    hist = read_csv(root / "base" / "input" / "historical_metrics.csv")

    n_control = sum(1 for row in raw if row["variant"] == "control")
    n_treatment = sum(1 for row in raw if row["variant"] == "treatment")
    chi2 = (n_treatment - n_control) ** 2 / (n_control + n_treatment)
    srm_pvalue = math.erfc(math.sqrt(chi2 / 2))

    metrics = {}
    for metric, column, is_primary in METRICS:
        control = [
            int(row[column])
            for row in raw
            if row["variant"] == "control" and row["delivered"] == "1"
        ]
        treatment = [
            int(row[column])
            for row in raw
            if row["variant"] == "treatment" and row["delivered"] == "1"
        ]
        pc = sum(control) / len(control)
        pt = sum(treatment) / len(treatment)
        lift = pt - pc
        se = math.sqrt(pc * (1 - pc) / len(control) + pt * (1 - pt) / len(treatment))
        pooled = (sum(control) + sum(treatment)) / (len(control) + len(treatment))
        sep = (
            math.sqrt(pooled * (1 - pooled) * (1 / len(control) + 1 / len(treatment)))
            if pooled not in (0.0, 1.0)
            else 0.0
        )
        z = lift / sep if sep else 0.0
        pvalue = 2 * (1 - N.cdf(abs(z)))
        metrics[metric] = {
            "is_primary": is_primary,
            "control_rate": pc,
            "treatment_rate": pt,
            "absolute_lift": lift,
            "relative_lift_pct": (lift / pc * 100) if pc else None,
            "ci_lower_90": lift - Z90 * se,
            "ci_upper_90": lift + Z90 * se,
            "z_statistic": z,
            "p_value_raw": pvalue,
            "significant_at_05": pvalue < 0.05,
            "holm_rank": None,
            "holm_threshold": None,
            "holm_significant": None,
        }

    ordered = sorted(SECONDARY, key=lambda metric: metrics[metric]["p_value_raw"])
    still_rejecting = True
    for rank, metric in enumerate(ordered, 1):
        threshold = 0.05 / (len(ordered) - rank + 1)
        significant = still_rejecting and metrics[metric]["p_value_raw"] <= threshold
        if not significant:
            still_rejecting = False
        metrics[metric]["holm_rank"] = rank
        metrics[metric]["holm_threshold"] = threshold
        metrics[metric]["holm_significant"] = significant

    baseline = sum(float(row["open_rate"]) for row in hist) / len(hist)
    alpha = 0.05
    power = 0.80
    mde = 0.03
    za = N.inv_cdf(1 - alpha / 2)
    zb = N.inv_cdf(power)
    p1 = baseline
    p2 = baseline + mde
    pooled = (p1 + p2) / 2
    required = math.ceil(
        (
            (za * math.sqrt(2 * pooled * (1 - pooled)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2)))
            ** 2
        )
        / (mde**2)
    )

    decision = (
        "ship"
        if metrics["opened_rate"]["p_value_raw"] < 0.05
        and metrics["unsubscribed_rate"]["absolute_lift"] <= 0.003
        else "hold"
    )

    return {
        "n_control": n_control,
        "n_treatment": n_treatment,
        "ratio": n_treatment / n_control,
        "srm_chi2": chi2,
        "srm_pvalue": srm_pvalue,
        "srm_pass": srm_pvalue > 0.05,
        "metrics": metrics,
        "historical_open_baseline": baseline,
        "required_per_arm": required,
        "decision": decision,
    }
