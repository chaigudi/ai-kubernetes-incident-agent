# Day 2 - Approve a fix and verify recovery

**Completed: October 6, 2026.** Goal: extend the investigator with configuration evidence and a narrowly scoped, human-approved repair.

## What improved

| Day 1 | Day 2 |
| --- | --- |
| Pod status, logs and events | Also reads orders configuration and inventory Service/EndpointSlices |
| Diagnosis only | Fixed remediation proposal with evidence and five-minute expiry |
| No executor | Separate executor identity with get/patch access to orders only |
| Manual repair | Exact plan-ID approval, atomic patch and recovery checks |
| SDK string log decoding | Explicit byte decoding so timestamped lines can be parsed |
| Six tool calls maximum | Eight tool calls maximum; model requests remain capped at four |

## Understand the three programs

- `incident_agent.py`: read-only AI investigator. It cannot execute a repair.
- `remediation.py`: human-operated launcher. It runs investigations, previews and the approval prompt using your operator kubeconfig.
- `remediator.py`: deterministic executor inside a Kubernetes Job. It has no model API key and supports one fixed URL correction.

The supported fix changes orders' explicit `INVENTORY_URL` from `http://inventory-typo:8080/stock` to `http://inventory:8080/stock`. A healthy URL returns `no_change_needed`; unknown configurations require manual review.

## Setup

Complete [shared setup](../../docs/SETUP.md). From the repository root:

```bash
kubectl apply -f days/day-02-approved-remediation/deploy/rbac.yaml
kubectl apply -f days/day-02-approved-remediation/deploy/remediator-rbac.yaml
```

Verify the identity boundary:

```bash
kubectl auth can-i patch deployment/orders -n ai-sre-lab --as=system:serviceaccount:ai-agent:incident-agent
# no
kubectl auth can-i patch deployment/orders -n ai-sre-lab --as=system:serviceaccount:ai-agent:incident-remediator
# yes
kubectl auth can-i patch deployment/inventory -n ai-sre-lab --as=system:serviceaccount:ai-agent:incident-remediator
# no
```

## Run the exercise

Inject only into the disposable demo namespace:

```bash
kubectl set env deployment/orders -n ai-sre-lab INVENTORY_URL=http://inventory-typo:8080/stock
kubectl rollout status deployment/orders -n ai-sre-lab --timeout=120s
cd days/day-02-approved-remediation
```

**1. Investigate**

```bash
python3 remediation.py investigate
```

The launcher runs a fresh investigator, saves the report, and writes `plan.json` if a supported proposal is produced. Review the resource, before/after values, failure evidence and expiry.

**2. Preview**

```bash
python3 remediation.py preview
```

A Job using `incident-remediator` asks Kubernetes to validate the patch with server-side dry run. Expected: `preview_passed` and `mutations: 0`.

**3. Approve the actual change**

```bash
python3 remediation.py approve
```

Type `APPROVE ` followed by the full plan ID displayed. This authorizes a real change. The executor repeats validation, applies the fixed patch once, waits for rollout and requires six consecutive checkout successes.

Expected final fields: `status: recovery_verified`, `mutations: 1`, `successful_probes: 6`.

The plan expires after five minutes. If it expires or the Deployment changes, run `investigate` again. Never edit the timestamps to bypass the check.

## Check the outcome

```bash
kubectl rollout status deployment/orders -n ai-sre-lab --timeout=120s
kubectl logs deployment/traffic -n ai-sre-lab --since=30s --timestamps
```

Check fresh HTTP 200/order-confirmed responses. Approval records and executor logs are under `remediation-audit/`, excluded from Git. If execution stops after a patch may have been submitted, inspect current state before retrying; no automatic rollback is attempted.

## Guardrails and limits

Expiry, plan digest, fixed resource/value checks and atomic UID/resourceVersion tests protect the supported workflow. Jobs have no automatic retries, use a non-root container and do not mount the model credential.

The approval gate is your trusted terminal, not an authenticated web approval service. An administrator can bypass it. RBAC permits patching any field on orders; only the executor code enforces the URL restriction. Admission enforcement, egress restrictions and signed approvals remain future work.

**Observed result:** the saved executor audit confirmed one mutation and six successful probes. [Results](../../docs/RESULTS.md) distinguish this from earlier trainer-operated resets.

From the repository root:

```bash
python -m unittest discover -s days/day-02-approved-remediation/tests -v
```

See [design details](../../docs/REMEDIATION.md), [other fault scenarios](../../lab/SCENARIOS.md) and [cleanup](../../docs/CLEANUP.md).
