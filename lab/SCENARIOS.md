# Controlled fault scenarios

Use only the isolated `ai-sre-lab` namespace. Activate one fault at a time, allow
the deployment/endpoints to settle, and run a fresh investigator Pod. The commands
below are human-operated lab controls, never agent tools. Reset between cases.

## 1. Incorrect dependency hostname - evaluated with the agent

```bash
kubectl -n ai-sre-lab set env deployment/orders INVENTORY_URL=http://inventory-typo:8080/stock
kubectl -n ai-sre-lab rollout status deployment/orders --timeout=120s
```

Expected: orders stays Ready, but checkout returns503 and orders logs show a
dependency DNS lookup failure. This is an incorrect application hostname, not
a failure of the cluster's DNS infrastructure.

## 2. Service selector mismatch

```bash
kubectl -n ai-sre-lab patch service inventory --type=merge -p '{"spec":{"selector":{"app":"inventory-mismatch"}}}'
```

Expected: inventory has no selected endpoints and checkout fails. The Day 1 agent cannot inspect Service configuration. Day 2 can inspect it, but its executor only supports the known URL correction and must not repair this selector fault.

## 3. Incorrect readiness path

```bash
kubectl -n ai-sre-lab patch deployment orders --type=strategic -p '{"spec":{"template":{"spec":{"containers":[{"name":"orders","readinessProbe":{"httpGet":{"path":"/not-ready","port":8080}}}]}}}}'
```

Wait for the replacement pod; the old pod can take30 seconds to terminate.
Expected: orders stays Running but is not Ready, with failed readiness events.
A fourth, combined scenario applies both cases2 and3; resolving one can leave
the other failure active.

## Reset and verify

```bash
kubectl -n ai-sre-lab set env deployment/orders INVENTORY_URL=http://inventory:8080/stock
kubectl -n ai-sre-lab patch service inventory --type=merge -p '{"spec":{"selector":{"app":"inventory"}}}'
kubectl -n ai-sre-lab patch deployment orders --type=strategic -p '{"spec":{"template":{"spec":{"containers":[{"name":"orders","readinessProbe":{"httpGet":{"path":"/readyz","port":8080}}}]}}}}'
kubectl -n ai-sre-lab rollout status deployment/orders --timeout=120s
kubectl -n ai-sre-lab logs deployment/traffic --tail=10 --timestamps
```

Check that new traffic samples consistently show status200 and `order-confirmed`.
Readiness alone is not recovery evidence. To probe directly, run
`kubectl -n ai-sre-lab port-forward service/orders 8080:8080` and, from another
terminal on that same machine, request `http://127.0.0.1:8080/checkout` repeatedly.

## Attribution

These synthetic exercises adapt documented Kubernetes mechanisms, not named
production outages:

- [DNS debugging](https://kubernetes.io/docs/tasks/administer-cluster/dns-debugging-resolution/)
- [Service debugging](https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/)
- [Readiness probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)

All four fault/recovery paths were checked in the lab. Only the hostname fault
has a recorded incident-agent evaluation in this repository.
