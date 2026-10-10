# Planned next installments

These features are ideas for continuing the series. They are not implemented or claimed as completed.

| Suggested installment | Build | Demonstrate |
| --- | --- | --- |
| Day 3 | Read-only MCP server plus bounded Prometheus tools | Correlate logs, configuration and measured error rates |
| Day 4 | Alertmanager-triggered investigations | Deduplicate alerts and bound concurrent jobs/model spend |
| Day 5 | Cluster-enforced admission guardrails | Reject prohibited changes even if executor code tries them |
| Day 6 | Repeatable evaluations and agent telemetry | Test misleading evidence, stale plans and model regressions |
| Day 7 | GitOps remediation | Reviewed configuration PR followed by deployment and recovery checks |

The first proposed step is to expose existing diagnostic functions through MCP while retaining read-only access and the separate approval/executor path. MCP standardizes tool access; it does not replace RBAC or human authorization.

Useful primary references:

- [MCP architecture](https://modelcontextprotocol.io/docs/learn/architecture)
- [Grafana MCP](https://github.com/grafana/mcp-grafana)
- [Prometheus Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/)
- [Kubernetes admission policies](https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/)
- [GitHub MCP](https://github.com/github/github-mcp-server)
