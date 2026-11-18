# Optional appendix: extraction is not correctness

The core workshop needs **neither** Fabric-native Copilot **nor** AI Functions.
The 48 fictional utility-bill PDFs and extraction-comparison lesson are optional,
after the core exit criteria. The original AI extraction notebook is deliberately
not shipped as an executable core asset. Native AI features have separate tenant settings, permissions,
region/capacity availability and entitlements. Their use requires explicit
organizational approval; do not change tenant settings to enable an exercise.

The inherited synthetic PDF set has 35 digital and 13 scanned documents, across
four fictional plants and six billing months. Approved inputs and two reference
CSVs live under [data/landing](../data/landing). The catch-up extraction is a
synthetic example of model output, **not ground truth**; compare it to
`utility_bills_ground_truth.csv` independently. An extraction confidence score
does not prove an invoice amount, unit or billing period is correct.

Inspect one bill and compare the extracted amount, unit and billing period
against the reference CSVs. Keep OCR/model confidence separate from correctness;
record mismatches and questions rather than silently accepting a plausible value.
Any separately approved AI extraction experiment belongs in an isolated
synthetic environment, not this kit's default execution path. The **core model
remains unchanged**. This kit does
not automatically add utility relationships or measures to 07, core DAX or the
monthly reporting lab. Design and review an optional extension as a separate
exercise only after its table/quality checks pass.

Optional report-generation task brief:

```text
Design (do not publish) a report using only the verified synthetic core model.
Use YearMonth and Actual Units for a monthly visual, show the approved scrap and
attainment definitions, and identify filters and unknown members. Reconcile
every production month to the independent source SQL before claiming correctness.
Do not require utilities, native Copilot or a Windows Desktop MCP.
```

Fabric/Power BI Copilot may optionally help draft report content if the tenant
already permits it; it is **not GitHub Copilot**, and the draft still needs
independent verification. Never run the inherited DELETE demonstration or inject
a fault into a real customer model. No destructive report demonstration is part
of this workshop.
