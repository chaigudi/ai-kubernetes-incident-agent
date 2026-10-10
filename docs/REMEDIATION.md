# Human-approved remediation

The investigator remains read-only. `propose_inventory_url_fix` takes no arguments;
the model cannot supply a namespace, replacement URL, patch, or approval.

- The baseline URL returns `no_change_needed` (other failures can still exist).
- The known inventory-typo URL requires ready inventory endpoints, expected Service
  configuration, a matching running orders pod, and two latest checkout log entries
  within 60 seconds showing 503s against that URL.
- Unknown, incomplete, stale, or changing evidence returns `manual_review`.

A proposal records the exact before/after values, Deployment UID/resourceVersion,
evidence timestamps, creation/expiry times, and required recovery checks. The
executor enforces the five-minute expiry before submitting the real patch. The SHA-256 plan
ID is a content digest, not a signature or approval. Logs remain untrusted evidence;
these checks do not protect against a compromised application forging observations.

## Run the workflow

Follow [shared setup](SETUP.md), apply `days/day-02-approved-remediation/deploy/remediator-rbac.yaml` from the repository root, then change directory to `days/day-02-approved-remediation`. Run the launcher only from your trusted operator terminal with the intended lab kubeconfig.

```bash
python3 remediation.py investigate
python3 remediation.py preview
python3 remediation.py approve
```

`investigate` replaces the completed investigator Pod, archives its logs, and
exports a validated proposal to `plan.json`. No plan is exported for healthy or
unsupported cases. `preview` runs a server-side dry run as the executor identity.
`approve` displays the exact change and requires typing `APPROVE <full-plan-id>`.
It creates a separate one-shot Job as `ai-agent/incident-remediator`, with no LLM
credential. Its code and plan are snapshotted into an immutable ConfigMap. The
executor repeats validation and dry run, uses atomic JSON Patch tests for UID,
resourceVersion and prior value, and replaces only the supported URL value.

After applying, the Job checks rollout and requires six consecutive successful
checkout probes, spaced two seconds apart. Verification failure stops for manual
review. It never automatically restores the known-bad URL or retries a mutation.
A network error can leave an unknown outcome; inspect current state before retrying.

If the plan expires or the Deployment changes, run `investigate` again and review
the new proposal. Do not extend timestamps or manually edit the saved plan.
The existing `incident-agent` remains read-only. Its loop allows four model requests
and eight tool calls. Only the executor identity receives named-object patch access.

## Trust boundaries and limits

Approval is an operator-terminal gate: the investigator cannot create executor
Jobs or approval ConfigMaps. A plan hash detects accidental modification, but is
not a signature and does not authenticate a person. Someone with operator/admin
credentials can bypass the launcher. The audit records the local OS username,
not a verified human identity.

RBAC restricts the executor to the named orders Deployment, but cannot restrict
individual fields. The program enforces the URL-only change. No admission policy
has been installed; a compromised executor could patch other fields on orders.
Logs are untrusted evidence, and endpoint readiness is not an application probe.
This is a training implementation, not a production security boundary.

Audit reports and approval records are saved under `remediation-audit/` and excluded
from Git. Jobs expire after one day; their immutable ConfigMaps remain for audit.
List retained bundles with `kubectl get configmaps -n ai-agent`; remove only named
`incident-remediation-*` bundles after retaining any audit evidence you need.
No external services or additional EC2 instances are provisioned.

## Validation scope

Twenty-three local tests cover expired/tampered plans, unsupported operations,
missing approval, stale resource identity, atomic patch construction, dry-run-only
behavior, no mutation retries, and consecutive recovery probes. The live investigation and executor preview passed with zero changes; checkout
remained at 503. The subsequent human-approved executor audit confirmed one mutation and six successful checkout probes; see [recorded results](RESULTS.md).

## Lab validation (2026-10-06)

Twelve local guardrail tests passed. The live healthy case returned
`no_change_needed`; the known URL fault returned `proposed` with two recent
checkout 503 observations. The fault run used four model requests, seven tool
calls, and 29,189 tokens in 16.65 seconds of the investigation loop. The agent
made zero changes. Administrative lab controls restored the baseline; six consecutive
checkout checks passed afterward. This is a controlled lab result, not autonomous
remediation or an accuracy benchmark.
