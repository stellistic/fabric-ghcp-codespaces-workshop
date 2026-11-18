# Facilitator runbook

The audience is IT, data and analytics practitioners who already have Fabric
data but need to understand many source tables, challenge vendor dictionaries
and ERDs, curate trusted stars/measures and troubleshoot wrong monthly figures.
The method is reusable; this dataset is **fictional manufacturing**, not a
clinical model. Business and clinical interpretation always needs an SME.

## Run of show

| Time | Activity and exit evidence |
|---|---|
| 10:00–10:15 | Requirements and the outcome/context/investigate/evidence/approve/execute/verify/iterate loop; define one domain/report and business owner |
| 10:15–10:40 | Show how GitHub Copilot helped prepare this workshop: real task briefs, source diffs, failing/passing checks and [preparation trail](../preparation-trail.md); do not live-regenerate everything |
| 10:40–11:00 | Browser Codespaces, Copilot CLI authentication and separate read-only Fabric metadata preflight; record target identity and unresolved access blockers |
| 11:00–11:40 | [Discovery lab](../../labs/01-discovery/README.md): challenge the dictionary, test keys/joins, distinguish evidence from hypotheses |
| 11:40–12:00 | [Curation lab](../../labs/02-curation-model/README.md): review a bounded sandbox plan and begin; pre-staged artifacts avoid upload time |
| 12:00–13:00 | Lunch; optional bounded local/read-only task or already-approved synthetic task with an owner and timeout; no unattended production writes |
| 13:00–13:25 | Complete model/curation acceptance, inspect quarantine and verify 18 joins; discuss unresolved definitions |
| 13:25–14:05 | [Monthly reporting lab](../../labs/03-reporting/README.md): capture red, review scoped diff, approve, repair and prove monthly green |
| 14:05–14:40 | Read-only application to one approved customer domain/report; otherwise use synthetic fallback and explicitly mark the real-environment objective incomplete |
| 14:40–15:00 | Independent challenge, exit checks, SME definitions, evidence handoff, stop Spark sessions and exact-item cleanup |

## Readiness and signoff

Keep the completed copy of
[approved-environment.md](../../templates/approved-environment.md) outside Git.
Initial status is **pending** unless an actual dated rehearsal supplies evidence.
Passing local gates is not evidence that Fabric access or Codespaces works for
participants.

| Gate | Evidence and responsible role | Initial status |
|---|---|---|
| Local materials | Maintainer runs `make gates` and complete fault/repair replay | See committed preparation trail; replay for each release |
| Data handling | Security/data owner approves synthetic assets, metadata scope and Copilot policy | Pending |
| Identity and Conditional Access | Identity owner witnesses sign-in from remote Linux Codespace, correct tenant/account and revocation path | Pending |
| Network | Network owner validates required GitHub/npm/PyPI/Fabric/Power BI endpoints, proxies/private links and browser sign-in without bypassing policy | Pending |
| Product access | Organizer confirms GitHub Copilot CLI entitlement, Codespaces policy/budget, Fabric and Power BI licensing | Pending |
| Sandbox | Platform owner selects existing capacity and isolated workspace/lakehouse/model per pair/person; no shared overwrite target | Pending |
| One-user POC | Facilitator completes browser onboarding, metadata preflight, notebook round trip and source-to-live-DAX monthly comparison | Pending |
| Group rehearsal | Platform owner measures launch/runtime/throttling at intended attendance and records safe parallelism | Pending |
| Real domain/report | Data owner supplies approved metadata and source reconciliation; SME agrees grain, measures, month/calendar and filters | Pending |

### One-user proof of concept

Use the [Codespaces guide](../codespaces.md) and [live adapter](../live-fabric.md).
Rebuild the pinned devcontainer; run offline gates first. Authenticate interactively
as the approved account without putting tokens in prompts or terminal history.
Confirm the exact tenant/workspace/lakehouse/model, then run read-only preflight
and inventory. Exercise one separately authorized synthetic notebook publish/run
and fetch its job status. Complete all core notebook/model checks, monthly SQL
versus actual DAX, and cleanup. Record what worked, the tested versions,
elapsed times and any policy failures; **do not declare a group ready from a
local mock test**.

