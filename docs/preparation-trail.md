# Preparation trail: evidence, not a fictional conversation

This is the preparation record for **this implementation**, not a reconstruction
of an earlier Copilot chat. The original delivery at `0d220ea` was offline-only;
the later explicitly authorized execution-host-to-Fabric rehearsal is recorded
below. No successful Codespaces login, browser screenshot or customer defect
investigation is claimed.

## Real work brief and decisions

The implementation assignment requested a reusable GitHub Copilot workshop
using an owner-supplied synthetic baseline: preserve deterministic data and the
Python-to-notebook pipeline; make Codespaces browser-first; add discovery,
trusted curation/modeling and a controlled monthly defect; separate native AI;
guard live targets and verify locally. These requirements drove actual edits,
not a claim that Copilot independently discovered a customer's requirements.

The bounded task briefs used for implementation were:

- **Offline tools:** observe CSVs before trusting vendor claims, keep a typed
  canonical contract, reproduce quarantine/unknown-member decisions, compute
  source/month sums with a separate SQL implementation, and test a reviewed,
  drift-protected single-relationship repair.
- **Notebook adaptation:** reuse 02/03/04/05/07, remove all utility dependencies
  from the core model, enforce explicit runtime workspace/lakehouse/model scope
  and preserve a read-only proposal/snapshot before separately approved changes.
- **Browser/live boundary:** pin setup tooling, use supported CLI interfaces,
  make preflight/inventory read-only, fail before commands on absent approval,
  and restrict writes to new, explicitly approved synthetic notebook items.

The participant-ready versions of the prompts are in the three
[lab guides](../labs/01-discovery/README.md); they are executable task briefs, not
manufactured screenshots or attributed historical answers.

## Actual red-to-green evidence

Before configuration implementation, this command failed during collection with
`ModuleNotFoundError: No module named 'workshop'`:

```bash
uv run pytest tests/test_config.py
```

After strict config implementation, the targeted run reported **10 passed**.
Before discovery/curation/reporting implementation, the new behavioral tests
failed with `ModuleNotFoundError: No module named 'workshop.discovery'`.
After implementation, discovery and curation tests plus inherited seeder tests
passed; the final complete suite also exercises the monthly defect and repair.
These are actual observed transitions during implementation, not instructions
to remove modules to manufacture a future failure.

The monthly lab is deliberately replayable red-to-green without changing test
code. The original source oracle is SQL over deduplicated **raw** source rows
joined to the date dimension; the curated model uses a separate Python path.
An inactive Date relationship repeats the all-time total. Review the one-edge
change and its digest, approve it, then repeat the exact same independent
month-by-month check. A correct total alone is insufficient.

The actual participant replay produced **30 failing monthly comparisons** before
repair (for example, January 2024 source **34,773** versus repeated model
**1,032,704**) and **30 matching months, no problems** after approving only the
inactive production-to-Date relationship change. The before/after evidence and
SHA-bound plan remain in ignored local results/state, not fabricated live logs.

## Facilitator replay

```bash
make setup
make gates
make offline
make report.fault
make report.check       # expected failure, preserve results/monthly-before.json
make report.plan        # inspect the plan; do not approve blindly
# Paste only after review:
make report.repair APPROVE_PLAN=<reviewed-sha256>
make report.check
git diff main...HEAD --stat
git log --oneline main..HEAD
git show HEAD -- tools/notebooks workshop tests
```

For a fresh replay, use a fresh Codespace/clone, or archive local evidence and
explicitly remove only the existing offline model fixture before `report.fault`.
The tool intentionally refuses to overwrite an existing exercise. Local logs,
plans, snapshots, generated metadata and results are ignored; do not commit them
or substitute invented output in a demo.

## Honest readiness labels

| Area | Status |
|---|---|
| Deterministic synthetic data and local behavior | Executable; run `make gates` for release-specific results |
| Notebook source generation and static validity | Executable local checks; not proof that Fabric runtime executed them |
| Copilot CLI/Fabric CLI command interfaces | Public documentation and local help checked; no account login performed |
| Devcontainer/Codespaces runtime | Configured, **not boot-tested here**: the available Docker client could not connect to a daemon |
| Fabric data notebooks 02/03/04/05 | **Passed from the approved execution host**, not from Codespaces; see follow-up evidence below |
| Core Direct Lake model and actual DAX | **Passed from the approved execution host**; 07's TOM runtime path remains a separate unexecuted gate |
| Group concurrency/capacity readiness | **Pending** measured rehearsal; no capacity created or resized |
| Customer domain/report objective | **Pending** approved metadata, domain selection and SME definitions |

