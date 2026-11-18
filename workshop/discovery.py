"""Observe files independently, then compare claims against evidence."""

import re
from collections import Counter
from pathlib import Path

from workshop.io import ROOT, read_csv, read_json


def validate_dictionary(path: Path, data: Path) -> dict:
    graph = read_json(path)
    if graph.get("version") != 1 or graph.get("classification") != "synthetic-only":
        raise ValueError("unsupported dictionary or data classification")
    entities = graph["entities"]
    sources = {entity["source"] for entity in entities}
    if len(sources) != len(entities) or sources != {path.stem for path in data.glob("*.csv")}:
        raise ValueError("dictionary entity coverage differs from actual CSV files")
    gold = {entity["gold"]: entity for entity in entities if entity["gold"]}
    for entity in entities:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", entity["source"]):
            raise ValueError("invalid entity identifier")
        header, _ = read_csv(data / f"{entity['source']}.csv")
        columns = entity["columns"]
        if header != columns or not entity["grain"] or entity["key"] not in columns:
            raise ValueError(f"{entity['source']}: dictionary header, key or grain mismatch")
        if not set(entity["nullable_columns"]) <= set(columns):
            raise ValueError("unknown nullable column")
        for column in columns:
            definition = graph["attributes"].get(column)
            if not definition or definition[0] not in ("integer", "decimal", "date", "string") or not definition[1]:
                raise ValueError(f"missing typed attribute description: {column}")
    edges = []
    adjacency = {table: set() for table in gold}
    for rel in graph["relationships"]:
        if rel["from_table"] not in gold or rel["to_table"] not in gold:
            raise ValueError("relationship references missing table")
        origin, target = gold[rel["from_table"]], gold[rel["to_table"]]
        if rel["from_column"] not in origin["columns"] or rel["to_column"] != target["key"]:
            raise ValueError("relationship references missing column or non-primary target")
        edges.append(tuple(rel[key] for key in ("from_table", "from_column", "to_table", "to_column")))
        adjacency[rel["from_table"]].add(rel["to_table"])
    if len(set(edges)) != len(edges):
        raise ValueError("duplicate relationship")
    visiting, visited = set(), set()

    def visit(table):
        if table in visiting:
            raise ValueError("cyclic mandatory relationship graph")
        if table in visited:
            return
        visiting.add(table)
        for parent in adjacency[table]:
            visit(parent)
        visiting.remove(table)
        visited.add(table)

    for table in gold:
        visit(table)
    reachable = {next(iter(gold))}
    while True:
        before = len(reachable)
        for rel in graph["relationships"]:
            if rel["from_table"] in reachable or rel["to_table"] in reachable:
                reachable.update((rel["from_table"], rel["to_table"]))
        if len(reachable) == before:
            break
    if reachable != set(gold):
        raise ValueError("disconnected core model")
    return graph


def validate_model(graph: dict, model: dict) -> None:
    expected_tables = {entity["gold"] for entity in graph["entities"] if entity["gold"]}
    if model.get("version") != 1 or set(model["tables"]) != expected_tables or len(model["tables"]) != 12:
        raise ValueError("model tables differ from canonical core placement")
    edge_keys = ("from_table", "from_column", "to_table", "to_column")
    canonical = {tuple(rel[key] for key in edge_keys) for rel in graph["relationships"]}
    modeled = {tuple(rel[key] for key in edge_keys) for rel in model["relationships"]}
    if (canonical != modeled or len(model["relationships"]) != 18
            or any(rel.get("active") is not True for rel in model["relationships"])):
        raise ValueError("model relationships differ from the healthy core contract")
    measures = model["measures"]
    if len(measures) != 14 or len({measure["name"] for measure in measures}) != 14:
        raise ValueError("model measures must be unique and core-only")
    for measure in measures:
        if (measure["table"] not in expected_tables or not isinstance(measure["dax"], str)
                or not measure["dax"].strip() or not isinstance(measure["format"], str)):
            raise ValueError("invalid measure home, expression or format")


def discover(data: Path, vendor_path: Path) -> dict:
    graph = read_json(ROOT / "data-model/dictionary.json")
    vendor = read_json(vendor_path)
    observed = {}
    tables = {}
    for entity in graph["entities"]:
        name = entity["source"]
        header, rows = read_csv(data / f"{name}.csv")
        observed[name] = rows
        override = vendor["overrides"].get(name, {"omit": [], "add": []})
        claimed = (set(entity["columns"]) - set(override["omit"])) | set(override["add"])
        key_counts = Counter(row.get(entity["key"], "").strip() for row in rows)
        tables[name] = {
            "rows": len(rows),
            "columns": header,
            "nulls": {column: sum(not row[column].strip() for row in rows) for column in header},
            "exact_duplicates": len(rows) - len({tuple(row.values()) for row in rows}),
            "duplicate_keys": sum(count - 1 for key, count in key_counts.items() if key and count > 1),
            "unknown_columns": sorted(set(header) - claimed),
            "missing_columns": sorted(claimed - set(header)),
            "grain": entity["grain"],
        }
    relationships = []
    raw_names = {entity["gold"]: entity["source"] for entity in graph["entities"] if entity["gold"]}
    candidates = list(vendor["candidate_relationships"])
    declared = {tuple(rel.values()) for rel in candidates}
    for edge in graph["relationships"]:
        rel = {
            "from_table": raw_names[edge["from_table"]], "from_column": edge["from_column"],
            "to_table": raw_names[edge["to_table"]], "to_column": edge["to_column"],
        }
        if tuple(rel.values()) not in declared:
            candidates.append(rel)
    for rel in candidates:
        source, target = observed[rel["from_table"]], observed[rel["to_table"]]
        fk, pk = rel["from_column"], rel["to_column"]
        if fk not in tables[rel["from_table"]]["columns"] or pk not in tables[rel["to_table"]]["columns"]:
            raise ValueError("vendor relationship references unknown column")
        targets = Counter(row[pk].strip() for row in target)
        orphan_rows = sum(bool(row[fk].strip()) and row[fk].strip() not in targets for row in source)
        blanks = sum(not row[fk].strip() for row in source)
        duplicate_targets = sum(count - 1 for key, count in targets.items() if key and count > 1)
        relationships.append({
            "from": f"{rel['from_table']}.{fk}",
            "to": f"{rel['to_table']}.{pk}",
            "orphan_rows": orphan_rows,
            "null_fk_rows": blanks,
            "target_duplicate_keys": duplicate_targets,
            "verdict": "reject" if orphan_rows or duplicate_targets or blanks else "candidate-supported",
            "interpretation": "Key evidence only; SME confirmation still required.",
        })
    return {"tables": tables, "relationships": relationships, "sme_questions": graph["sme_questions"]}
