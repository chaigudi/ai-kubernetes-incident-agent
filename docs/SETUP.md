# Setup

Use a disposable Kubernetes cluster with outbound HTTPS access. The original lab
used one EC2 t3.large, Amazon Linux 2023, and K3s. This repository does not provision
AWS resources or include account-specific infrastructure state.

## Optional EC2 bootstrap

Create a dedicated EC2 instance with an SSM instance profile and no inbound ports.
Use Session Manager for access. On a fresh Amazon Linux 2023 lab host, review and
run `sudo bash lab/bootstrap-ec2.sh`. It installs the K3s stable channel and starts
an eight-hour shutdown timer. Configure EC2's instance-initiated shutdown behavior
to **stop**. Stopped instances still incur storage charges; terminate the lab when
finished. Bootstrap needs outbound access to package repositories and K3s downloads.

The original cluster reported K3s v1.36.5+k3s1. The stable channel and container
base tags can change; the scripts do not guarantee an identical future runtime.

## Deploy the application and agent identity

Run from the repository root with kubectl targeting your disposable cluster:

```bash
kubectl apply -f lab/demo.yaml
kubectl wait --for=condition=Available deployment --all -n ai-sre-lab --timeout=180s
kubectl apply -f deploy/rbac.yaml
```

The RoleBinding in `ai-sre-lab` grants read access to the `incident-agent`
ServiceAccount in `ai-agent`. The agent has no Secret-read, Pod-exec, or workload
write permissions. Its preflight checks use its actual in-cluster identity.

## Supply the API credential

Run in Bash. Enter the key in the hidden prompt, not in source code:

```bash
read -rsp 'KodeKey API key: ' KODEKEY_API_KEY
echo
printf '%s' "$KODEKEY_API_KEY" |
  kubectl -n ai-agent create secret generic kodekey --from-file=api-key=/dev/stdin
unset KODEKEY_API_KEY
```

The Pod mounts that specific Secret. The agent process can read its mounted key,
but cannot retrieve Secrets through the Kubernetes API. The key never belongs
in model messages, source control, or screenshots.

## Run an investigation

Set `MODEL` and `INCIDENT` in `deploy/agent.yaml` to a model your KodeKey plan
supports and the symptom you want investigated. The tested model was `gpt-6-luna`.
For a healthy baseline, use: `Check whether checkout appears healthy. Inspect
recent application logs and events.`

```bash
kubectl apply -f deploy/agent.yaml
kubectl logs -f incident-investigator -n ai-agent --pod-running-timeout=120s
```

Each Pod runs once. To investigate again, save its current report and recreate it:

```bash
mkdir -p reports
kubectl logs incident-investigator -n ai-agent > reports/latest.txt
kubectl delete pod incident-investigator -n ai-agent
kubectl apply -f deploy/agent.yaml
kubectl logs -f incident-investigator -n ai-agent --pod-running-timeout=120s
```

Check evidence timestamps. Applying an unchanged manifest does not rerun a
completed Pod. Earlier errors may remain in the five-minute log window after repair.

## Modify and test

Edit `incident_agent.py`, run the tests, then run `python scripts/render.py` to
refresh the source embedded in the deployment ConfigMap. Recreate the agent Pod
to run the changed version. App source changes similarly require rendering and
restarting the affected demo deployments.

The loop caps model requests at 4, tool attempts at 6, completion tokens at 1200
per request, and serialized input at 60,000 characters. It checks a 180-second
deadline between operations; the Pod has a 360-second active deadline including
startup. SDK retries are disabled. These are resource bounds, not a dollar cap.

Logs are limited to 50 recent lines, 12,000 bytes fetched, and 8,000 characters
returned. The agent can only read logs for pods in its latest namespace listing.
Events are bounded and filtered to a recent window. Pagination/truncation is
reported. This version cannot inspect Service selectors or deployment settings.

Dependencies are installed at startup for simplicity. For a production design,
build an image, pin digests, enforce egress policy, add broader credential/PII
redaction, and evaluate prompt-injection and failure handling. A system prompt
alone does not guarantee prompt-injection resistance.

## Cleanup

After exporting anything needed from this disposable lab:

```bash
kubectl delete -f deploy/agent.yaml --ignore-not-found
kubectl delete namespace ai-agent ai-sre-lab
```

This removes all resources in both lab namespaces, including the API-key Secret.
If using EC2, stop or terminate the dedicated instance separately; confirm that
attached storage and any other billable resources are cleaned up.
