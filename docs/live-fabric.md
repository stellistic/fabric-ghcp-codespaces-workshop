# Live Fabric adapter — explicit sandbox opt-in

**Codespaces POC and group rehearsal: PENDING.** An explicitly authorized
execution-host rehearsal verified real tenant/workspace preflight, synthetic
file upload, notebook publication and all four core data notebooks on Fabric
Runtime 2.0, followed by separately scoped REST model/DAX reconciliation and a
controlled Date-fault/repair proof. Those model calls are not extra adapter
actions. This does **not** prove Codespaces authentication, Conditional Access,
customer-device routing, group concurrency or a production recovery path.
The [preparation trail](preparation-trail.md) separates the original offline
delivery from the later authorized live rehearsal and records remaining gates.

Use the [browser-first Codespaces setup](codespaces.md). GitHub Copilot assists with
code; Microsoft Fabric executes notebooks. Native Fabric Copilot and AI Functions
are **not required**.

## Boundaries and permissions

An organizer supplies an **existing**, capacity-backed sandbox workspace and a
schema-enabled Lakehouse **inside that workspace**. The adapter never creates
workspaces/Lakehouses, assigns capacity/RBAC, queries business data/semantic models,
updates existing item definitions, or deletes anything. It cannot publish the
semantic-model recovery notebook or the optional AI lab. No Admin/Member role is
the default.

