# %% [markdown]
# # 07 · Review, then recover named semantic model objects
#
# First obtain an owner-prestaged Direct Lake semantic model with the **12 core Gold tables** below, excluding
# `agg_plant_month`. Use the explicit workspace and model UUIDs, never discovery by display name.
# This notebook defaults to **read-only model access**: it saves the original definition and proposed diff
# in the approved Lakehouse. A later run may apply only independently reviewed, individually named edits.
# No tables, partitions, sources, roles or unrelated DAX are rebuilt.

# %%
TABLES = ["dim_date", "dim_plant", "dim_line", "dim_product", "dim_shift", "dim_customer", "dim_defect_type",
          "dim_asset", "fact_production_run", "fact_quality_inspection", "fact_maintenance_event",
          "fact_customer_order"]

RELATIONSHIPS = [
    ("fact_production_run", "DateKey", "dim_date", "DateKey"),
    ("fact_production_run", "PlantKey", "dim_plant", "PlantKey"),
    ("fact_production_run", "LineKey", "dim_line", "LineKey"),
    ("fact_production_run", "ProductKey", "dim_product", "ProductKey"),
    ("fact_production_run", "ShiftKey", "dim_shift", "ShiftKey"),
    ("fact_quality_inspection", "DateKey", "dim_date", "DateKey"),
    ("fact_quality_inspection", "PlantKey", "dim_plant", "PlantKey"),
    ("fact_quality_inspection", "LineKey", "dim_line", "LineKey"),
    ("fact_quality_inspection", "ProductKey", "dim_product", "ProductKey"),
    ("fact_quality_inspection", "DefectTypeKey", "dim_defect_type", "DefectTypeKey"),
    ("fact_maintenance_event", "DateKey", "dim_date", "DateKey"),
    ("fact_maintenance_event", "PlantKey", "dim_plant", "PlantKey"),
    ("fact_maintenance_event", "LineKey", "dim_line", "LineKey"),
    ("fact_maintenance_event", "AssetKey", "dim_asset", "AssetKey"),
    ("fact_customer_order", "DateKey", "dim_date", "DateKey"),
    ("fact_customer_order", "PlantKey", "dim_plant", "PlantKey"),
    ("fact_customer_order", "ProductKey", "dim_product", "ProductKey"),
    ("fact_customer_order", "CustomerKey", "dim_customer", "CustomerKey"),
]

MEASURES = [
    ("fact_production_run", "Planned Units", "SUM ( 'fact_production_run'[PlannedUnits] )", "#,0"),
    ("fact_production_run", "Actual Units", "SUM ( 'fact_production_run'[ActualUnits] )", "#,0"),
    ("fact_production_run", "Scrap Units", "SUM ( 'fact_production_run'[ScrapUnits] )", "#,0"),
    ("fact_production_run", "Scrap Rate %", "DIVIDE ( [Scrap Units], [Actual Units] + [Scrap Units] )", "0.00%"),
    ("fact_production_run", "Production Attainment %", "DIVIDE ( [Actual Units], [Planned Units] )", "0.0%"),
    ("fact_production_run", "Downtime Minutes", "SUM ( 'fact_production_run'[DowntimeMinutes] )", "#,0"),
    ("fact_quality_inspection", "Inspected Units", "SUM ( 'fact_quality_inspection'[InspectedUnits] )", "#,0"),
    ("fact_quality_inspection", "Defect Count", "SUM ( 'fact_quality_inspection'[DefectCount] )", "#,0"),
    ("fact_quality_inspection", "Defect Rate %", "DIVIDE ( [Defect Count], [Inspected Units] )", "0.00%"),
    ("fact_maintenance_event", "Maintenance Events", "COUNTROWS ( 'fact_maintenance_event' )", "#,0"),
    ("fact_maintenance_event", "Preventive Maintenance %",
     "DIVIDE ( CALCULATE ( [Maintenance Events], 'fact_maintenance_event'[PreventiveFlag] = 1 ), [Maintenance Events] )",
     "0.0%"),
    ("fact_customer_order", "Orders", "COUNTROWS ( 'fact_customer_order' )", "#,0"),
    ("fact_customer_order", "Total Revenue", "SUM ( 'fact_customer_order'[Revenue] )", "#,0"),
    ("fact_customer_order", "Late Order %", "DIVIDE ( SUM ( 'fact_customer_order'[LateShipmentFlag] ), [Orders] )", "0.0%"),
]

CONTRACT = {
    "version": 1, "tables": TABLES,
    "relationships": [dict(zip(("from_table", "from_column", "to_table", "to_column"), value, strict=True), active=True)
                      for value in RELATIONSHIPS],
    "measures": [dict(zip(("table", "name", "dax", "format"), value, strict=True)) for value in MEASURES],
}

# %% [markdown]
# ## 1 · Snapshot and proposed diff (no model edits)
#
# The shared guard executes before this cell. Workspace, Lakehouse and model IDs must all be explicit UUIDs.
# Semantic Link is provided by supported Fabric runtimes; use a reviewed Fabric Environment if it is missing.
# There is no automatic install, provisioning, refresh, model selection or authentication setup here.
# Planning is model-read-only, not storage-read-only: the explicitly approved sandbox receives the snapshot.
# Each Lakehouse directory/file write rechecks runtime UUIDs and the exact workspace approval.

# %%
def require_model_context():
    require_sandbox()
    assert_model_target(workspace_id=workspace_id, model_workspace_id=model_workspace_id,
                        expected_model_id=expected_model_id)
    if type(apply_changes) is not bool or type(verify_model) is not bool:
        raise ValueError("apply_changes and verify_model must be Boolean values, not strings")


require_model_context()
from math import isfinite

