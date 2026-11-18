# Lab 2: curate trusted data and model it

**Outcome:** approve a scoped plan, execute only in a disposable synthetic
sandbox or offline reference, and independently validate a star schema.
Budget: 20 minutes before lunch, 25 minutes after. Files/tables should be
pre-staged; do not spend the core session rebuilding the environment.

**Inputs:** Lab 1 evidence, [dictionary](../../data-model/dictionary.json),
[expected counts](../../tools/expected_counts.json) and
[core model contract](../../data-model/model.json).

```text
Outcome: produce a trustworthy monthly manufacturing model from this fictional
extract. Read AGENTS.md, the Lab 1 evidence, data-model/dictionary.json and
data-model/model.json. Before editing, propose a small scoped plan: raw Bronze
preserved, exact duplicates removed, 26 invalid records quarantined with reasons,
typed/conformed Silver, unknown customer/defect members in Gold, no fact-to-fact
BatchID relationship. Explain good units versus scrap, the source late flag and
revenue ambiguity as SME decisions, not universal facts. List the exact files
and data affected, rollback and independent acceptance. Stop for plan approval.
After approval run make curate, not a live deployment. Verify counts, all
18 relationships and independent monthly SQL; do not relax an oracle to pass.
```

After reviewing and approving the proposed **offline** scope:

```bash
make dict.validate
make curate
make source.months
```

**Outputs:** `results/gold/*.csv`, `results/quarantine.csv`,
`results/curation.json`, `results/source-months.json` and ignored generation
metadata. The original source CSVs remain untouched. Quarantine preserves record
JSON and a reason; the 27 duplicate copies (25 runs plus one product and one
customer) are accounted for separately, not counted as quarantined records.

**Acceptance:** eight dimensions, four facts and a 120-row site/month aggregate.
Gold includes 3,629 production runs, 2,729 inspections, 270 maintenance events,
4,560 orders, 36 customers and 13 defect types (including unknown members).
Exactly 26 rejects: five invalid dates, six missing actual quantities, eight
negative scrap quantities and seven impossible demo defect counts. All 18 core
fact-to-dimension checks pass. Actual units **1,032,704**, planned units
**1,095,550**, scrap units **33,404**, displayed scrap rate **3.13%** and production
attainment **94.26%**. Do not average monthly percentages to obtain the total.

**Fabric variant, separately authorized:** follow
[the notebook procedure](../../docs/notebooks.md) and
[live access contract](../../docs/live-fabric.md). Execute 02 -> 03 -> 04 -> 05,
then create an isolated core semantic model and use 07's read-only plan before
any separately approved changes. Spark, Delta and semantic-link run in Fabric.
Notebook 04 is the default dimension catch-up; Dataflow Gen2 click-through is
not required. Utilities and Fabric-native Copilot are not required.

The notebook full-refresh/overwrite approach is **only** for disposable
synthetic sandboxes. Customer pipelines need approved incremental/merge and
history policies, not a copy of this overwrite pattern. No unattended production
task during lunch. An optional lunch task may inspect already-local evidence
or run a bounded approved synthetic notebook; name an owner and stop condition.

**Peer check:** independently inspect one quarantine record, one unknown
customer order, and a fact-to-dimension key anti-join. Does the proposed model
address the required grain without inventing meanings? Carry unresolved SME
questions into [the reporting lab](../03-reporting/README.md).
