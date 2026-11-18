import csv
import json
import sqlite3
from pathlib import Path

import pytest

from workshop.curation import curate
from workshop.discovery import discover, validate_dictionary, validate_model
from workshop.reporting import (
    apply_repair,
    compare_months,
    inject_fault,
    model_months,
    plan_repair,
    source_months,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/landing/plant"


def test_discovery_uses_observations_not_vendor_claims():
    report = discover(DATA, ROOT / "fixtures/vendor-dictionary.json")
    assert len(report["tables"]) == 13
    assert sum(t["rows"] for t in report["tables"].values()) == 12279
    runs = report["tables"]["FactProductionRun"]
    assert runs["exact_duplicates"] == 25
    assert runs["nulls"]["ActualUnits"] == 6
    assert runs["unknown_columns"] == ["OperatorTeam"]
    assert runs["missing_columns"] == ["RunDurationMinutes"]
    customers = report["tables"]["DimCustomer"]
    assert customers["duplicate_keys"] == 1
    relation = next(r for r in report["relationships"] if r["from"] == "FactCustomerOrder.CustomerKey")
    assert relation["orphan_rows"] == 6
    assert relation["verdict"] == "reject"
    batch = next(r for r in report["relationships"] if r["from"] == "FactQualityInspection.BatchID")
    assert batch["verdict"] == "reject"
    assert batch["target_duplicate_keys"] > 0
    assert report["sme_questions"]


def test_dictionary_cohesion_rejects_bad_edges(tmp_path):
    source = ROOT / "data-model/dictionary.json"
    validate_dictionary(source, DATA)
    graph = json.loads(source.read_text())
    graph["relationships"][0]["to_table"] = "missing"
    path = tmp_path / "dictionary.json"
    path.write_text(json.dumps(graph))
    with pytest.raises(ValueError, match="relationship"):
        validate_dictionary(path, DATA)


@pytest.mark.parametrize("defect", ["table", "measure-home", "duplicate-measure", "inactive", "duplicate-edge"])
def test_model_cohesion_rejects_tampered_contract(defect):
    graph = json.loads((ROOT / "data-model/dictionary.json").read_text())
    model = json.loads((ROOT / "data-model/model.json").read_text())
    if defect == "table":
        model["tables"][0] = "unapproved_table"
    elif defect == "measure-home":
        model["measures"][0]["table"] = "missing_table"
    elif defect == "duplicate-measure":
        model["measures"][0]["name"] = model["measures"][1]["name"]
    elif defect == "inactive":
        model["relationships"][0]["active"] = False
    else:
        model["relationships"].append(model["relationships"][0])
    with pytest.raises(ValueError):
        validate_model(graph, model)


def test_discovery_checks_raw_date_relationships_too():
    report = discover(DATA, ROOT / "fixtures/vendor-dictionary.json")
    edge = next(r for r in report["relationships"] if r["from"] == "FactProductionRun.DateKey")
    assert edge["orphan_rows"] == 5
    assert edge["verdict"] == "reject"


def test_curation_fails_on_unplanned_null_instead_of_silent_default(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for path in DATA.glob("*.csv"):
        (source / path.name).write_bytes(path.read_bytes())
    path = source / "DimShift.csv"
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    rows[0]["ShiftName"] = ""
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="unexpected null"):
        curate(source, tmp_path / "gold", ROOT / "data-model/dictionary.json")


def test_discovery_rejects_unexpected_csv_shape(tmp_path):
    for path in DATA.glob("*.csv"):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    (tmp_path / "DimShift.csv").write_text("ShiftKey,ShiftKey\n1,2\n")
    with pytest.raises(ValueError, match="header"):
        discover(tmp_path, ROOT / "fixtures/vendor-dictionary.json")


@pytest.fixture
def gold(tmp_path):
    return curate(DATA, tmp_path / "curated", ROOT / "data-model/dictionary.json")


def test_curation_counts_quarantine_keys_and_metrics(gold):
    expected = json.loads((ROOT / "tools/expected_counts.json").read_text())
    assert gold["counts"] == expected["gold"]
    assert gold["quarantine_counts"] == {
        "invalid_date": 5,
        "missing_actual_units": 6,
        "negative_scrap": 8,
        "defects_exceed_inspected": 7,
    }
    assert gold["duplicates_removed"] == 27
    assert gold["relationships_checked"] == 18
    assert gold["kpis"]["actual_units"] == 1032704
    assert gold["kpis"]["scrap_rate_pct"] == 0.0313
    assert gold["kpis"]["production_attainment_pct"] == 0.9426
    with (Path(gold["output"]) / "fact_customer_order.csv").open() as stream:
        orders = list(csv.DictReader(stream))
    assert sum(r["CustomerKey"] == "-1" for r in orders) == 6


def test_relational_gold_month_query_matches_independent_raw_source(gold):
    with sqlite3.connect(":memory:") as connection:
        connection.execute("ATTACH DATABASE ':memory:' AS gold")
        for table in ("fact_production_run", "dim_date"):
            with (Path(gold["output"]) / f"{table}.csv").open() as stream:
                reader = csv.DictReader(stream)
                columns = list(reader.fieldnames)
                schema = ", ".join(f'"{column}" TEXT' for column in columns)
                connection.execute(f"CREATE TABLE gold.{table} ({schema})")
                parameters = ",".join("?" for _ in columns)
                connection.executemany(
                    f"INSERT INTO gold.{table} VALUES ({parameters})",
                    [tuple(row[column] for column in columns) for row in reader],
                )
        rows = connection.execute((ROOT / "queries/monthly-fabric.sql").read_text()).fetchall()
    actual = [{"YearMonth": month, "Actual Units": value} for month, value in rows]
    assert compare_months(source_months(DATA), actual) == []


def test_monthly_fault_fails_before_and_passes_after_reviewed_repair(gold, tmp_path):
    state = tmp_path / "model.json"
    inject_fault(ROOT / "data-model/model.json", state)
    expected = source_months(DATA)
    assert len(expected) == 30
    assert sum(row["Actual Units"] for row in expected) == 1032704
    broken = model_months(Path(gold["output"]), state)
    assert len({row["Actual Units"] for row in broken}) == 1
    assert compare_months(expected, broken)
    plan = plan_repair(state)
    assert len(plan["changes"]) == 1
    with pytest.raises(ValueError, match="approval"):
        apply_repair(state, plan, "not-reviewed")
    apply_repair(state, plan, plan["sha256"])
    assert compare_months(expected, model_months(Path(gold["output"]), state)) == []


def test_repair_rejects_drift(gold, tmp_path):
    state = tmp_path / "model.json"
    inject_fault(ROOT / "data-model/model.json", state)
    plan = plan_repair(state)
    original = state.read_text()
    state.write_text(original + "\n")
    with pytest.raises(ValueError, match="changed"):
        apply_repair(state, plan, plan["sha256"])
    assert state.read_text() == original + "\n"


@pytest.mark.parametrize(
    "actual",
    [
        [],
        [{"YearMonth": "2024-01", "Actual Units": None}],
        [{"YearMonth": "2024-01", "Actual Units": 1}] * 2,
        [{"YearMonth": "2024-01", "Actual Units": float("nan")}],
        [{"YearMonth": "2024-01", "Actual Units": 10.1}],
    ],
)
def test_monthly_reconciliation_rejects_bad_or_incomplete_shape(actual):
    assert compare_months([{"YearMonth": "2024-01", "Actual Units": 10}], actual)


def test_monthly_reconciliation_detects_redistribution_even_when_total_matches():
    expected = [
        {"YearMonth": "2024-01", "Actual Units": 10},
        {"YearMonth": "2024-02", "Actual Units": 20},
    ]
    assert compare_months(expected, list(reversed([
        {"YearMonth": "2024-01", "Actual Units": 20},
        {"YearMonth": "2024-02", "Actual Units": 10},
    ])))


def test_fault_injection_refuses_unrelated_or_existing_model(tmp_path):
    path = tmp_path / "model.json"
    path.write_text('{"scope":"production"}')
    with pytest.raises(ValueError, match="exists"):
        inject_fault(ROOT / "data-model/model.json", path)
    assert json.loads(path.read_text()) == {"scope": "production"}