import sempy.fabric as fabric

# Cache invalidation has only a workspace argument in the documented SemPy API.
fabric.refresh_tom_cache(workspace=model_workspace_id)
server = fabric.create_tom_server(dataset=expected_model_id, workspace=model_workspace_id, readonly=True)
try:
    import Microsoft.AnalysisServices.Tabular as TOM

    model = server.Databases[expected_model_id].Model
    if str(model.Database.ID) != expected_model_id:
        raise ValueError("Resolved model UUID differs from expected_model_id")
    editor = NativeModelEditor(model, TOM)
    plan = make_plan(editor, CONTRACT, model_workspace_id, expected_model_id)
finally:
    server.Disconnect()

require_model_context()
snapshot_folder = f"Files/workshop/recovery/{batch_id}/{plan['digest']}"
snapshot_path = f"{snapshot_folder}/plan.json"
snapshot_text = canonical_json(plan)
require_model_context()
notebookutils.fs.mkdirs(snapshot_folder)
if notebookutils.fs.exists(snapshot_path):
    existing_text = notebookutils.fs.head(snapshot_path, len(snapshot_text.encode("utf-8")) + 1)
    if existing_text != snapshot_text:
        raise ValueError("Existing rollback snapshot differs; use a new batch_id and investigate")
else:
    require_model_context()
    if not notebookutils.fs.put(snapshot_path, snapshot_text, False):
        raise ValueError("Could not preserve the original definition; no edits are permitted")
print("Snapshot and rollback definitions:", snapshot_path)
print("REVIEWED DIFF HASH (independent review required):", plan["digest"])
print(json.dumps(plan["changes"], indent=2))

# %% [markdown]
# ## 2 · Separately approved, explicitly scoped apply
#
# Default `apply_changes=False`. After downloading/reviewing the original definition and diff, supply the
# displayed SHA-256 as `reviewed_diff_hash`, set `apply_approval` to the exact model UUID, list only the approved
# `selected_changes` keys, and set `apply_changes=True`. A changed model or changed contract invalidates review.
# Existing reversed relationships, wrong home tables and missing columns require manual remediation.
# The client never saves in a `finally` block. On failure it disconnects without saving in-memory changes.

# %%
require_model_context()
if apply_changes:
    if apply_approval != expected_model_id:
        raise ValueError("Separate apply_approval must equal the exact expected model UUID")
    if (plan["snapshot"]["workspace_id"], plan["snapshot"]["model_id"]) != (
            model_workspace_id, expected_model_id):
        raise ValueError("The reviewed plan targets a different model")
    validate_review(plan, reviewed_diff_hash, selected_changes)
    # Re-read server state instead of applying against a cached or stale client model.
    fabric.refresh_tom_cache(workspace=model_workspace_id)
    server = fabric.create_tom_server(dataset=expected_model_id, workspace=model_workspace_id, readonly=False)
    try:
        live_model = server.Databases[expected_model_id].Model
        if str(live_model.Database.ID) != expected_model_id:
            raise ValueError("Writable model UUID differs from expected_model_id")
        live_editor = NativeModelEditor(live_model, TOM)
        applied = apply_plan(live_editor, CONTRACT, plan, reviewed_diff_hash=reviewed_diff_hash,
                             selected_changes=selected_changes, tom_types=TOM)
        require_model_context()
        live_model.SaveChanges()
        print("Saved only these approved changes:", applied)
    finally:
        server.Disconnect()
    fabric.refresh_tom_cache(workspace=model_workspace_id)
else:
    print("Read-only model plan complete. No semantic model changes were saved.")

# %% [markdown]
# ## 3 · Optional read-only verification after model completion
#
# Set `verify_model=True` only when all required measures/relationships exist. Querying does not refresh data.
# If Direct Lake metadata needs refresh, perform that manually in the Fabric UI with appropriate permission.
# Keep the saved snapshot for manual scoped restoration; never deploy the entire old database over new work.

# %%
require_model_context()
if verify_model:
    result = fabric.evaluate_dax(dataset=expected_model_id, dax_string=CHECK_MEASURES_DAX,
                                 workspace=model_workspace_id)
    display(result)
    row = result.iloc[0].tolist()
    expected = [
        ("Planned Units", 1095550, 0), ("Actual Units", 1032704, 0), ("Scrap Units", 33404, 0),
        ("Scrap Rate %", 0.0313, 0.00005), ("Production Attainment %", 0.9426, 0.00005),
    ]
    for (name, value, tolerance), actual in zip(expected, row[:5], strict=True):
        if actual is None or not isfinite(float(actual)) or abs(float(actual) - value) > tolerance:
            raise ValueError(f"{name}: expected {value}, got {actual}")
    monthly = fabric.evaluate_dax(dataset=expected_model_id, dax_string=MONTHLY_DAX,
                                  workspace=model_workspace_id)
    display(monthly)
    by_plant = fabric.evaluate_dax(
        dataset=expected_model_id, workspace=model_workspace_id,
        dax_string="""EVALUATE SUMMARIZECOLUMNS (
            'dim_plant'[PlantCode], "Scrap", ROUND ( [Scrap Rate %], 4 )
        ) ORDER BY 'dim_plant'[PlantCode]""",
    )
    scrap = {key: round(float(value), 4)
             for key, value in zip(by_plant.iloc[:, 0], by_plant.iloc[:, 1], strict=True)}
    if scrap != {"AU-01": 0.0294, "IN-01": 0.0292, "MY-01": 0.0379, "SG-01": 0.0291}:
        raise ValueError("Plant-filtered scrap rates differ; inspect the reviewed relationships")
    print("Headline values and plant relationships verified. Stop the Spark session.")
