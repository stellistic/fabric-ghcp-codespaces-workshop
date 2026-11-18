# GitHub Copilot Workshop

Use **GitHub Copilot as an agentic assistant** to investigate data, review a
curation plan, and diagnose a repeated-month reporting defect. **Microsoft Fabric
is the target data platform**, not the assistant. Fabric/Power BI Copilot and
Fabric AI Functions are separate, optional products, not core prerequisites.

The supported participant surface is **GitHub Codespaces in a browser**, with
the browser editor and **GitHub Copilot CLI in the remote terminal**. Nothing
needs installing on participant laptops. Spark and semantic-link code run
**in Fabric**, never in the Codespace.

## Start here

1. Follow [browser onboarding](docs/codespaces.md) and complete the
   [approved-environment record](templates/approved-environment.md).
2. Complete [discovery and dictionary verification](labs/01-discovery/README.md).
3. Build [trusted curation and a model](labs/02-curation-model/README.md).
4. [Investigate and repair monthly reporting](labs/03-reporting/README.md).
5. Apply the read-only method to **one approved domain/report**, recording
   [customer application evidence](templates/customer-application.md).

Facilitators: [runbook and timed agenda](docs/facilitator/runbook.md),
[expected results](docs/facilitator/expected-results.md),
[preparation trail](docs/preparation-trail.md).

## Reproducible offline path

In the Codespaces terminal (after the devcontainer setup completes):

```bash
make gates
make offline
make report.fault
make report.check       # expected nonzero: repeated monthly totals
make report.plan        # review results/repair-plan.json; copy its SHA256
# After independently reviewing the one-relationship diff:
make report.repair APPROVE_PLAN=<reviewed-sha256>
make report.check       # all 30 production months and the total must match
```

`make offline` reads only committed synthetic fixtures and writes ignored local
evidence. It does **not** call GitHub Copilot, authenticate, provision, or contact
Fabric. The fault is an explicitly labeled, narrow **offline Date-filter
simulator**, not a general DAX engine. The optional live path uses the same
source/month acceptance criteria and an actual DAX query.

## Architecture and contracts

| Contract or boundary | Purpose |
|---|---|
| [demo.yaml](demo.yaml) | Client-agnostic, offline-safe defaults; no tenant or workspace selected |
| [data-model](data-model/README.md) | Typed source dictionary, grain, relationships, rules and SME questions |
| [data/landing](data/landing) | 13 fictional K-Corp CSVs: 12,279 raw rows; optional synthetic PDFs |
| [workshop](workshop) | Strict config, observation, Python reference curation, independent SQL oracle, guarded live adapter |
| [notebook sources](tools/notebooks/src) | Reviewable percent-format source; [generated notebooks](notebooks) execute in Fabric |
| [queries](queries) | Independent source SQL and core-only DAX checks |
| `results/`, `.state/` | Ignored evidence, snapshots, reviewed plans and created item IDs |

This is a **13-table teaching exercise**, not a claim to govern a 200+ table
estate. Eight dimensions and four facts form the core model: **12 model tables,
18 relationships, 14 measures**. Gold also contains the SQL checkpoint
`agg_plant_month`. The illustrative anomaly table is bronze-only.
Utility extraction is a [separate appendix](docs/appendix-utilities.md);
core tables, DAX and reporting never depend on it.

The learning loop is: **outcome -> context -> investigate -> evidence and
proposed plan -> approve scoped changes -> execute with tools -> independently
verify -> iterate**. Evidence does not establish business or clinical meaning;
definitions require an SME. Nothing here diagnoses a real customer's report.

## Access, costs and readiness

You need repository access, an organization-approved GitHub Copilot entitlement
with CLI access, and Codespaces access/budget. **These do not grant Fabric
capacity, Fabric/Power BI licenses, data access, or native Copilot entitlement.**
The offline path needs no Fabric account. For optional Fabric work, an owner
pre-stages an approved, isolated sandbox on an existing supported capacity.
See the [least-privilege action matrix and live commands](docs/live-fabric.md).

**An authorized execution-host rehearsal has passed all four core Fabric data
notebooks, all 14 actual model measures and all 30 source-to-DAX month checks.**
A controlled live Date-relationship fault was reproduced and repaired, with
the synthetic model restored healthy.
This is **not** Codespaces-to-Fabric acceptance: the linked automation credential
lacks Codespaces permission, and devcontainer boot, Copilot CLI connectivity
from Codespaces, browser/customer-device Conditional Access and measured group
concurrency remain pending. No customer data was used. The
[preparation trail](docs/preparation-trail.md) records the distinct gates.

Use [AGENTS.md](AGENTS.md) as the safety contract. Copy `demo.yaml` to ignored
`demo.local.yaml` only after environment approval; overrides are complete files,
not implicit merges. Keep customer records, metadata exports, credentials,
screenshots and logs out of Git.

## Reuse and rights

This workshop adapts an owner-supplied synthetic workshop baseline, preserving
its deterministic K-Corp seeder, notebook source/build approach and acceptance
counts. K-Corp and all examples are fictional. Person-like plant labels have
been replaced with explicit fictional roles and notification addresses use
`example.invalid`. Provenance and reuse boundaries are in
[ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md). See [LICENSE](LICENSE) for content rights;
product subscriptions and third-party dependency licenses are separate.

Canonical repository:
[stellistic/fabric-ghcp-codespaces-workshop](https://github.com/stellistic/fabric-ghcp-codespaces-workshop).
