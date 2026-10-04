# Recorded lab result

The injected fault changed the orders dependency URL to a nonexistent inventory
hostname. Checkout returned503 while all application pods remained Running/Ready.

The investigator identified the failed DNS lookup from orders logs and confirmed
checkout impact using synthetic traffic logs. It separated an earlier startup
probe event from the ongoing failure, and acknowledged that its tools could not
inspect the configuration or intended Service name.

| Measurement | Observed value |
|---|---:|
| Model | gpt-6-luna through KodeKey |
| Model requests | 3 |
| Diagnostic tool calls | 5 |
| Prompt tokens | 9,636 |
| Completion tokens | 790 |
| Investigation loop | 11.02 seconds |
| Agent mutations | 0 |

The diagnosis matched the injected fault. After the dependency URL was restored,
six consecutive checkout checks returned200 with `order-confirmed`.

The loop duration excludes Pod startup, dependency installation, human review,
and repair. It is not MTTR. This is one controlled incident, not a general
accuracy benchmark. Self-reported confidence is not calibrated probability.

Five local guardrail tests passed. An in-cluster baseline also passed allowed
pod reads and denied Secret-read, deployment-patch, Pod-exec, and kube-system
access checks. The model has no remediation tools. Network egress restrictions
are not implemented in this version.
