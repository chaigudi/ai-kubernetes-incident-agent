# Recorded lab results

These are measurements from a small synthetic lab, not production accuracy benchmarks.

## Day 1 - October 4, 2026

Orders used an incorrect inventory hostname. Pods remained Running and Ready while checkout returned 503. The investigator correlated orders and traffic logs and identified the failed dependency lookup.

| Measurement | Recorded value |
| --- | --- |
| Model requests | 3 |
| Tool calls | 5 |
| Total tokens | 10,426 |
| Investigation loop | 11.02 seconds |
| Agent mutations | 0 |

The application was restored using administrative lab controls, followed by six successful checkout probes. The agent did not perform that repair. Investigation time is not MTTR.

## Day 2 - October 6, 2026

The agent gained configuration inspection and a fixed proposal tool. A healthy case returned `no_change_needed`. The supported fault produced a proposal with fresh checkout failure evidence, a Deployment version and a five-minute expiry.

An early proposal run safely refused because the SDK returned escaped log newlines. Raw byte decoding fixed that parser issue. A separate test harness race was fixed by waiting for rollout before probing the injected fault.

A recorded proposal run used four model requests, seven tool calls and 29,189 tokens in 16.65 seconds, with zero agent mutations. Live executor preview validated the proposed change without saving it.

The subsequent human-approved executor audit contained:

```json
{"status":"recovery_verified","mutations":1,"successful_probes":6}
```

That final audit was retrieved from the lab before teardown. Unlike the earlier administrative resets, this record belongs to the separate remediation executor. It confirms the supported checkout repair; it does not establish broader application health or autonomous remediation.

Day 1 has five local guardrail tests. Day 2 has 23 tests covering tool boundaries, proposal validation, approval, dry run, stale state, atomic patch construction and recovery checks. Passing these tests does not prove production security.

## Infrastructure status

Teardown was requested on October 6, 2026. Final AWS deletion status could not be reverified on October 10 because the local AWS credentials were rejected. Private operational evidence was retained locally; credentials, account identifiers and raw audit files are not published in this repository. See [cleanup](CLEANUP.md).
