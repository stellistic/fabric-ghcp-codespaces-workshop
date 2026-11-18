# Guarded Fabric notebooks

These are **GitHub Copilot Workshop** assets. GitHub Copilot assists with writing,
reviewing and testing code; **Microsoft Fabric is the execution target**. All rows
describe fictional, synthetic manufacturing operations, not clinical or patient
data. Fabric-native AI features are separate, optional services; the core path
does not call them, extract documents, or require utility-bill tables.

## What is reused

The percent-format Python pipeline and five core sources were adapted from the
owner-supplied snapshot at commit
`d0d8c57a5dfc3d9eff8a2339c0266395367733df`. The source repository is read-only.
No media or optional 06 notebook is copied. The canonical business columns and
rules are described by `data-model/dictionary.json`; lineage columns below are
additional technical metadata.

Author in `tools/notebooks/src/`, not the generated `.ipynb` files:

```bash
python -m tools.notebooks.build
python -m tools.notebooks.build --check
python -m pytest -q tests/test_notebooks.py
```

The build injects the shared guard and helpers into **standalone** notebooks:
no local `tools` package is needed inside Fabric. Every original Python code cell
starts by rechecking authorization. All generated code cells are ordinary Python
(including SQL via `spark.sql`), have deterministic nbformat cell IDs, and contain
no execution output. Missing sources fail the build rather than being skipped.
`--check` covers shared helpers, queries, every notebook, and `model.json`.

The authoritative core lists in 07 export `data-model/model.json`, whose schema
is exactly:

```text
{version: 1, tables: [names],
 relationships: [{from_table, from_column, to_table, to_column, active: true}],
 measures: [{table, name, dax, format}]}
```

There are **12 model tables, 18 relationships, and 14 measures**. Gold has
**13 outputs**: the model's twelve tables plus `agg_plant_month` (120 rows),
which is a SQL exploration aggregate, not a model table. Neither the core contract
nor the two DAX queries depends on an optional appendix.

## Fabric-only preparation and execution

Local tests/builds are offline and do not authenticate, provision, or run Spark.
The notebooks themselves require a compatible **Fabric PySpark notebook runtime**
with `notebookutils`, Spark `try_*` functions, and a schema-enabled Lakehouse.
Runtime 1.3 or a newer tenant-approved equivalent is the intended baseline.
Use a reviewed Fabric Environment if Semantic Link is not already available.
There is deliberately no `%pip install`, token setup, or automatic provisioning.
The authorized execution-host rehearsal actually passed data notebooks 02–05
on Runtime **2.0**. Its semantic model/DAX checks used separately scoped REST
operations; that does not verify 07's native TOM runtime or XMLA prerequisites.

1. The **platform owner pre-stages/selects an approved existing disposable
   sandbox workspace and schema-enabled Lakehouse on existing capacity**.
   Do not select a production resource. This materials implementation does not
   authorize resource creation, capacity/RBAC changes, or tenant-setting changes;
   any provisioning is a separate platform-owner process.
2. Import all five `notebooks/*.ipynb` files into that workspace. In each
   notebook's **Data items**, attach that Lakehouse and mark it as default.
   The build does not embed resource IDs or attach a Lakehouse automatically.
3. Manually upload the thirteen generated plant CSVs (listed in 02's
   `EXPECTED_BRONZE`) into `Files/landing/plant/` in the attached Lakehouse. Keep only the thirteen
   expected CSV filenames in that folder; missing/unexpected CSVs are rejected.
   Do not stage private files or optional appendix data there.
4. Obtain the actual workspace and Lakehouse item UUIDs from the Fabric UI.
   Fill the **tagged parameters cell** in each imported notebook as below, or
   supply typed parameters through Fabric pipeline notebook activities.
5. **Run all**, in order: **02 → 03 → 04 → 05 → 07**. Wait for each notebook's
   checks to pass before proceeding. 04 is the code catch-up route for the
   three dimensions; do not run a Dataflow writer against those tables
   concurrently. 05 requires all twelve Silver business tables.
6. Before 07, the platform owner provides the approved, existing Direct Lake
   semantic model with the twelve core Gold tables listed in `model.json`,
   **not** `agg_plant_month`. Initial model provisioning/table binding is an
   owner prerequisite, not performed or authorized by this implementation.
   Wait for SQL endpoint/table discovery; verify schemas and source Lakehouse in
   the UI. Copy the model's UUID rather than relying on its display name.

