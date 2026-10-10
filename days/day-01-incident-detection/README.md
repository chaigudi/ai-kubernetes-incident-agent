# Day 1 — Find an incident using AI

**Completed: October 4, 2026.** Goal: give a model bounded, read-only tools to investigate a failing checkout.

## What happens

1. Python authenticates to Kubernetes as `ai-agent/incident-agent`.
2. The model chooses tools to list pods, read recent logs and inspect events.
3. Python validates the request and runs it only in `ai-sre-lab`.
4. The model returns evidence, a likely cause, missing information and suggested checks.

The model does not run shell commands or repair anything. The service account is an identity; the Python program is the agent.

## Files

- `incident_agent.py`: three diagnostic tools and the bounded model loop.
- `deploy/rbac.yaml`: the read-only ServiceAccount, Role and binding.
- `deploy/agent.yaml`: embedded code and a one-shot investigator Pod.
- `tests/test_guardrails.py`: checks namespace, input and execution limits.

## Run it

First complete [shared setup](../../docs/SETUP.md), including the demo workloads and API-key Secret. Run these commands from the repository root:

```bash
kubectl apply -f days/day-01-incident-detection/deploy/rbac.yaml
kubectl apply -f days/day-01-incident-detection/deploy/agent.yaml
kubectl logs -f incident-investigator -n ai-agent --pod-running-timeout=180s
```

If the container is still creating, retry the logs command. If an old investigator Pod already exists, save its logs and delete it before applying the manifest. Applying an unchanged manifest does not rerun a completed Pod.

## Reproduce the incident

```bash
kubectl set env deployment/orders -n ai-sre-lab INVENTORY_URL=http://inventory-typo:8080/stock
kubectl rollout status deployment/orders -n ai-sre-lab --timeout=120s
kubectl delete pod incident-investigator -n ai-agent --ignore-not-found
kubectl apply -f days/day-01-incident-detection/deploy/agent.yaml
kubectl logs -f incident-investigator -n ai-agent --pod-running-timeout=180s
```

Expected: pods can remain Ready while checkout returns 503. Orders logs show a failed lookup for the incorrect dependency hostname. The agent should identify that evidence without claiming it inspected configuration that it cannot access.

Restore the lab manually:

```bash
kubectl set env deployment/orders -n ai-sre-lab INVENTORY_URL=http://inventory:8080/stock
kubectl rollout status deployment/orders -n ai-sre-lab --timeout=120s
kubectl logs deployment/traffic -n ai-sre-lab --since=30s --timestamps
```

Confirm fresh successful checkout responses after the correction. Historical 503s may remain in the log window.

## Result and limitations

The recorded fault investigation used three model requests, five tool calls and 10,426 tokens in 11.02 seconds, with zero mutations. This is investigation-loop time, not MTTR. See [results](../../docs/RESULTS.md).

This snapshot preserves the original implementation. It has no configuration inspection or remediation, and its SDK log decoding was improved in Day 2. It caps four model requests and six tool calls. It is not a production deployment.

```bash
pip install -r requirements.txt
python -m unittest discover -s days/day-01-incident-detection/tests -v
```

Next: [Day 2 — approve and verify a repair](../day-02-approved-remediation/README.md).
