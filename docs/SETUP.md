# Shared setup

Use a disposable Kubernetes cluster with outbound HTTPS. The original lab ran K3s on one EC2 t3.large with Amazon Linux 2023. These files do not provision AWS resources; use your own disposable cluster.

## 1. Prepare Kubernetes

For EC2, use a dedicated host, Session Manager access and an appropriate SSM instance profile. Review `lab/bootstrap-ec2.sh` before running it on a fresh Amazon Linux 2023 host. It installs the K3s stable channel and configures an eight-hour shutdown timer. Set the instance's shutdown behavior to stop.

Stopping still leaves billable storage. Follow [cleanup](CLEANUP.md) when finished. No existing account-wide VPC, IAM or EKS resources should be removed as part of this lab.

The original runtime reported K3s v1.36.5+k3s1. Stable-channel installs and container tags can change, so this is not an exact runtime lockfile.

## 2. Clone and deploy the demo

Run on the operator host with kubectl pointing at the intended lab cluster:

```bash
git clone https://github.com/chaigudi/ai-kubernetes-incident-agent.git
cd ai-kubernetes-incident-agent
kubectl config current-context
kubectl apply -f lab/demo.yaml
kubectl wait --for=condition=Available deployment --all -n ai-sre-lab --timeout=180s
```

The shared application is synthetic: traffic calls orders, and orders calls inventory. Prometheus collects basic metrics. No real customer data is needed.

## 3. Choose a milestone

For the latest workflow:

```bash
kubectl apply -f days/day-02-approved-remediation/deploy/rbac.yaml
```

For the original read-only milestone, use `days/day-01-incident-detection/deploy/rbac.yaml` instead. Both create the `ai-agent` namespace and `incident-agent` identity. The RoleBinding connects that identity to the application namespace. Use one milestone at a time.

If downgrading from Day 2, its additional configuration-reader Role/RoleBinding and executor permissions remain until explicitly deleted; applying Day 1 does not remove additive permissions.

## 4. Create the model Secret

Run in Bash; input stays out of shell history:

```bash
read -rsp 'KodeKey API key: ' KODEKEY_API_KEY
echo
printf '%s' "$KODEKEY_API_KEY" |
  kubectl create secret generic kodekey -n ai-agent --from-file=api-key=/dev/stdin --dry-run=client -o yaml |
  kubectl apply -f -
unset KODEKEY_API_KEY
```

The investigator mounts this key but cannot read Secrets through the Kubernetes API. Never commit the key or paste it into reports. The executor does not need it.

Each day's `deploy/agent.yaml` uses `https://api.ai.kodekloud.com/v1` through the OpenAI-compatible client. The tested model was `gpt-6-luna`; choose a model available to your account by editing `MODEL`. A 401 from the model API is separate from Kubernetes RBAC.

## 5. Follow a day

- [Day 1: investigation](../days/day-01-incident-detection/README.md)
- [Day 2: approved remediation](../days/day-02-approved-remediation/README.md)

Agent Pods run once. The Day 2 launcher archives the old report and recreates the Pod. Startup installs pinned Python dependencies and may take a few minutes. Evidence timestamps matter; old failures can remain in the log window after recovery.

## Develop locally

```bash
python -m venv .venv
# Activate this environment using your shell's activation command.
pip install -r requirements.txt
python -m unittest discover -s days/day-01-incident-detection/tests -v
python -m unittest discover -s days/day-02-approved-remediation/tests -v
python scripts/render.py
```

Edit Python source rather than embedded ConfigMap strings. The render script refreshes both milestone manifests and the shared application. Recreate Pods to load changes. Run milestone tests separately to avoid loading two modules with the same name into one Python process.

Both agents bound requests, log size and execution time. These are not billing guarantees. Production hardening would also require pinned image digests, admission and network controls, broader data redaction, and independent evaluation.