Show the real Git diff alongside these labels. Do not equate unit-tested mock
adapters with a successful live end-to-end workshop.

The pinned container manifest and local pinned Copilot CLI executable were
checked successfully. This confirms artifact availability/version only, not a
container boot, login, network policy or live Fabric run.

Original offline release gate: `make gates` reported **205 passed** and passed Ruff,
Bash syntax, generated-notebook freshness, generated expected-results freshness,
and dictionary/model cohesion. Python compilation and `npm ls --depth=0` also
passed. The shipped `demo.yaml` was exercised against live preflight and correctly
refused access before any Fabric invocation. No live acceptance result is implied.

## Authorized execution-host-to-Fabric follow-up

After separate user approval of an isolated existing-capacity rehearsal target,
the existing execution host completed real Fabric preflight, one schema-enabled
synthetic Lakehouse creation, upload of the thirteen approved CSVs, publication,
and sequential execution of notebooks **02 -> 03 -> 04 -> 05** on Fabric Runtime
**2.0**. All four jobs completed with their real count/quarantine/relationship/KPI
gates. The workspace's session API subsequently reported all four owned Spark
sessions `Succeeded` with end timestamps. No tenant/RBAC settings were changed.
Capacity lifecycle remained with the separately authorized coordinator.

Actual OneLake production/date CSVs were downloaded and SHA-256 compared with
the committed synthetic inputs. Both matched byte-for-byte; the independent
source SQL over those downloaded files produced **30 months** and **1,032,704
actual units**. This is stronger evidence than querying a headline card, but
still does not establish a real customer's definitions. The source SQL ran
locally over downloaded actual OneLake files; this rehearsal did not execute
the optional SQL-endpoint T-SQL query.

The first live notebook create exposed a real adapter defect: Fabric returned
an HTTPS regional `wabi-*.analysis.windows.net` LRO location rather than the
canonical host. The request outcome was reconciled by exact owned metadata and
remote notebook content, without resubmitting or creating a duplicate. The fix
requires the regional host to match the authenticated response's
`home-cluster-uri`, keeps the exact operation/job path, and reissues only
canonical relative CLI routes. Its regression failed first, then passed;
unknown/mismatched hosts still fail closed. The updated local release gate
reports **211 tests passed**, including a regression that rejects an extra virtual
blank month even when the calendar rows otherwise match.

The same isolated rehearsal created one real **12-table Direct Lake** semantic
model from its approved Gold OneLake tables using the documented creation API.
Its full original definition was saved before a hash-reviewed diff added only
the **18 core relationships and 14 measures**. Tables, partitions, sources and
other metadata were preserved. All 14 actual remote DAX measure checks passed,
and every one of the 30 monthly DAX rows matched the independent SQL oracle over
the byte-verified OneLake inputs.

The controlled live reporting exercise then changed **only** the production
Date relationship's active state. After a verified metadata refresh, actual DAX
returned the all-time **1,032,704** units for each of the 30 calendar months and
also exposed **one virtual blank-month row**. Both the wrong values and extra
row were retained as failed evidence; they were not filtered away to force a
match. A separately hash-reviewed one-edge repair, completed refresh and the
same independent queries restored **exactly 30 matching months**, no extra
blank row, and all 14 original measure values. The model was left healthy.

Two service-contract details were recorded rather than hidden: a successful
definition-update LRO can have no result body (`OperationHasNoResult`), and
immediate post-update queries returned missing-table metadata until the model's
refresh completed. Neither a write acknowledgment nor that intermediate error
was counted as business acceptance. The reusable notebook adapter only uses
result-bearing create/get-definition operations; model setup/reconciliation
was a separately approved, exact-ID REST rehearsal. Notebook 07's native TOM
recovery path was **not executed**, so its environment/XMLA prerequisites remain
a separate rehearsal gate.

Codespaces itself was **not created or billed**: the linked automation
credential could read repository/machine metadata, but listing was denied for
missing Codespaces permission. No credentials were substituted, caches copied,
identities switched or denied APIs retried without changed authorization.
Browser-first onboarding, Codespaces-to-Fabric, Copilot CLI in that Codespace,
customer-device/Conditional Access and group rehearsal therefore remain **pending**.
