"""Small deterministic reference implementation; Spark stays in Fabric."""

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from workshop.discovery import validate_dictionary
from workshop.io import ROOT, read_csv, read_json, write_json


def _date(value: str) -> str:
    for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"unrecognized date: {value!r}")


def _convert(value: str, kind: str):
    value = value.strip()
    if not value:
        return None
    if kind == "integer":
        return int(value)
    if kind == "decimal":
        number = Decimal(value.replace(",", "").replace("$", ""))
        if not number.is_finite():
            raise ValueError("nonfinite quantity")
        return number
    if kind == "date":
        return _date(value)
    return value


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing empty synthetic output: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def curate(data: Path, output: Path, dictionary: Path) -> dict:
    graph = validate_dictionary(dictionary, data)
    tables = {}
    rejects = []
    duplicate_count = 0
    for entity in graph["entities"]:
        table = entity["gold"]
        if table is None:
            continue
        _, raw = read_csv(data / f"{entity['source']}.csv")
        seen = set()
        cleaned = []
        for original in raw:
            fingerprint = tuple(original.values())
            if fingerprint in seen:
                duplicate_count += 1
                continue
            seen.add(fingerprint)
            reason = None
            if table.startswith("fact_"):
                try:
                    datetime.strptime(original["DateKey"], "%Y%m%d")
                except ValueError:
                    reason = "invalid_date"
            if table == "fact_production_run" and reason is None:
                if not original["ActualUnits"].strip():
                    reason = "missing_actual_units"
                elif int(original["ScrapUnits"]) < 0:
                    reason = "negative_scrap"
            if table == "fact_quality_inspection" and reason is None:
                if int(original["DefectCount"]) > int(original["InspectedUnits"]):
                    reason = "defects_exceed_inspected"
            if reason:
                rejects.append({
                    "SourceTable": table,
                    "RecordKey": original[entity["key"]],
                    "DqReason": reason,
                    "RecordJson": json.dumps(original, sort_keys=True),
                })
                continue
            normalized = dict(original)
            if "PreventiveFlag" in normalized:
                flag = normalized["PreventiveFlag"].strip().upper()
                if flag not in {"0", "1", "Y", "YES", "TRUE", "N", "NO", "FALSE"}:
                    raise ValueError("unrecognized preventive flag")
                normalized["PreventiveFlag"] = "1" if flag in {"1", "Y", "YES", "TRUE"} else "0"
            row = {
                column: _convert(value, graph["attributes"][column][0])
                for column, value in normalized.items()
            }
            if table == "fact_production_run":
                match = re.fullmatch(r"TEAM[-_ ]?([A-C])", original["OperatorTeam"].strip().upper())
                if not match:
                    raise ValueError("unrecognized operator team")
                row["OperatorTeam"] = f"Team-{match[1]}"
                row["TotalUnits"] = row["ActualUnits"] + row["ScrapUnits"]
            if table == "fact_quality_inspection":
                row["DefectTypeKey"] = row["DefectTypeKey"] if row["DefectTypeKey"] is not None else -1
                row["Severity"] = row["Severity"].title()
                if row["Severity"] not in graph["enums"]["Severity"]:
                    raise ValueError("unrecognized severity")
            if table == "fact_maintenance_event":
                row["RootCause"] = row["RootCause"] or "Unknown"
            if table == "fact_customer_order":
                row["OrderStatus"] = "Shipped" if row["ActualShipDate"] else "Open"
            if table == "dim_product":
                row["Category"] = row["Category"].title()
                row["UnitMargin"] = row["UnitPrice"] - row["StandardCost"]
                row["MarginPct"] = round(row["UnitMargin"] / row["UnitPrice"], 4)
            if table == "dim_plant":
                row["PlantCode"] = row["PlantCode"].upper()
            if table == "dim_customer":
                country = row["Country"].upper()
                countries = {
                    "SG": "Singapore", "SINGAPORE": "Singapore",
                    "MY": "Malaysia", "MALAYSIA": "Malaysia",
                    "IN": "India", "INDIA": "India",
                    "AU": "Australia", "AUSTRALIA": "Australia",
                }
                if country not in countries:
                    raise ValueError("unrecognized country")
                row["Country"] = countries[country]
            if table == "dim_date":
                row["Year"] = row.pop("FiscalYear")
                row["YearMonth"] = row["Date"][:7]
                row["MonthStart"] = row["Date"][:7] + "-01"
            required = set(entity["columns"]) - set(entity["nullable_columns"]) - {"FiscalYear"}
            if any(row[column] is None for column in required):
                raise ValueError(f"{table}: unexpected null outside the declared quarantine/nullable rules")
            cleaned.append(row)
        keys = [row[entity["key"]] for row in cleaned]
        if None in keys or len(set(keys)) != len(keys):
            raise ValueError(f"{table}: null or conflicting duplicate primary key")
        tables[table] = cleaned
    for name in ("dim_customer", "dim_defect_type"):
        key = next(entity["key"] for entity in graph["entities"] if entity["gold"] == name)
        tables[name].append({column: -1 if column == key else "Unknown" for column in tables[name][0]})
    customers = {row["CustomerKey"] for row in tables["dim_customer"]}
    for row in tables["fact_customer_order"]:
        if row["CustomerKey"] not in customers:
            row["CustomerKey"] = -1
    dates = {row["DateKey"]: row["YearMonth"] for row in tables["dim_date"]}
    aggregate = defaultdict(lambda: {
        "PlannedUnits": 0, "ActualUnits": 0, "ScrapUnits": 0, "ProductionDowntimeMinutes": 0,
        "InspectedUnits": 0, "DefectCount": 0, "MaintenanceEvents": 0, "Orders": 0, "LateOrders": 0,
        "Revenue": Decimal(0), "MaintenanceCost": Decimal(0),
    })
    for row in tables["fact_production_run"]:
        month = aggregate[row["PlantKey"], dates[row["DateKey"]]]
        for column in ("PlannedUnits", "ActualUnits", "ScrapUnits"):
            month[column] += row[column]
        month["ProductionDowntimeMinutes"] += row["DowntimeMinutes"]
    for row in tables["fact_quality_inspection"]:
        month = aggregate[row["PlantKey"], dates[row["DateKey"]]]
        month["InspectedUnits"] += row["InspectedUnits"]
        month["DefectCount"] += row["DefectCount"]
    for row in tables["fact_maintenance_event"]:
        month = aggregate[row["PlantKey"], dates[row["DateKey"]]]
        month["MaintenanceEvents"] += 1
        month["MaintenanceCost"] += row["MaintenanceCost"]
    for row in tables["fact_customer_order"]:
        month = aggregate[row["PlantKey"], dates[row["DateKey"]]]
        month["Orders"] += 1
        month["LateOrders"] += row["LateShipmentFlag"]
        month["Revenue"] += row["Revenue"]
    tables["agg_plant_month"] = [
        {"PlantKey": plant, "YearMonth": month, **values}
        for (plant, month), values in sorted(aggregate.items())
    ]
    for rel in graph["relationships"]:
        parent_keys = [row[rel["to_column"]] for row in tables[rel["to_table"]]]
        if len(set(parent_keys)) != len(parent_keys):
            raise ValueError(f"relationship target is not unique: {rel}")
        if any(row[rel["from_column"]] not in set(parent_keys) for row in tables[rel["from_table"]]):
            raise ValueError(f"relationship has orphan keys: {rel}")
    runs, quality = tables["fact_production_run"], tables["fact_quality_inspection"]
    orders, maintenance = tables["fact_customer_order"], tables["fact_maintenance_event"]
    actual = sum(row["ActualUnits"] for row in runs)
    scrap = sum(row["ScrapUnits"] for row in runs)
    planned = sum(row["PlannedUnits"] for row in runs)
    inspected = sum(row["InspectedUnits"] for row in quality)
    defects = sum(row["DefectCount"] for row in quality)
    preventive = sum(row["PreventiveFlag"] for row in maintenance)
    kpis = {
        "planned_units": planned, "actual_units": actual, "scrap_units": scrap,
        "production_attainment_pct": round(actual / planned, 4), "scrap_rate_pct": round(scrap / (actual + scrap), 4),
        "inspected_units": inspected, "defect_count": defects, "defect_rate_pct": round(defects / inspected, 4),
        "orders": len(orders), "open_orders": sum(row["OrderStatus"] == "Open" for row in orders),
        "late_orders": sum(row["LateShipmentFlag"] for row in orders),
        "total_revenue": float(sum(row["Revenue"] for row in orders)),
        "maintenance_events": len(maintenance), "preventive_events": preventive,
        "preventive_maintenance_pct": round(preventive / len(maintenance), 4),
        "maintenance_downtime_minutes": sum(row["DowntimeMinutes"] for row in maintenance),
        "plant_months": len(aggregate),
    }
    counts = {table: len(rows) for table, rows in tables.items()}
    expected = read_json(ROOT / "tools/expected_counts.json")
    if counts != expected["gold"] or kpis != expected["kpis"]:
        raise ValueError("curation failed pinned count/KPI acceptance; inspect input and rules, do not relax gates")
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in tables.items():
        _write_csv(output / f"{name}.csv", rows)
    _write_csv(output.parent / "quarantine.csv", rejects)
    result = {
        "output": str(output), "dictionary_version": graph["version"],
        "dictionary_sha256": hashlib.sha256(dictionary.read_bytes()).hexdigest(),
        "counts": counts, "quarantine_counts": dict(Counter(row["DqReason"] for row in rejects)),
        "duplicates_removed": duplicate_count, "relationships_checked": len(graph["relationships"]), "kpis": kpis,
    }
    write_json(output.parent / "curation.json", result)
    return result
