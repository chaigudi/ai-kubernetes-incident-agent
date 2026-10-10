# AI Kubernetes Incident Agent

A hands-on series: investigate a Kubernetes incident with AI, then repair one supported fault with human approval and a separate executor.

| Day | Built and tested | Start here |
| --- | --- | --- |
| 1 - October 4, 2026 | Read-only investigation using pod status, logs and events | [Incident detection](days/day-01-incident-detection/README.md) |
| 2 - October 6, 2026 | Configuration evidence, guarded proposals, approval and verified remediation | [Approved remediation](days/day-02-approved-remediation/README.md) |
| Next - planned | MCP tools, metrics and alert-driven investigation | [Roadmap](roadmap/README.md) |

Day numbers represent project milestones, not consecutive calendar dates. Each completed day has its own runnable code and manifests. Deploy one day at a time: both use the same lab resource names.

```text
AI investigator (read-only) -> proposed fix -> human approval
                                                    |
                                                    v
                                  separate executor -> recovery checks
```

The lab uses Python, Kubernetes on AWS EC2, and KodeKloud's OpenAI-compatible model API. The demo checkout calls an inventory service; synthetic traffic makes failures visible even while pods remain Ready.

## Start

Follow [shared setup](docs/SETUP.md), then choose a day above. For the latest workflow, use Day 2. See [measured results](docs/RESULTS.md) and [cleanup](docs/CLEANUP.md).

```text
days/day-01-incident-detection/   Original read-only milestone
days/day-02-approved-remediation/ Investigator, approval launcher and executor
lab/                            Shared applications, bootstrap and fault scenarios
scripts/                        Manifest generation
docs/                           Setup, results, design and teardown
roadmap/                        Future work, explicitly not implemented
```

## Important boundaries

The investigator cannot patch workloads, execute in pods, or read Secrets through the Kubernetes API. Its model key is mounted separately. The executor has get/patch access to only the orders Deployment and no model key. It validates the fixed operation, expiry and Deployment version before writing.

RBAC does not restrict individual Deployment fields: the URL-only restriction is implemented in Python. No admission policy or network egress policy is installed. Terminal approval and local audit records are lab controls, not tamper-proof authorization.

This is a reproducible lab, not a hosted service. This repository contains code and sanitized results, not running infrastructure or credentials. Lab scenarios were set up with AI assistance.