| Action | Minimum intended access (also subject to tenant policy, API scopes and item permissions) |
|---|---|
| Preflight: auth state, workspace GET, Lakehouse GET | Viewer/read access to selected workspace and Lakehouse |
| Inventory: selected workspace item metadata | Viewer/read APIs; individual items may require additional grants |
| Get results: previously recorded job status/optional exit value | Read access to the notebook/job; API `Item.Read.All` or notebook equivalent |
| Publish new notebook | Workspace **Contributor**, `Notebook.ReadWrite.All` or `Item.ReadWrite.All`; supported Fabric capacity |
| Run approved notebook | **Contributor**, notebook execute permission/API scope and write access to the selected Lakehouse |
| Semantic queries (outside this adapter) | Appropriate semantic-model Read/**Build**, licensing and source permissions; Viewer alone is not sufficient |

Use a separate disposable workspace/Lakehouse per participant or nonconcurrent
team. Notebook runs perform guarded synthetic **full refreshes** of Bronze/Silver/
Gold tables, plus run-audit writes; publishing only creates a notebook, but running
can overwrite its allowlisted sandbox tables. Different notebook names do not
isolate a shared Lakehouse. Manually stage the 13 synthetic plant CSVs under the
selected Lakehouse's `Files/landing/plant` before running Bronze.

## Complete local configuration

```bash
cp demo.yaml demo.local.yaml
```

Edit the **whole file**, not a partial overlay:

```yaml
version: 1
profile: synthetic-core
seed: 20261001
fabric:
  tenant_id: null       # replace with explicit nonzero lowercase canonical UUID
  workspace_id: null    # replace with exact sandbox UUID
  workspace_name: null  # replace with exact current display name
  lakehouse_id: null    # replace with Lakehouse UUID in that workspace
  model_id: null        # not used by this adapter
  sandbox: false
security:
  approved_data: synthetic-only
  allow_live_read: false
  allow_live_write: false
```

Defaults deliberately fail **before any subprocess**. Supply all four target
fields and set `allow_live_read: true` for metadata reads. `approved-metadata` is
also accepted for reads; it never permits a write or saves notebook exit values.
Only after reviewing the notebooks and confirming a disposable synthetic target,
set `sandbox: true` and `allow_live_write: true`; retain
`approved_data: synthetic-only`. Each write additionally needs the separate
`--approve-workspace` flag equal to that **exact workspace UUID**.

`demo.local.yaml`, `.state/`, and `results/` are already git-ignored. They must never
be force-added, attached to AI prompts, or uploaded with credentials. Do not store
tokens, passwords or connection strings in configuration/notebooks.

## Commands (run inside the Codespace)

After the separate manual Fabric login in [codespaces.md](codespaces.md):

```bash
uv run --frozen python -m workshop.live --help
uv run --frozen python -m workshop.live --config demo.local.yaml preflight
uv run --frozen python -m workshop.live --config demo.local.yaml inventory
```

Every action independently verifies Fabric CLI authentication (`logged_in: true`
and the authenticated tenant UUID), GETs the exact workspace UUID and checks its
name, then GETs the Lakehouse through that workspace and checks its `workspaceId`.
Configured identity alone is never treated as proof of the active tenant.

The following are **write commands**, not setup commands. Replace `EXACT_UUID`
with the approved workspace UUID and choose your participant slug:

```bash
uv run --frozen python -m workshop.live --config demo.local.yaml publish-notebook \
  --notebook bronze --participant team01 --approve-workspace EXACT_UUID
uv run --frozen python -m workshop.live --config demo.local.yaml --timeout 900 run-notebook \
  --notebook bronze --participant team01 --approve-workspace EXACT_UUID
uv run --frozen python -m workshop.live --config demo.local.yaml get-results \
  --notebook bronze --participant team01
```

`--config` and `--timeout` go **before** the action; action-specific flags go after.
Timeout is 1–1800 seconds, default 300. Participant slugs use 1–24 lowercase
letters/digits/underscores/hyphens and begin with a letter/digit. The fixed notebook
choices, in execution order, are:

| Choice | Fixed repository input |
|---|---|
| `bronze` | `notebooks/02_bronze_ingest.ipynb` |
| `silver` | `notebooks/03_silver_transform.ipynb` |
| `silver-dims` | `notebooks/04_silver_dims_catchup.ipynb` |
| `gold` | `notebooks/05_gold_star_schema.ipynb` |

There is no arbitrary file, URL, endpoint, item-ID or job-ID argument. The adapter
rejects symlinks in notebook/state/results paths. It builds a clean ipynb definition,
removes outputs and unapproved metadata/environment bindings, and sets the default
Lakehouse UUID, its workspace UUID, and `known_lakehouses`. Original repository
files and their fail-closed parameter defaults are unchanged. Run requests supply
the approved UUIDs as the generated notebooks' `workspace_id` / `lakehouse_id`,
plus `sandbox`, `approval` and `batch_id` as typed notebook parameters.
Sources declaring the explicit `expected_workspace_id` / `expected_lakehouse_id`
variant use those exact UUID parameter names instead. Only these two complete,
fail-closed literal parameter contracts are accepted, determined offline from the
tagged cell; missing parameters or pre-approved defaults block all subprocesses.

Notebook names are deterministic: `ghcp_<participant>_<choice>_<content-hash12>`.
Creation checks all bounded inventory pages first. An existing name without matching
local ownership state is an error, **never an overwrite/adoption**. Reuse and execution
check the recorded tenant/workspace/Lakehouse/name/hash, live item metadata and the
remote notebook definition. Executable-content or attachment drift blocks reuse/run.
Changed code/binding produces a new name/state entry; it does not replace old items.

## Results, bounds and uncertain outcomes

- Transport is verified Fabric CLI **1.7.0** `fab api <fixed-route> -X get|post
  --show_headers --output_format json`, executed with argument arrays, no shell and
  closed stdin. The adapter never runs `auth login` or falls back to synthetic success.
  Raw stdout/stderr and authentication fields are not printed or saved.
  CLI settings enabling debug logging or plaintext encrypted-cache fallback are
  rejected; credential-cache files are never inspected.
- Inventory follows opaque `continuationToken` values only against the same fixed
  workspace route, with token validation, repeated-token detection, at most 100 pages
  and 10,000 items. External/changed continuation URIs are rejected.
- Each subprocess is capped at 30 seconds; the whole action has the configured
  deadline, at most 256 requests, 60 polls per operation and 120 job polls. `429`
  produces a clear rate-limit failure without automatic retries. Respect the
  service's delay before manually retrying; writes with uncertain outcomes need
  reconciliation, not resubmission.
- Notebook creation uses the documented `format: ipynb`, single
  `notebook-content.ipynb` part with `payloadType: InlineBase64`. The optional
  `.platform` part is not sent.
- HTTP `202` means **accepted, not created/completed**. Persist the operation/job
  UUID before polling. Validate the exact HTTPS Fabric v1 path, respect
  `Retry-After`, poll operation state and then its `/result`, or poll the recorded
  job instance. Polling deadlines survive process restarts; immediate retries
  cannot bypass a saved service delay. Unknown/failed statuses are never success.
  Fabric can return a regional `wabi-*.analysis.windows.net` Location: it is
  accepted only when its host matches the same authenticated response's
  `home-cluster-uri`. The adapter never uses the response URL as an arbitrary
  credential destination: it reissues only the validated relative route through
  `fab api`, leaving authenticated service routing to the supported CLI.
- State is stored under `.state/live/<workspace>/ghcp_*.json`, with private files
  and an exclusive per-entry lock. Preserve accepted-operation state and use the
  read-only `get-results` to resume creation polling or retrieve the last known
  job. Job results are private `results/live/<workspace>/<job-id>.json` files.
  Console output contains IDs/status/file paths, **not exit-value content**.
  Where returned, `exitValue` is saved only for `synthetic-only` approval.
- If no job has been submitted, `get-results` verifies the live owned item and
  reports `NotRun`, never a successful notebook run inferred from a local state file.
- Results mean **job metadata/optional exit value**, not cell logs, table extracts
  or semantic-query results. The notebooks may return no exit value; this is not
  fabricated into a data result. Failed runs are failures; diagnose using the
  Fabric run UI without pasting sensitive logs into chat.
- A timeout stops local waiting, **not** remote compute. The adapter does not cancel
  jobs automatically. A crash/timeout between submission and receipt of an ID
  leaves a `submitting`/`run-submitting` entry and blocks automatic resubmission.
  Review the exact deterministic name/recorded IDs in Fabric with the organizer.
  Do not remove locks/state merely to bypass this safeguard.

State is a local ownership/reproducibility record, not a cryptographic authorization
boundary against someone who can edit your checkout. Do not share participant
state or trust unreviewed notebooks. Fabric may normalize notebook metadata; the
live POC must confirm round-trip compatibility. Unexpected normalization fails
closed rather than running unverified code.

## Manual teardown — only exact owned notebook IDs

1. Stop/inspect any running job using its recorded workspace, notebook and job UUIDs
   in the Fabric UI. Check completion/cancellation there; a local timeout is not proof.
   Job `Completed` can precede Spark-session shutdown: inspect the documented
   workspace `spark/livySessions` read API and confirm the exact owned sessions
   have terminal states/end timestamps. A `JobAlreadyCompleted` cancellation
   response is not evidence that a session has stopped. The host rehearsal
   confirmed all four sessions eventually reached `Succeeded`; do not assume
   that outcome for another run.
2. Read your `.state/live/<workspace>/ghcp_*.json` files locally. In the **selected
   sandbox workspace**, verify each recorded notebook UUID, deterministic name and
   ownership description. For accepted creations, resolve the saved operation ID;
   for unknown submissions, reconcile the exact name before touching anything.
3. Manually delete **only those verified notebook IDs** with the organizer's approval.
   Never bulk-delete by prefix alone, delete user items, the Lakehouse/workspace,
   semantic models, or capacity. This adapter does not provide a delete command.
4. Organizer-owned sandbox tables/landing data require a separate reviewed cleanup.
   Stop Spark sessions. Log out of Fabric and Copilot as described in Codespaces docs,
   close the encrypted-keyring shell, then stop/delete the Codespace. Do not capture
   authentication/token-cache files as workshop evidence.

## Offline validation and Make integration

```bash
uv run --frozen python -m pytest tests/test_live.py --basetemp=.state/pytest-live
uv run --frozen ruff check workshop/live.py tests/test_live.py
```

These tests replace every subprocess and do not authenticate. The equivalent
named Make targets are:

```bash
make fabric.preflight CONFIG=demo.local.yaml
make fabric.inventory CONFIG=demo.local.yaml
make fabric.publish CONFIG=demo.local.yaml NOTEBOOK=bronze PARTICIPANT=team01 APPROVE_WORKSPACE=EXACT_UUID
make fabric.run CONFIG=demo.local.yaml NOTEBOOK=bronze PARTICIPANT=team01 APPROVE_WORKSPACE=EXACT_UUID TIMEOUT=900
make fabric.results CONFIG=demo.local.yaml NOTEBOOK=bronze PARTICIPANT=team01
```

These are real adapter calls, not simulations: only invoke them after the
separate approvals above. The default configuration refuses access before any
subprocess. Manual exact-ID cleanup remains deliberate; no delete target exists.

## Verified sources

Installed 1.7.0 `--help` and offline source were the command/envelope authority.
No live `auth status` was invoked during development. Online CLI docs may describe
newer flags not present in the pin; in particular this pin does not advertise an
Azure-CLI/device-code login flag.

- [Fabric CLI](https://microsoft.github.io/fabric-cli/) and [authentication examples](https://microsoft.github.io/fabric-cli/examples/auth_examples/)
- [Create Notebook](https://learn.microsoft.com/en-us/rest/api/fabric/notebook/items/create-notebook)
- [Notebook definition](https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/notebook-definition)
- [Long-running operations](https://learn.microsoft.com/en-us/rest/api/fabric/articles/long-running-operation)
- [Run on-demand item job](https://learn.microsoft.com/en-us/rest/api/fabric/core/job-scheduler/run-on-demand-item-job)
- [Get item job instance](https://learn.microsoft.com/en-us/rest/api/fabric/core/job-scheduler/get-item-job-instance)
- [Notebook public APIs / exit values](https://learn.microsoft.com/en-us/fabric/data-engineering/notebook-public-api)
