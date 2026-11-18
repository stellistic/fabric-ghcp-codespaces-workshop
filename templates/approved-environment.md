# Approved environment record

Copy this template into an **ignored results directory or approved document
system**, never fill customer details into the tracked template.

| Decision | Approved value / evidence |
|---|---|
| Status | Pending / offline only / one-user live POC / group rehearsed |
| Account and tenant | Approved role identifier and tenant UUID; never a token |
| Data handling | Synthetic only or allowlisted read-only metadata; security approval reference |
| Copilot | GitHub Copilot CLI entitlement and organization AI policy approval |
| Codespaces | Browser access, policy/budget, network/CA POC evidence, tested image/tool versions |
| Fabric/Power BI | Required licenses, existing capacity selected by owner, no resize/create authorization |
| Workspace | Exact UUID and expected name; owner confirms isolated synthetic sandbox |
| Lakehouse/model | Exact UUIDs; each pair/person has a non-overlapping approved target |
| Read approval | Allowed metadata endpoints/schemas/report and read permissions |
| Write approval | Separate scoped action, exact item(s), reviewed diff/hash, approver role, expiry |
| Concurrency | Measured safe Spark concurrency, cold starts, queues, duration and throttling |
| Rollback/cleanup | Captured original, exact owned IDs, stop condition and cleanup owner |
| Signoff | Required platform/security/identity/data/SME roles; dated approval references outside Git |

Default remains **no live access approved**. Authorization for materials is not
authorization to authenticate, read customer data, deploy or spend capacity.
