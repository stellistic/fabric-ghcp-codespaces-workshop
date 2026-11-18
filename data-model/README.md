# Dictionary contract, version 1

[dictionary.json](dictionary.json) is authoritative for **this synthetic
extract**, not a claim about a real organization. Each entity declares source
columns, one primary key, nullable columns, target placement and grain. Shared
attribute definitions carry explicit types and descriptions. Relationships
declare the 18 core many-to-one, single-direction fact-to-dimension joins.
[model.json](model.json) holds the corresponding semantic tables and DAX.

This compact JSON layout deliberately replaces the larger demo-scaffold
multi-file graph structure: there is one small, frozen dataset, no customer
generation service, no cross-warehouse routing, and no lifecycle engine.
`make dict.validate` checks coverage, ordered CSV schemas, typed descriptions,
primary-key targets, duplicate edges, graph connectivity and model cohesion.
`make curate` independently enforces actual keys and all 18 foreign-key joins.

Data types describe the **curated intent**; raw Bronze strings deliberately
violate it. Seeded issues, correction decisions and enums are declared here;
counts and KPI acceptance remain in
[expected_counts.json](../tools/expected_counts.json). Calendar and grain
questions must be resolved with an SME before reuse elsewhere. `BatchID` is a
label, not a unique primary key. Do not join fact tables on it.

Eight dimensions and four facts enter the core model. `FactAnomalyEvent` is
retained for discovery/bronze only: its narrative is an illustration, not proof
of a root cause or permission to send notifications. `agg_plant_month` is a
derived SQL checkpoint, not a thirteenth core model table.

[vendor-dictionary.json](../fixtures/vendor-dictionary.json) is intentionally
wrong: it omits an actual field, invents an absent field and claims uniqueness.
The discovery tool reports observed nulls, duplicates, unknown/missing columns,
orphan keys and rejected join candidates **without changing the input**.

Generation is frozen to seed `20261001` and the owner-supplied source snapshot.
`make data.build` reproduces the seeded CSVs byte-for-byte; `make curate` records
the current Git SHA, dictionary version/hash, profile, timestamp and row counts
under ignored `.state/`. Never change the oracle merely to make a check green.
