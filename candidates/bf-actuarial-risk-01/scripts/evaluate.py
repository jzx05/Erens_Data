#!/usr/bin/env python3
"""Standalone evaluator for bf-actuarial-risk-01.

Compares the submission under ``--output-dir`` with the gold files in
``base/reference/gold``.  The scoring is all-or-nothing, mirroring the seed task:

  score = 1.0 only when
    * all three output files exist and parse;
    * classified_events.csv contains each of the 60 ledger Event_IDs exactly once;
    * every category is EL1-EL7 and every business line is BL1-BL8;
    * loss-event category accuracy  >= 0.90;
    * business-line accuracy         >= 0.90;
    * loss-amount accuracy           == 1.00;
    * capital_calculation.json matches the gold BIA values.

  otherwise score = 0.0.

Usage:
  python3 -I scripts/evaluate.py --candidate-root <dir> --output-dir <dir>
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

REQUIRED_OUTPUTS = ("classified_events.csv", "capital_calculation.json", "execution_log.txt")
CLASSIFIED_COLUMNS = ("Event_ID", "Loss_Event_Category", "Business_Line", "Loss_Amount_CNY")
CAPITAL_KEYS = (
    "alpha",
    "gross_income_years",
    "positive_year_count",
    "positive_gi_sum_cny",
    "average_positive_gi_cny",
    "or_capital_cny",
)
VALID_EL = {f"EL{i}" for i in range(1, 8)}
VALID_BL = {f"BL{i}" for i in range(1, 9)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def as_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return Decimal(str(value))
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if not text:
            return None
        try:
            return Decimal(text)
        except InvalidOperation:
            return None
    return None


def as_number(value: Any) -> float | None:
    number = as_decimal(value)
    return None if number is None else float(number)


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]], list[str]]:
    errors: list[str] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    if fieldnames != list(CLASSIFIED_COLUMNS):
        errors.append(
            "classified_events.csv header must be exactly " + ",".join(CLASSIFIED_COLUMNS)
        )
    return fieldnames, rows, errors


def main() -> None:
    args = parse_args()
    root = (args.candidate_root or Path(__file__).resolve().parent.parent).resolve()
    output_dir = (args.output_dir or root / "base" / "output").resolve()

    contract = load_json(root / "base" / "reference" / "verification_contract.json")
    tolerance = Decimal(str(contract.get("tolerance", 0.01)))
    category_min = Decimal(str(contract.get("category_accuracy_min", 0.9)))
    business_line_min = Decimal(str(contract.get("business_line_accuracy_min", 0.9)))
    expected_count = int(contract.get("event_count", 60))

    gold_dir = root / "base" / "reference" / "gold"
    gold_fields, gold_rows, gold_errors = read_rows(gold_dir / "classified_events.csv")
    gold_capital = load_json(gold_dir / "capital_calculation.json")

    errors: list[str] = list(gold_errors)
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, expected: Any = None, actual: Any = None) -> bool:
        checks.append({"name": name, "passed": bool(passed), "expected": expected, "actual": actual})
        return bool(passed)

    # ---------------------------------------------------------------- file presence
    missing = [name for name in REQUIRED_OUTPUTS if not (output_dir / name).is_file()]
    if missing:
        errors.append("missing required output files: " + ", ".join(missing))

    execution_log_ok = False
    log_path = output_dir / "execution_log.txt"
    if log_path.is_file():
        try:
            log_text = log_path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError as exc:
            log_text = ""
            errors.append(f"execution_log.txt unreadable: {exc}")
        execution_log_ok = bool(log_text)
        if not execution_log_ok:
            errors.append("execution_log.txt is empty")

    # ------------------------------------------------------------ classification CSV
    submitted_rows: list[dict[str, str]] = []
    csv_ok = False
    csv_path = output_dir / "classified_events.csv"
    if csv_path.is_file():
        try:
            _, submitted_rows, header_errors = read_rows(csv_path)
            errors.extend(header_errors)
            csv_ok = True
        except (OSError, UnicodeError, csv.Error) as exc:
            errors.append(f"classified_events.csv unreadable: {exc}")

    gold_by_id: dict[str, dict[str, Any]] = {}
    for row in gold_rows:
        event_id = str(row.get("Event_ID", "")).strip()
        gold_by_id[event_id] = {
            "category": str(row.get("Loss_Event_Category", "")).strip().upper(),
            "business_line": str(row.get("Business_Line", "")).strip().upper(),
            "amount": as_decimal(row.get("Loss_Amount_CNY")),
        }

    submitted_by_id: dict[str, dict[str, Any]] = {}
    submitted_duplicates: list[str] = []
    for index, row in enumerate(submitted_rows, start=2):
        event_id = str(row.get("Event_ID", "")).strip()
        if not event_id:
            errors.append(f"classified_events.csv row {index} is missing Event_ID")
            continue
        if event_id in submitted_by_id:
            submitted_duplicates.append(event_id)
            errors.append(f"classified_events.csv has duplicate Event_ID {event_id}")
            continue
        category_raw = str(row.get("Loss_Event_Category", "") or "").strip().upper()
        business_line_raw = str(row.get("Business_Line", "") or "").strip().upper()
        if category_raw and category_raw not in VALID_EL:
            errors.append(f"classified_events.csv {event_id} has invalid Loss_Event_Category {category_raw!r}")
        if business_line_raw and business_line_raw not in VALID_BL:
            errors.append(f"classified_events.csv {event_id} has invalid Business_Line {business_line_raw!r}")
        submitted_by_id[event_id] = {
            "category": category_raw,
            "business_line": business_line_raw,
            "amount": as_decimal(row.get("Loss_Amount_CNY")),
        }

    expected_ids = set(gold_by_id)
    actual_ids = set(submitted_by_id)
    if actual_ids != expected_ids:
        missing_ids = sorted(expected_ids - actual_ids)
        extra_ids = sorted(actual_ids - expected_ids)
        if missing_ids:
            errors.append("classified_events.csv missing Event_IDs: " + ", ".join(missing_ids[:10]))
        if extra_ids:
            errors.append("classified_events.csv has unexpected Event_IDs: " + ", ".join(extra_ids[:10]))

    total = len(gold_by_id)
    category_correct = 0
    business_line_correct = 0
    loss_amount_correct = 0
    details: list[dict[str, Any]] = []
    for event_id in sorted(gold_by_id):
        gold = gold_by_id[event_id]
        submitted = submitted_by_id.get(event_id)
        if submitted is None:
            details.append(
                {
                    "Event_ID": event_id,
                    "expected_category": gold["category"],
                    "expected_business_line": gold["business_line"],
                    "expected_loss_amount_cny": str(gold["amount"]),
                    "actual_category": None,
                    "actual_business_line": None,
                    "actual_loss_amount_cny": None,
                    "category_correct": False,
                    "business_line_correct": False,
                    "loss_amount_correct": False,
                }
            )
            continue
        category_ok = submitted["category"] == gold["category"]
        business_line_ok = submitted["business_line"] == gold["business_line"]
        amount_ok = submitted["amount"] is not None and submitted["amount"] == gold["amount"]
        category_correct += int(category_ok)
        business_line_correct += int(business_line_ok)
        loss_amount_correct += int(amount_ok)
        details.append(
            {
                "Event_ID": event_id,
                "expected_category": gold["category"],
                "expected_business_line": gold["business_line"],
                "expected_loss_amount_cny": str(gold["amount"]),
                "actual_category": submitted["category"],
                "actual_business_line": submitted["business_line"],
                "actual_loss_amount_cny": None if submitted["amount"] is None else str(submitted["amount"]),
                "category_correct": category_ok,
                "business_line_correct": business_line_ok,
                "loss_amount_correct": amount_ok,
            }
        )

    category_accuracy = Decimal(category_correct) / Decimal(total) if total else Decimal("0")
    business_line_accuracy = Decimal(business_line_correct) / Decimal(total) if total else Decimal("0")
    loss_amount_accuracy = Decimal(loss_amount_correct) / Decimal(total) if total else Decimal("0")

    # -------------------------------------------------------------------- capital
    capital_checks: dict[str, Any] = {}
    capital_correct = False
    capital_path = output_dir / "capital_calculation.json"
    if not capital_path.is_file():
        errors.append("capital_calculation.json is missing")
    else:
        try:
            submitted_capital = load_json(capital_path)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            submitted_capital = None
            errors.append(f"capital_calculation.json unreadable: {exc}")

        if not isinstance(submitted_capital, dict):
            errors.append("capital_calculation.json must be a JSON object")
        else:
            extra_keys = sorted(set(submitted_capital) - set(CAPITAL_KEYS))
            missing_keys = sorted(set(CAPITAL_KEYS) - set(submitted_capital))
            if missing_keys:
                errors.append("capital_calculation.json missing keys: " + ", ".join(missing_keys))
            if extra_keys:
                errors.append("capital_calculation.json has unexpected keys: " + ", ".join(extra_keys))

            alpha_ok = False
            alpha = as_number(submitted_capital.get("alpha"))
            if alpha is not None and abs(alpha - float(gold_capital["alpha"])) <= 1e-9:
                alpha_ok = True
            else:
                errors.append("capital_calculation.json alpha is not 0.15")
            capital_checks["alpha"] = {"passed": alpha_ok, "expected": gold_capital["alpha"], "actual": submitted_capital.get("alpha")}

            count_ok = False
            count_value = as_number(submitted_capital.get("positive_year_count"))
            if count_value is not None and count_value == float(gold_capital["positive_year_count"]):
                count_ok = True
            else:
                errors.append("capital_calculation.json positive_year_count is wrong")
            capital_checks["positive_year_count"] = {
                "passed": count_ok,
                "expected": gold_capital["positive_year_count"],
                "actual": submitted_capital.get("positive_year_count"),
            }

            years_ok = False
            submitted_years = submitted_capital.get("gross_income_years")
            if not isinstance(submitted_years, dict):
                errors.append("capital_calculation.json gross_income_years must be an object")
            else:
                gold_years = gold_capital["gross_income_years"]
                if set(submitted_years) != set(gold_years):
                    errors.append(
                        "capital_calculation.json gross_income_years keys must be exactly "
                        + ", ".join(sorted(gold_years))
                    )
                else:
                    years_ok = True
                    for year, expected_value in gold_years.items():
                        actual_value = as_decimal(submitted_years.get(year))
                        if actual_value is None or abs(actual_value - Decimal(str(expected_value))) > tolerance:
                            years_ok = False
                            errors.append(
                                f"capital_calculation.json gross_income_years[{year}] is wrong"
                            )
            capital_checks["gross_income_years"] = {"passed": years_ok}

            money_ok = True
            for key in ("positive_gi_sum_cny", "average_positive_gi_cny", "or_capital_cny"):
                expected_value = Decimal(str(gold_capital[key]))
                actual_value = as_decimal(submitted_capital.get(key))
                key_ok = actual_value is not None and abs(actual_value - expected_value) <= tolerance
                if not key_ok:
                    money_ok = False
                    errors.append(f"capital_calculation.json {key} is wrong")
                capital_checks[key] = {
                    "passed": key_ok,
                    "expected": float(expected_value),
                    "actual": submitted_capital.get(key),
                }

            capital_correct = (
                alpha_ok and count_ok and years_ok and money_ok and not missing_keys and not extra_keys
            )

    # ------------------------------------------------------------------ verdict
    passed = (
        not errors
        and csv_ok
        and execution_log_ok
        and total == expected_count
        and category_accuracy >= category_min
        and business_line_accuracy >= business_line_min
        and loss_amount_accuracy == Decimal("1")
        and capital_correct
    )

    wrong_category_ids = [d["Event_ID"] for d in details if not d["category_correct"]]
    wrong_business_line_ids = [d["Event_ID"] for d in details if not d["business_line_correct"]]
    wrong_amount_ids = [d["Event_ID"] for d in details if not d["loss_amount_correct"]]

    report = {
        "score": 1.0 if passed else 0.0,
        "pass_fail": passed,
        "errors": errors,
        "total_events": total,
        "category_correct": category_correct,
        "business_line_correct": business_line_correct,
        "loss_amount_correct": loss_amount_correct,
        "category_accuracy": float(round(category_accuracy, 6)),
        "business_line_accuracy": float(round(business_line_accuracy, 6)),
        "loss_amount_accuracy": float(round(loss_amount_accuracy, 6)),
        "category_accuracy_min": float(category_min),
        "business_line_accuracy_min": float(business_line_min),
        "loss_amount_accuracy_required": 1.0,
        "wrong_category_ids": wrong_category_ids,
        "wrong_business_line_ids": wrong_business_line_ids,
        "wrong_amount_ids": wrong_amount_ids,
        "capital_correct": capital_correct,
        "capital_checks": capital_checks,
        "checks": checks,
        "details": details,
        "notes": [
            "All-or-nothing scoring: 1.0 only if category accuracy >= 0.90, business-line "
            "accuracy >= 0.90, loss-amount accuracy == 1.00, capital correct, and no structural "
            f"errors. Monetary values use an absolute tolerance of {tolerance} CNY."
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
