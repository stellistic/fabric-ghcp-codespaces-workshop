# GitHub Copilot Workshop

The authoritative rules are [AGENTS.md](../AGENTS.md). Read them before edits.
Configuration is [demo.yaml](../demo.yaml); source grain/keys/semantics and approved
quality decisions are [data-model/dictionary.json](../data-model/dictionary.json);
the core semantic contract is [data-model/model.json](../data-model/model.json).
Do not treat the deliberately imperfect vendor dictionary as canonical.

Use named Make targets. Prefer verified Fabric CLI -> REST -> T-SQL. Local gates
must never call live services. Scripts are noninteractive and fail closed;
authentication and write approval are separate deliberate actions. Produce
executable code and focused tests, not pseudocode. Preserve original definitions,
review scoped diffs and reject drift before live writes. Never widen permissions,
alter tenant settings, or create/resize capacity. Distinguish GitHub Copilot from
optional Fabric-native Copilot and AI Functions.

Report evidence and SME questions separately from hypotheses. Run `make gates`.
Clearly label completed offline work, pending live acceptance and human approval.
