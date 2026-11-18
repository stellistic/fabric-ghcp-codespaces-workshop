"""Pure scoped model planning plus a small native TOM adapter; no network on import."""

import hashlib
import hmac
import json


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def relationship_key(value) -> str:
    return ("relationship:" + value["from_table"] + "." + value["from_column"]
            + "->" + value["to_table"] + "." + value["to_column"])


def measure_key(value) -> str:
    return "measure:" + value["table"] + ":" + value["name"]


def snapshot_model(tom, workspace_id: str, model_id: str) -> dict:
    tables = []
    measures = []
    for table in tom.model.Tables:
        tables.append({"name": table.Name, "columns": sorted(column.Name for column in table.Columns)})
        for measure in table.Measures:
            measures.append({
                "table": table.Name, "name": measure.Name,
                "dax": measure.Expression or "", "format": measure.FormatString or "",
            })
    relationships = []
    for relation in tom.model.Relationships:
        if not hasattr(relation, "FromColumn"):
            raise ValueError("Unsupported relationship type; inspect and recover manually")
        relationships.append({
            "name": relation.Name,
            "from_table": relation.FromTable.Name, "from_column": relation.FromColumn.Name,
            "to_table": relation.ToTable.Name, "to_column": relation.ToColumn.Name,
            "active": bool(relation.IsActive),
            "from_cardinality": str(relation.FromCardinality),
            "to_cardinality": str(relation.ToCardinality),
            "cross_filtering_behavior": str(relation.CrossFilteringBehavior),
            "security_filtering_behavior": str(getattr(relation, "SecurityFilteringBehavior", "")),
            "rely_on_referential_integrity": bool(getattr(relation, "RelyOnReferentialIntegrity", False)),
        })
    snapshot = {
        "workspace_id": workspace_id, "model_id": model_id,
        "tables": sorted(tables, key=lambda value: value["name"]),
        "relationships": sorted(relationships, key=lambda value: value["name"]),
        "measures": sorted(measures, key=measure_key),
    }
    if hasattr(tom, "snapshot_definition"):
        # Native TOM serialization preserves annotations, partitions and other rollback context.
        snapshot["original_database_definition"] = tom.snapshot_definition()
    return snapshot


def make_plan(tom, contract: dict, workspace_id: str, model_id: str) -> dict:
    snapshot = snapshot_model(tom, workspace_id, model_id)
    tables = {table["name"]: set(table["columns"]) for table in snapshot["tables"]}
    missing = set(contract["tables"]) - set(tables)
    if missing:
        raise ValueError(f"Manually attach the missing core tables before planning: {sorted(missing)}")
    relationships = {}
    for relation in snapshot["relationships"]:
        key = relationship_key(relation)
        if key in relationships:
            raise ValueError("Duplicate relationship endpoints require manual review")
        relationships[key] = relation
    measures = {measure_key(measure): measure for measure in snapshot["measures"]}
    changes = []
    for desired in contract["relationships"]:
        for table, column in (("from_table", "from_column"), ("to_table", "to_column")):
            if desired[column] not in tables[desired[table]]:
                raise ValueError(f"Missing column {desired[table]}[{desired[column]}]; repair tables manually")
        key = relationship_key(desired)
        reverse = {
            "from_table": desired["to_table"], "from_column": desired["to_column"],
            "to_table": desired["from_table"], "to_column": desired["from_column"],
        }
        if relationship_key(reverse) in relationships:
            raise ValueError(f"A reversed relationship requires manual review: {key}")
        before = relationships.get(key)
        after = dict(desired, from_cardinality="Many", to_cardinality="One",
                     cross_filtering_behavior="OneDirection")
        if before is None or any(before[field] != after[field] for field in after):
            changes.append({"key": key, "kind": "relationship", "before": before, "after": after})
    for desired in contract["measures"]:
        key = measure_key(desired)
        before = measures.get(key)
        other_home = [measure for measure in snapshot["measures"]
                      if measure["name"] == desired["name"] and measure["table"] != desired["table"]]
        if other_home:
            raise ValueError(f"Measure [{desired['name']}] exists in a different home table; review manually")
        # Exact DAX comparison deliberately preserves string literal whitespace semantics.
        if before != desired:
            changes.append({"key": key, "kind": "measure", "before": before, "after": dict(desired)})
    payload = {"snapshot": snapshot, "desired_contract": contract, "changes": changes}
    return dict(payload, digest=hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest())