### Group rehearsal and capacity

Pre-stage the 13 files and checkpoints before participants arrive. Give each
pair/person a separately approved isolated sandbox; names alone are not sufficient
isolation. Use the same immutable dataset and workbook/notebook version.
Measure concurrent Spark sessions, cold-start delay, notebook duration, capacity
utilization, memory pressure, queued work and throttling at intended attendance.
Choose a measured stagger/parallelism limit and record it; do not guess an SKU,
resize capacity, or grant broader roles to make a demo work. Stop Spark sessions
after each exercise and again at exit.

## Time cut lines and fallback

At 11:00, unresolved network/authentication moves the **exercise** to the offline
path while the platform owner investigates separately. At 11:40, switch unfinished
cleansing to notebook 04/curation reference and retain unresolved evidence.
At 13:25, use the validated offline Gold checkpoint if a Fabric job is still
queued. Reserve the monthly investigation; do not consume it on low-code setup.
At 14:05, use only a previously approved real domain/report. If absent or blocked,
record **synthetic learning complete / real-environment objective incomplete**.
Never silently substitute a synthetic success for customer readiness.

Checkpoint/catch-up artifacts are the seeded CSVs, `make curate` outputs,
[notebooks 02–07](../notebooks.md), canonical model and generated
[expected results](expected-results.md). The utility appendix and report-generation
experiments are cut first. Core work never requires Fabric-native Copilot.

## Troubleshooting boundaries

| Symptom | Safe response |
|---|---|
| Copilot CLI unavailable | Check Codespaces post-create output, pinned package setup, Node version and entitlement; do not switch to a different unsupported desktop surface mid-lab |
| Wrong tenant/account, expired session | Stop; log out and repeat approved sign-in with tenant selection; rerun read-only preflight; never reuse someone else's token |
| CA/device/network/private-link denial | Record the policy/error category without tokens; involve identity/network owner; use offline fallback, never bypass controls |
| Config rejected | Review the complete ignored override; canonical UUIDs, exact workspace name and explicit booleans are required; do not disable guards |
| Permission denied | Compare the action-specific access matrix; ask the owner for the minimum approved item permissions, not blanket Admin/Member |
| Fabric notebook missing tables | Verify default lakehouse UUID and execution order; use pre-staged catch-up, not a customer's current workspace |
| Source totals differ | Recount source, quarantine and duplicates before changing a measure; do not modify an acceptance constant to pass |
| Grand total right, months wrong | Inspect Date table coverage, active relationship, cardinality/filter direction and DAX filter removal; reconcile every month |
| Concurrent overwrite or model drift | Stop the write, preserve snapshots and isolate targets; re-plan and obtain fresh scoped approval |
| Throttling/slow Spark | Stop nonessential sessions, stagger within measured limits and retain job IDs; no capacity or tenant changes |

## Evidence and media

Use real task briefs, Git diffs and deterministic check output. Ask before any
recording, screenshot or sharing. Capture only approved synthetic screens;
exclude identities, account menus, URLs with tenant IDs/tokens, notifications and
other tabs. Keep captures ignored/outside Git until reviewed. The inherited
105 screenshots and ten recordings were **not bulk-copied**: they can contain
stale tenant/event UI and identities. Reuse an individual source image/clip only
after a facilitator verifies its instructional relevance and redacts it; no
recapture of unrelated screenshots is necessary for this Markdown-first kit.

## Exit and cleanup

Ask participants to explain one rejected join, one SME question, the approved
diff and why totals alone miss a Date defect. Collect the approved evidence
record, not credentials. Stop every Spark session in the Fabric notebook UI.
Review only owned item IDs from ignored state and the approved environment
record; delete exact disposable items manually under owner approval as described
in the live guide. Never delete a shared workspace/capacity or broaden RBAC.
Log out of Copilot/Fabric in shared environments, close/delete billable Codespaces
according to the organizer's policy, and retain only approved evidence.