Do not treat a Lakehouse display name, its pin, a notebook's current workspace,
or a model name as authorization.

### Required parameters and fail-closed checks

Every notebook starts with these defaults:

```python
workspace_id = ""
lakehouse_id = ""
sandbox = False
approval = ""
batch_id = ""
```

For an intentional run, supply nonzero lowercase canonical UUID strings,
`sandbox=True` as a **Boolean**, and `approval` equal to the **exact workspace
UUID**. Supply a nonempty `batch_id` containing only letters, digits, `_` and `-`,
starting with a letter/digit, at most 80 characters. Do not paste credentials.

Before any code-created schema, DataFrame, table write or snapshot write,
`assert_sandbox_context` reads **`notebookutils.runtime.context`** and requires:

- `currentWorkspaceId == workspace_id`;
- `defaultLakehouseId == lakehouse_id`;
- if supplied by runtime, `defaultLakehouseWorkspaceId == workspace_id`;
- the explicit sandbox approval above.

Missing context, mismatched UUIDs, names instead of UUIDs, or string `"true"`
fail closed. Cross-workspace Lakehouse/model targets are not supported here.
The write helper also permits only this notebook's fixed table allowlist.
These checks do **not** establish that a resource is disposable or replace Fabric
permissions: the operator must confirm that before approving its UUID.
Fabric may initialize a session before Python runs; the guard governs notebook
operations, not platform session startup.

## Profiles, permissions and costs

- **Offline contributor:** only run pytest, syntax/nbformat checks and the build.
  No Fabric account, CLI login, capacity or network call is needed for those.
- **Workshop executor:** use a dedicated sandbox identity/workspace, with the
  minimum tenant-approved ability to import/run notebooks and read/write this
  Lakehouse. Workspace Contributor is a common workshop setup, but remains
  broader than read-only access. Do not grant workspace Admin solely for a lab.
- **Model reviewer/applicator:** 07 uses TOM/XMLA. SemPy's `create_tom_server`
  documentation requires model **ReadWrite permission even for TOM inspection**;
  `readonly=True` limits what this notebook does, not what the identity could do.
  Apply additionally requires capacity XMLA read/write enabled and appropriate
  model write access. DAX verification requires model query/Build permissions
  under the tenant's configuration. Check actual tenant/capacity/license rules.

Use your organization's authorized Fabric sign-in and environment configuration
manually; these assets neither provision permissions nor acquire credentials
offline. Do not use blanket tenant administrator grants, embed tokens, or upload
real client data. Spark sessions and optional platform services can incur cost.
**Stop the Spark session** in Fabric after each working session (and after failed
runs); do not leave it idle while reviewing model diffs.

## Full-refresh exception, lineage and expected results

**This is a deliberate teaching exception to production medallion ingestion.**
The authorized 02–05 path overwrites only the fixed synthetic `bronze.*`,
`silver.*` and `gold.*` outputs, including `overwriteSchema=True`. Re-running
replaces those tables' current contents; it is **not** append-only Bronze,
incremental ingestion, MERGE, SCD2, or a production recovery strategy. A partial
failure can leave a partly refreshed layer: stop, inspect checks, then rerun the
whole affected notebook only after confirming the sandbox UUID again.

Production designs should preserve immutable Bronze, use typed schemas,
watermarks and business-key MERGE, retain quarantines, and implement suitable
history and transactional orchestration. Do not repoint these full-refresh
notebooks at production. Delta history is instructional and is not a substitute
for backup, retention policy or the semantic-model rollback snapshots.

- Bronze preserves all raw business values/duplicates, adding
  `_ingest_timestamp`, `_source_file`, `_source_system`, `_batch_id`.
- Silver removes ingestion metadata **before exact-row deduplication**, then
  adds `_processed_timestamp`, `_record_hash` (SHA-256 of ordered business
  columns, retaining null fields) and `_batch_id`. Bad rows go to
  `silver.dq_rejects`, not an unreported drop.
