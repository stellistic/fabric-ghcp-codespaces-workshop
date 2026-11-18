# GitHub Copilot Workshop — browser-first Codespaces

Canonical repository: **[stellistic/fabric-ghcp-codespaces-workshop](https://github.com/stellistic/fabric-ghcp-codespaces-workshop)**
(private). Participants need repository access; do not make a client-data fork public.
The workshop title is **GitHub Copilot Workshop**.

**LIVE POC: PENDING. Group rehearsal: PENDING.** Container settings, CLI help and
offline adapters are not evidence that organization policy, Conditional Access,
browser callbacks, encrypted keyrings, network routing or Fabric capacity work for
your participants. Rehearse with an explicitly approved disposable sandbox first.
No live login/resource calls were authorized or performed in the original
offline delivery.

The later authorized **execution-host-to-Fabric** rehearsal is recorded separately
in the [preparation trail](preparation-trail.md); it does not change this
Codespaces readiness status.

## What participants need

Only a current web browser: open the private repository, select **Code → Codespaces
→ Create codespace**, and remain in VS Code for the Web. All commands below run in
the **remote Codespace terminal**, never on a participant's laptop. No local Python,
Node, Docker, Windows, Power BI Desktop or desktop MCP installation is mandatory.
Fabric notebook editing/monitoring happens in the Fabric web portal.

The organizer confirms these **separate entitlements/costs**:

| Service | Check before the session |
|---|---|
| GitHub Copilot | Eligible account/plan or organizational seat, permitted CLI usage and applicable AI policies/usage limits |
| GitHub Codespaces | Access to the private repository, creation policy, organization/personal compute and storage budget |
| Microsoft Fabric | Correct Entra tenant, existing sandbox workspace/Lakehouse on supported Fabric capacity, item permissions and applicable Fabric/Power BI licenses |

Paying for Copilot does not provide Codespaces compute or Fabric capacity. This
core workshop uses GitHub Copilot as the coding assistant; native Fabric Copilot
and AI Functions are optional/out of scope and are **not prerequisites**.

## Reproducible, credential-free setup

The devcontainer pins Python **3.12 Bookworm** to versioned image
`3.3.3-3.12-bookworm` plus its verified multi-architecture digest, Node **22.23.5**,
uv **0.12.5**, isolated Fabric CLI **1.7.0**, and the local npm Copilot CLI
**1.0.114** (resolved from the public npm registry; `package-lock.json` committed).
The Fabric tool environment includes pinned PyGObject **3.50.0** for Bookworm's
libsecret/GLib integration, separate from the workshop's `.venv`.

Post-create runs `uv sync --frozen`, then `npm ci --ignore-scripts` against the
public registry, secure local Fabric settings, version/help checks. It does **not**
login, read auth status, list resources, copy credentials, or execute notebooks.
The Docker build context is `.devcontainer` only, not the repository's local
configuration/state. No host credential mounts or baked tokens are configured.
Review lifecycle scripts before trusting a repository.

If dependency downloads fail, inspect Codespaces/network policy; do not bypass TLS,
change lockfiles blindly or paste access tokens. After an interrupted setup:

```bash
bash .devcontainer/post-create.sh
uv run --frozen python -m pytest tests/test_live.py --basetemp=.state/pytest-live
```

Keep CLI debug logging disabled. Fabric encrypted-cache fallback is explicitly
**false**; the setup never disables keyring/encryption.

### Organizer automation permission gate

Creating a Codespace in the GitHub browser and managing one through a linked
automation credential are separate authorization paths. In this implementation's
attempted automated rehearsal, repository/machine discovery worked, but the
linked credential's Codespaces listing was denied for missing `codespace` scope;
no Codespace was created or billed. This is not evidence that a participant's
normal browser creation flow is blocked.

For a CLI-managed OAuth login, use GitHub's documented consent flow
`gh auth refresh -h github.com -s codespace` and approve it as the intended
account. An app-injected `GH_TOKEN` takes precedence over stored CLI logins:
refreshing a different keyring account will not amend that credential. Request
the host's supported linked-account permission refresh; do not unset/substitute
tokens, switch identities, transplant caches or retry a denied API until
authorization has actually changed.

## GitHub Copilot login and workspace trust

In the remote terminal:

```bash
npm run copilot
```

Inside Copilot, enter `/login` and follow the browser instructions for your GitHub
account. Authenticate as yourself, confirm the repository's trust prompt only after
reviewing it, and keep tool/write approvals enabled. Do not use blanket
allow-all permissions for workshop convenience.

Try: “Explain the synthetic manufacturing data pipeline and propose offline
tests. Do not authenticate, access Fabric or execute live commands.” Review changes
and run offline tests before considering any live action. Copilot trust/login is
not Fabric authorization; it does not approve any cloud write.

## Fabric login: explicit tenant, encrypted cache

Login is a **manual opt-in**, separate from post-create and offline tests. Obtain
the selected tenant UUID and sandbox identifiers from the organizer. Never copy a
host `~/.azure`, Fabric MSAL cache, GitHub token or service-principal secret into the
Codespace.

Start a private D-Bus/encrypted-keyring shell:

```bash
bash .devcontainer/fabric-terminal.sh
```

Choose a nonempty keyring password (or unlock your existing keyring); this is not
an access token. The helper reads it without echo, passes it through stdin to
GNOME Keyring and unsets it. It does not save/export the password or perform login.
Run all subsequent Fabric commands in this same shell. A new remote terminal does
not inherit that session bus. Keep the password out of prompts/chat/screenshots.

Then use the flow verified in installed 1.7.0 help/source:

```bash
fab auth login --tenant YOUR_EXACT_TENANT_UUID
```

Select **Interactive with a web browser**, complete the supplied browser flow as
the intended Entra user, and verify the account/tenant in the browser. The CLI
supports `--tenant`; no unverified `--device-code`, `--use-device-code` or
`--azure-cli` flag is prescribed for this pinned version. Follow Codespaces'
private port/browser forwarding prompts if presented; never expose authentication
callback ports publicly.

**Rehearsal gate:** this CLI uses MSAL interactive/loopback authentication, whose
callback may be blocked in a browser-only Codespace or by Conditional Access.
The exact browser forwarding and secret-service behavior must pass the live POC.
If the encrypted cache cannot initialize/unlock, browser callback cannot complete,
or policy requires a managed/compliant device, stop the live exercise and use the
offline path. Do not switch to plaintext caches, transplant tokens, capture/copy
callback authorization codes, or invent an unsupported login flag to force it.
Escalate to the organizer/tenant administrator for an approved supported flow.

Configure the complete ignored `demo.local.yaml`, then explicitly opt into the
read checks in [live-fabric.md](live-fabric.md):

```bash
uv run --frozen python -m workshop.live --config demo.local.yaml preflight
uv run --frozen python -m workshop.live --config demo.local.yaml inventory
```

Do not invoke these with the shipped defaults and expect access: defaults are
deliberately denied before starting `fab`. Live writes need sandbox configuration
**and** the separate exact-workspace approval flag documented there.

## Cross-tenant/cache and teardown warnings

Fabric and GitHub identities are independent. Shared browsers can retain accounts,
and CLI caches can outlive a terminal or Codespace stop. Never infer the active
tenant from a workspace name or from a successful GitHub login. The adapter checks
auth tenant plus workspace UUID/name and Lakehouse membership on every action.
For a tenant switch, finish/reconcile pending work, **log out**, log in with the new
explicit tenant and rerun preflight; do not reuse another participant's state.

At the end:

1. Follow the exact-ID manual notebook/job cleanup in [live-fabric.md](live-fabric.md).
   Stop Spark sessions; deleting a Codespace does not stop Fabric compute.
2. In the encrypted-keyring shell run `fab auth logout`, then close that shell.
   In Copilot use `/logout`, then exit. Log out of relevant browser accounts.
3. Never save tokens/auth codes/cache files in workshop evidence or shell history.
   Keep local `.state/` and `results/` private; retain only policy-approved sanitized
   evidence. Stopping a Codespace preserves its disk and credential caches.
4. Stop/delete your Codespace through GitHub when appropriate, and check remaining
   Codespaces storage/compute and Fabric capacity costs with the organizer.

## Official references

- [Copilot CLI quickstart: Node 22+, terminal, `/login` and trust](https://docs.github.com/en/copilot/get-started/cli-quickstart)
- [Using Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/overview)
- [Creating a Codespace](https://docs.github.com/en/codespaces/developing-in-a-codespace/creating-a-codespace-for-a-repository)
- [Codespaces billing](https://docs.github.com/en/billing/concepts/product-billing/github-codespaces)
- [Fabric CLI](https://microsoft.github.io/fabric-cli/) / [authentication](https://microsoft.github.io/fabric-cli/examples/auth_examples/)
- [MSAL encrypted token cache on Linux](https://github.com/AzureAD/microsoft-authentication-extensions-for-python/wiki/Encryption-on-Linux)
