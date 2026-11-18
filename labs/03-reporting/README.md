# Lab 3: diagnose repeated monthly figures

**Outcome:** reproduce a controlled defect, explain the evidence, review a
minimal diff, repair and prove the same regression now passes. Budget: 40 minutes.

**Inputs:** curated synthetic data from Lab 2, the healthy model contract,
[independent source SQL](../../queries/monthly-source.sql), and
[monthly DAX](../../queries/monthly.dax).
The fault is an inactive production-to-Date relationship in a **copy**, never a
production model. The offline implementation simulates only propagation of that
Date filter for `Actual Units`; it does not execute DAX or prove a real service works.

```bash
make report.fault
make report.check
```

The second command **must fail**: each month repeats the overall 1,032,704 units.
Keep `results/monthly-check.json` as before evidence. The original healthy fixture
is preserved in `.state/model.original.json`.

```text
Outcome: diagnose repeated monthly Actual Units in this disposable synthetic
copy. Read AGENTS.md. Compare raw-source SQL, curated facts, model relationships
and the Actual Units SUM definition. Do not blame an actual customer report.
Consider date coverage, row grain, duplicate joins, relationship activity and
direction, and measures that remove date filters. State evidence versus
hypotheses. Run make report.check to reproduce; propose the smallest repair.
Use make report.plan and show the one-edge diff, base SHA and rollback evidence.
Stop for approval. Never reset every measure, change source totals or edit a live
model to make a card look right. After approval, apply only the reviewed hash
and independently rerun monthly reconciliation plus local regression checks.
```

```bash
make report.plan
# Inspect results/repair-plan.json. After approval, paste the exact sha256:
make report.repair APPROVE_PLAN=<reviewed-sha256>
make report.check
```

**Outputs:** before snapshot, reviewed SHA-bound plan, pre-repair snapshot,
and passing independent reconciliation. A changed model invalidates the plan;
investigate the drift and obtain a fresh review rather than forcing it through.
Rollback restores the captured healthy fixture only after approval of the
current file SHA: `make report.restore APPROVE_PLAN=<current-model-file-sha256>`.
`report.fault` refuses to overwrite an existing exercise; archive local evidence
and explicitly remove only `.state/model.json` before starting a fresh attempt.

**Acceptance:** all **30 production months** appear exactly once, integer units
match independently in every month and in the overall total. Missing/extra
months, duplicate month rows, nulls, non-finite quantities, fractional counts,
or a rearrangement with the same grand total fail. Counts use **zero tolerance**.
Rounded headline rates use absolute tolerance 0.00005 only; revenue uses 0.01.

**Live extension:** use a separately approved copied model, snapshot its
definition, and inspect 07's scoped plan. Do **not** inject this fault into a real
customer model. Execute the monthly DAX in Fabric's supported browser query
surface or approved semantic-link notebook with explicit workspace/model IDs.
Run [monthly-fabric.sql](../../queries/monthly-fabric.sql) in the approved SQL
analytics endpoint's browser editor as the separate relational source check;
confirm its result also agrees with the raw-source oracle for the same synthetic
version. An item inventory or a successful model refresh is not reconciliation.
Export approved results into ignored `results/`; normalize to:

```json
[
  {"YearMonth": "2024-01", "Actual Units": 123}
]
```

The number above illustrates shape, not an expected value. Then run:

```bash
uv run python -m workshop.cli report-check --dax-results results/live-months.json
```

For the synthetic model, compare against this repo's source oracle. For a real
customer report, use that domain's separately approved source/month SQL and
definitions instead; the K-Corp numbers are never its acceptance oracle.
The CLI validates supplied evidence, not its authenticity; record query text,
timestamp, exact model/workspace, filter context and source version for peer review.

**Independent challenge:** investigate a different month/filter without having
Copilot suggest the expected answer first. Explain why a correct total or plant
breakdown alone would have missed the Date defect. Finish the
[customer application record](../../templates/customer-application.md), retaining
any business definitions that still require an SME.