- Gold retains the source's stable dimension keys and fixed snapshot semantics;
  it does not claim historical SCD2. Unknown customer/defect members remain `-1`.
  `_built_timestamp` and `_batch_id` are added without changing business counts.
  Additional metadata columns are excluded from the core model table list.
- Successful data notebooks append operational metadata to
  **`workshop._pipeline_runs`**, separately from the thirteen Gold outputs:
  batch, notebook, layer/domain, timestamps, input/output/quarantine counts, status,
  dictionary version, pinned source SHA. This audit table is intentionally
  append-only. Failed notebooks are diagnosed through Fabric run logs and their
  failed checks; they do not emit a misleading success row.
- 07 preserves its original definition, diff and target IDs as JSON under
  `Files/workshop/recovery/`, not a Gold business table.

The notebook gates preserve the pinned source's `tools/expected_counts.json`
business counts. In particular:

| Check | Expected |
|---|---:|
| Bronze production runs | 3,673 |
| Silver/Gold production runs | 3,629 |
| Silver/Gold quality inspections | 2,729 |
| Silver/Gold maintenance events | 270 |
| Silver/Gold customer orders | 4,560 |
| Quarantined rows | 26 |
| Gold customers / defect types (including unknown) | 36 / 13 |
| Plant-month aggregate | 120 |
| Planned units | 1,095,550 |
| Actual units | 1,032,704 |
| Scrap units | 33,404 |
| Scrap rate, rounded to four decimals | 0.0313 |
| Production attainment, rounded to four decimals | 0.9426 |

Scrap rate is **scrap / (actual + scrap)**, not scrap / actual. Rates are
fractions before Power BI percentage formatting. `queries/check-measures.dax`
returns all fourteen core measures. `queries/monthly.dax` returns only
`YearMonth` and `Actual Units` at **month grain** (30 rows for this snapshot),
matching the participant offline comparator. It does not group by plant or
read the aggregate table. Plant-filtered relationship verification is a separate
query in 07; `gold.agg_plant_month` remains at plant-month grain (120 rows).

## 07: snapshot → review → scoped apply → verify

07 additionally defaults to:

```python
expected_model_id = ""
model_workspace_id = ""
apply_changes = False
apply_approval = ""
reviewed_diff_hash = ""
selected_changes = []
verify_model = False
```

`model_workspace_id` must equal the explicitly approved `workspace_id`.
`expected_model_id` must be a nonzero canonical UUID. Every SemPy model/query
call explicitly supplies that model UUID and workspace UUID. The documented
cache-invalidation call accepts a workspace only, which is also always explicit.
No code chooses a model by its name or by current-workspace defaults.

1. **Plan only.** Keep `apply_changes=False`. The notebook opens TOM with
   `readonly=True`, checks required tables/columns, captures the **entire original
   database definition**, and computes a proposed diff for only the eighteen
   named core relationships and fourteen core measures. It also captures all
   table/column names and current relationships/measures. Unrelated objects are
   preserved. An extra model table is not implicitly deleted.
2. **Preserve and review.** It writes an immutable-by-convention, non-overwriting
   snapshot/diff to
   `Files/workshop/recovery/<batch_id>/<sha256>/plan.json`, and displays its hash
   and named change keys. **Model-read-only does not mean storage-read-only:**
   creating this directory/file is a Lakehouse write authorized by the explicit
   `sandbox=True`, exact workspace `approval`, and matching runtime UUIDs.
   Both `fs.mkdirs` and `fs.put` immediately recheck that authorization; defaults
   authorize neither. No plan/snapshot writes a Lakehouse table.
   Existing different content is rejected. Download it
   and independently review target IDs, original definitions, intended DAX,
   cardinality, active state and filter direction. These files are not WORM
   storage; protect their Lakehouse permissions and keep a separate reviewed
   copy. Definitions may reveal internal connection/schema metadata: do not
   commit or share snapshots publicly.
3. **Approve a subset.** On a separate run, set `reviewed_diff_hash` to the exact
   reviewed digest, copy only individually approved change keys into the Python
   list `selected_changes`, set `apply_approval` to the exact model UUID, and set
   `apply_changes=True`. Leave unrelated/custom DAX alone. Empty scope,
   unknown/duplicate keys, wrong approval, tampered plans or model/contract
   drift are rejected. The hash binds the target, full original definition,
   desired contract and proposed changes.
