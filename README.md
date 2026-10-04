# AI Kubernetes Incident Agent

A read-only incident investigator built with Python, Kubernetes RBAC, and an LLM
through KodeKloud's OpenAI-compatible API. Tested on Kubernetes running on AWS EC2.

The agent chooses tools to inspect pod status, bounded logs, and recent events,
then reports observations, likely causes, missing evidence, and recovery checks.

**Guardrails:** namespace-scoped access, mounted API-key Secret, validated tool
arguments, non-root container, resource limits, and a maximum of four model
requests and six tool calls. No remediation tools or cluster write permissions.

**Lab result:** identified an incorrect dependency hostname behind checkout 503s
while all application pods were Running and Ready. The run used three model
requests, five tool calls, and 10,426 tokens in 11.02 seconds. After correction,
six consecutive checkout checks passed. Investigation time is not MTTR.

## Run it

Follow [setup](docs/SETUP.md), try the [fault scenarios](lab/SCENARIOS.md), and
review the [measured result](docs/RESULTS.md).

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

This is a learning lab; egress restrictions and production hardening remain future
work. Lab scenarios were set up with AI assistance.
