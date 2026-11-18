# One-domain/report application worksheet

Fill only in ignored `results/` or the approved document system. No actual
customer data or identifiers belong in the tracked repository.

| Field | Record |
|---|---|
| Objective and domain/report | One bounded, approved business question and owner role |
| Status | Pending / approved read-only / synthetic fallback (real objective incomplete) / independently verified |
| Allowed context | Specific metadata artifacts, schemas, tables and permitted samples; excluded data |
| Grain and scope | Fact grain, dimension keys, time/calendar/timezone and covered date interval |
| Measures | Approved definitions, denominators, null/unknown handling, revenue/late semantics |
| Observations | Actual schema/key/null/duplicate/orphan evidence with query and source version |
| Hypotheses | Plausible explanations, explicitly not yet established causes |
| Rejected relationships | Cardinality/coverage failure and proposed remediation for review only |
| Proposed next change | Exact sandbox scope, diff, expected impact and rollback; no production writes |
| Approval | Read approval reference; any write needs a distinct authorization |
| Independent verification | Source monthly SQL versus actual DAX with identical filters; exact counts, defined rate/currency tolerance |
| Coverage limits | Tables/months not assessed, 200+ table estate not implied complete |
| SME questions | Ambiguous definitions and responsible decision role; no invented clinical meaning |
| Exit evidence | Reproducible checks, residual blockers and whether real-environment objective remains incomplete |

Do not use the K-Corp totals as the oracle for a real domain. Do not copy
customer records into Copilot or the repository merely because it is private.