4. **Apply.** The notebook invalidates the workspace's local TOM cache, reopens
   the explicit model, recomputes the plan, and requires the digest to match
   before editing. Only selected missing/changed relationships/measures are
   added/updated. It uses native TOM objects with **one explicit `SaveChanges`**;
   it does not use a save-on-close wrapper, reset every measure, remove every
   relationship, normalize all lineage tags, deploy a database, or refresh data.
   Failure before `SaveChanges` disconnects without persisting client edits.
   No model edit is saved in `finally`. Reviewers should pause concurrent model
   editing: the hash check is not a distributed lock, and tenant-side concurrency
   behavior must still be verified.
5. **Verify explicitly.** Reset `apply_changes=False`. When all required
   relationships/measures exist, set `verify_model=True` and run again. The
   notebook executes the two core queries and validates headline math and
   plant-filtered scrap rates. DAX queries are read-only; endpoint discovery,
   Direct Lake metadata refresh and credentials remain manual UI checks.

Existing reverse relationships, duplicate relationship endpoints, wrong measure
home tables, unsupported relationship types or missing columns stop for manual
review rather than destructive guessing. Relationship updates enforce active,
many-to-one, single-direction behavior only for selected endpoint pairs.
Measure updates use the named home table and exact reviewed DAX/format; there is
no whitespace-normalizing comparison that could alter string-literal semantics.

### Manual rollback, not blanket replacement

Keep the reviewed `plan.json` **before** applying changes. Each proposed change
contains `before` and `after` definitions; the snapshot also contains
`original_database_definition` for full reference.

- For an updated measure, manually restore only its saved `before.dax` and
  `before.format` in the saved home table.
- For an updated relationship, restore only its saved endpoints, active state,
  cardinalities and filter settings, using its saved existing name.
- `before: null` means the object did not exist: remove only that newly added,
  approved object if rolling back, after checking dependencies.
- Re-read the live model and compare with the saved **after** state first.
  If another editor changed it, stop and reconcile. Never overwrite newer
  unrelated work, deploy the whole saved database, or run a blanket DAX reset.

A service/network failure during or after `SaveChanges` can leave commit status
uncertain. Inspect the explicit model in Fabric, compare with the snapshot, and
decide whether a fresh plan or scoped rollback is needed. There is intentionally
no automatic rollback against an arbitrary model.

## Verification boundary and API references

Offline tests exercise rejection/execution mocks, scoped diff/apply and drift,
generated freshness, missing-source failure, Python syntax, and the core
contract. They do **not** prove that these notebooks have run in a tenant.
Before workshop delivery, an authorized operator still needs to verify runtime
version and Semantic Link availability, actual context UUID values, schema-enabled
Lakehouse attachment, CSV staging, Spark/SQL endpoint behavior, lineage types,
row/KPI gates, Direct Lake table binding, TOM serialization/access, capacity XMLA
settings, permission profiles, snapshot download and manual scoped restoration.
Stop Spark after that verification. No live execution/provisioning/authentication
was performed to build these assets.

APIs were checked against first-party documentation and upstream implementation:

- [NotebookUtils runtime context and exact ID properties](https://learn.microsoft.com/fabric/data-engineering/notebookutils/notebookutils-runtime)
- [SemPy Fabric API: `create_tom_server`, `refresh_tom_cache`, `evaluate_dax`](https://learn.microsoft.com/python/api/semantic-link-sempy/sempy.fabric?view=semantic-link-python)
- [TOM `JsonSerializer.SerializeDatabase`](https://learn.microsoft.com/dotnet/api/microsoft.analysisservices.tabular.jsonserializer.serializedatabase?view=analysisservices-dotnet)
- [TOM model `SaveChanges`](https://learn.microsoft.com/dotnet/api/microsoft.analysisservices.tabular.model.savechanges?view=analysisservices-dotnet)
- [Upstream Semantic Link Labs TOM implementation](https://github.com/microsoft/semantic-link-labs/blob/main/src/sempy_labs/tom/_model.py)

The upstream wrapper was inspected for its connection and object APIs, but is
deliberately **not** used to save: a wrapper's automatic initialization or
save-on-close behavior is inappropriate for this scoped two-phase recovery.