def validate_review(plan: dict, reviewed_diff_hash: str, selected_changes: list[str]) -> None:
    if (not isinstance(reviewed_diff_hash, str) or len(reviewed_diff_hash) != 64
            or not hmac.compare_digest(reviewed_diff_hash, plan["digest"])):
        raise ValueError("Provide the exact SHA-256 digest of the independently reviewed snapshot/diff")
    payload = {key: plan[key] for key in ("snapshot", "desired_contract", "changes")}
    if hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest() != plan["digest"]:
        raise ValueError("Snapshot/diff drift: the reviewed plan was modified")
    if (not isinstance(selected_changes, list) or not selected_changes
            or any(not isinstance(key, str) for key in selected_changes)
            or len(set(selected_changes)) != len(selected_changes)):
        raise ValueError("Explicitly select a nonempty list of unique change keys")
    known = {change["key"] for change in plan["changes"]}
    if set(selected_changes) - known:
        raise ValueError("Selected edits must be a subset of the reviewed named changes")


def apply_plan(tom, contract: dict, plan: dict, *, reviewed_diff_hash: str,
               selected_changes: list[str], tom_types) -> list[str]:
    """Mutate only approved objects in memory. The caller alone may explicitly SaveChanges."""
    validate_review(plan, reviewed_diff_hash, selected_changes)
    current = make_plan(tom, contract, plan["snapshot"]["workspace_id"], plan["snapshot"]["model_id"])
    if current["digest"] != plan["digest"]:
        raise ValueError("Model drift since review; obtain a new snapshot/diff and approval")
    chosen = [change for change in plan["changes"] if change["key"] in selected_changes]
    if tom_types is None and any(change["kind"] == "relationship" and change["before"] is not None
                                 for change in chosen):
        raise ValueError("TOM enum types must be supplied before editing existing relationships")
    tables = {table.Name: table for table in tom.model.Tables}
    relations = {relation.Name: relation for relation in tom.model.Relationships}
    for change in chosen:
        desired = change["after"]
        if change["kind"] == "measure":
            if change["before"] is None:
                tom.add_measure(table_name=desired["table"], measure_name=desired["name"],
                                expression=desired["dax"], format_string=desired["format"])
            else:
                measure = next(value for value in tables[desired["table"]].Measures
                               if value.Name == desired["name"])
                measure.Expression = desired["dax"]
                measure.FormatString = desired["format"]
        elif change["before"] is None:
            tom.add_relationship(
                from_table=desired["from_table"], from_column=desired["from_column"],
                to_table=desired["to_table"], to_column=desired["to_column"],
                from_cardinality="Many", to_cardinality="One",
                cross_filtering_behavior="OneDirection", is_active=True,
            )
        else:
            relation = relations[change["before"]["name"]]
            relation.IsActive = True
            relation.FromCardinality = tom_types.RelationshipEndCardinality.Many
            relation.ToCardinality = tom_types.RelationshipEndCardinality.One
            relation.CrossFilteringBehavior = tom_types.CrossFilteringBehavior.OneDirection
    return [change["key"] for change in chosen]


class NativeModelEditor:
    """No save-on-close wrapper or automatic model-wide lineage/DAX normalization."""

    def __init__(self, model, tom_types):
        self.model = model
        self.types = tom_types

    def snapshot_definition(self):
        return json.loads(str(self.types.JsonSerializer.SerializeDatabase(self.model.Database)))

    def add_measure(self, *, table_name, measure_name, expression, format_string):
        measure = self.types.Measure()
        measure.Name = measure_name
        measure.Expression = expression
        measure.FormatString = format_string
        self.model.Tables[table_name].Measures.Add(measure)

    def add_relationship(self, *, from_table, from_column, to_table, to_column,
                         from_cardinality, to_cardinality, cross_filtering_behavior, is_active):
        relation = self.types.SingleColumnRelationship()
        relation.Name = f"{from_table}_{from_column}__{to_table}_{to_column}"
        if any(value.Name == relation.Name for value in self.model.Relationships):
            raise ValueError("Proposed relationship name conflicts with another object; review manually")
        relation.FromColumn = self.model.Tables[from_table].Columns[from_column]
        relation.ToColumn = self.model.Tables[to_table].Columns[to_column]
        relation.FromCardinality = getattr(self.types.RelationshipEndCardinality, from_cardinality)
        relation.ToCardinality = getattr(self.types.RelationshipEndCardinality, to_cardinality)
        relation.CrossFilteringBehavior = getattr(self.types.CrossFilteringBehavior, cross_filtering_behavior)
        relation.IsActive = is_active
        self.model.Relationships.Add(relation)
