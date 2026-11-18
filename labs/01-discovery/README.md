# Lab 1: discover data and challenge a dictionary

**Outcome:** a reviewable evidence pack for 13 source tables, not a guessed ERD.
Budget: 40 minutes. Prerequisite: [browser onboarding](../../docs/codespaces.md).

**Inputs:** [fictional CSVs](../../data/landing/plant), the deliberately imperfect
[vendor claims](../../fixtures/vendor-dictionary.json), and a requested business
outcome: explain manufacturing output by month and site without losing records.
Read the canonical dictionary only **after** forming the first evidence-based
observations; it is the facilitator's answer contract, not vendor evidence.

Paste this task brief into **GitHub Copilot CLI** in the Codespaces terminal:

```text
Outcome: assess whether these synthetic extracts can support trusted monthly
production reporting. Read AGENTS.md. Work read-only. Inspect data/landing/plant
and fixtures/vendor-dictionary.json; do not assume field names prove meaning.
Propose a bounded investigation, then use make discover. Identify row grain,
columns absent from the vendor dictionary, declared fields absent from data,
blank values, exact duplicates, duplicate candidate keys and orphan foreign keys.
Test the proposed customer join and BatchID fact-to-fact join. Separate direct
evidence from hypotheses and SME questions. Do not clean files or contact Fabric.
Return a small candidate star schema plus rejected relationships with reasons.
Stop before any changes and give acceptance criteria for a proposed curation.
```

Run independently:

```bash
make discover
```

**Output:** ignored `results/discovery.json`, plus a short evidence/decision
record using [the investigation template](../../templates/investigation.md).
Have a peer inspect CSV headers and recount one finding without accepting the
assistant's narrative.

**Acceptance:** 13 tables, 12,279 rows; production has 25 exact duplicate rows
and six blank `ActualUnits`; the vendor omits `OperatorTeam` and invents
`RunDurationMinutes`; customer dimension has one duplicate key; six orders
reference absent customer 999. Reject the raw customer join until uniqueness
and unknown-member handling are resolved. Reject BatchID as a many-to-one join:
the proposed target is not unique. A clean PlantKey join supports a candidate
relationship, not the business interpretation of that relationship.

Discuss why a plausible diagram is insufficient. Product/customer duplicate
rows must not multiply fact values. Unknown members preserve counts but do
not resolve missing business meaning. Missing source fields are not permission
to invent them.

**Scaling boundary:** this validates the provided extract, not a 200+ table
estate. For a real estate, obtain an approved metadata-only inventory, select
one domain/report with its owner, inspect only allowlisted schemas, sample
within approved limits, and expand in reviewed batches. Record coverage and
unknowns explicitly. Never upload an estate-wide export into Copilot by default.
For a staged synthetic Fabric lakehouse, use the browser SQL editor and the
read-only [allowlisted schema query](../../queries/schema-inventory.sql);
workspace item inventory alone does not establish a table's columns or keys.
Any customer allowlist change needs owner review before running a query or
sending its results to an assistant.
Do not use the synthetic model-recovery notebook as a customer discovery
shortcut: its TOM connection can require model write permissions even when
planning. Use an approved read-only metadata/query interface instead; do not
broaden access solely to make inspection convenient.

**Checkpoint:** use the canonical dictionary for comparison, but retain
contradictory evidence and unresolved definitions. Continue to
[trusted curation and modeling](../02-curation-model/README.md).
