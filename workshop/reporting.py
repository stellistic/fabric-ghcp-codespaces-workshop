"""Narrow offline Date-filter simulator, NOT a DAX engine or live Power BI proof."""

import hashlib
import json
import math
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

from workshop.io import ROOT, read_csv, read_json, write_json

DATE_EDGE = ("fact_production_run", "DateKey", "dim_date", "DateKey")


def _edge(rel):
    return tuple(rel[key] for key in ("from_table", "from_column", "to_table", "to_column"))


def source_months(data: Path) -> list[dict]:
    with sqlite3.connect(":memory:") as connection:
        for file, table in (("FactProductionRun", "raw_runs"), ("DimDate", "raw_dates")):
            header, rows = read_csv(data / f"{file}.csv")
            if any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", column) for column in header):
                raise ValueError("invalid source column identifier")
            columns = ", ".join(f'"{column}" TEXT' for column in header)
            connection.execute(f"CREATE TABLE {table} ({columns})")
            placeholders = ",".join("?" for _ in header)
            connection.executemany(
                f"INSERT INTO {table} VALUES ({placeholders})",
                [tuple(row[column] for column in header) for row in rows],
            )
        result = connection.execute((ROOT / "queries/monthly-source.sql").read_text()).fetchall()
    return [{"YearMonth": month, "Actual Units": value} for month, value in result]


def inject_fault(contract: Path, state: Path) -> None:
    if state.exists():
        raise ValueError("model fixture already exists; preserve evidence or explicitly remove that fixture first")
    model = read_json(contract)
    edges = [rel for rel in model["relationships"] if _edge(rel) == DATE_EDGE]
    if len(edges) != 1:
        raise ValueError("expected exactly one production Date relationship")
    model["scope"] = "offline-synthetic"
    write_json(state.with_suffix(".original.json"), model)
    edges[0]["active"] = False
    write_json(state, model)


def model_months(gold: Path, state: Path) -> list[dict]:
    model = read_json(state)
    if model.get("scope") != "offline-synthetic":
        raise ValueError("only the offline-synthetic fixture is supported")
    measure = next((measure for measure in model["measures"] if measure["name"] == "Actual Units"), None)
    if measure is None or re.sub(r"\s+", "", measure["dax"]) != "SUM('fact_production_run'[ActualUnits])":
        raise ValueError("this simulator supports only the contract Actual Units SUM measure")
    _, dates = read_csv(gold / "dim_date.csv")
    _, runs = read_csv(gold / "fact_production_run.csv")
    months = {row["DateKey"]: row["YearMonth"] for row in dates}
    filtered = defaultdict(int)
    for row in runs:
        filtered[months[row["DateKey"]]] += int(row["ActualUnits"])
    edges = [rel for rel in model["relationships"] if _edge(rel) == DATE_EDGE]
    active = len(edges) == 1 and edges[0]["active"] is True
    total = sum(filtered.values())
    return [
        {"YearMonth": month, "Actual Units": filtered[month] if active else total}
        for month in sorted(filtered)
    ]


def compare_months(expected: list[dict], actual: list[dict]) -> list[str]:
    """Counts must match exactly: no tolerance, rounding, coercion or missing months."""
    problems = []

    def keyed(rows, label):
        result = {}
        if not isinstance(rows, list) or not rows:
            problems.append(f"{label}: expected a nonempty array")
            return result
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"YearMonth", "Actual Units"}:
                problems.append(f"{label}: invalid column shape")
                continue
            month, units = row["YearMonth"], row["Actual Units"]
            if not isinstance(month, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
                problems.append(f"{label}: invalid month")
                continue
            if type(units) not in (int, float) or not math.isfinite(units) or units < 0 or int(units) != units:
                problems.append(f"{label}: {month} must have finite nonnegative integral units")
                continue
            if month in result:
                problems.append(f"{label}: duplicate month {month}")
            result[month] = units
        return result

    source, model = keyed(expected, "source"), keyed(actual, "model")
    if set(source) != set(model):
        problems.append("month coverage differs")
    for month in sorted(set(source) & set(model)):
        if source[month] != model[month]:
            problems.append(f"{month}: source={source[month]}, model={model[month]}")
    if sum(source.values()) != sum(model.values()):
        problems.append("grand total differs")
    return problems


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def plan_repair(state: Path) -> dict:
    model = read_json(state)
    if model.get("scope") != "offline-synthetic":
        raise ValueError("refusing a non-offline fixture")
    matches = [rel for rel in model["relationships"] if _edge(rel) == DATE_EDGE]
    if len(matches) != 1 or matches[0]["active"] is not False:
        raise ValueError("expected precisely the seeded inactive Date relationship")
    plan = {
        "scope": "offline-synthetic",
        "base_sha256": hashlib.sha256(state.read_bytes()).hexdigest(),
        "changes": [{"relationship": list(DATE_EDGE), "before": False, "after": True}],
    }
    return {**plan, "sha256": _digest(plan)}


def apply_repair(state: Path, plan: dict, approval: str) -> None:
    current_plan = plan_repair(state)
    if plan.get("base_sha256") != current_plan["base_sha256"]:
        raise ValueError("model changed since review; obtain new evidence and approval")
    if plan != current_plan or approval != current_plan["sha256"]:
        raise ValueError("positive approval must exactly match the reviewed plan SHA256")
    model = read_json(state)
    for rel in model["relationships"]:
        if _edge(rel) == DATE_EDGE:
            rel["active"] = True
    write_json(state.with_suffix(".before-repair.json"), read_json(state))
    write_json(state, model)
