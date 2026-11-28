# Task-first utility review did not obtain paired judgments

The frozen PersistBench strict beneficial-use panel comprised 18 exposed source groups with two archived answers each. The new review was completed at the request-ledger level. No case obtained an independent model judgment of the two actual answers.

| Stage | Physically dispatched | Valid response | Unknown delivery | Not eligible |
|---|---:|---:|---:|---:|
| Predicates from Query and original history | 18 | 2 | 16 | 0 |
| Anonymous answer evaluation | 2 | 0 | 2 | 16 |
| Total requests | 20 | 2 | 18 | — |

All 18 unknown deliveries returned HTTP 200, the expected GPT-6.1-sol alias and a stream ending marker. Each retained a choice finish reason of `in_progress` instead of a verified terminal `stop`. The recorded evidence does not establish whether this reflects the remote response state or a compatibility issue. No automatic retry was made. Of 20 requests, 20 lack usable token usage. The reported subtotal is zero and total consumption is unknown. No Actor or benchmark Judge was run again.

Both successful predicates were frozen before their respective anonymous answer requests. Both evaluation requests ended with unknown delivery. The no-call replay and exposure join agree: no paired result on any of the three review axes for any of the 18 assigned cases, including the three previously recorded Qwen-only strict-use differences. No old scores were changed. This run cannot arbitrate the GPT-4.1 versus Qwen disagreement, establish protected utility or change the main development results. Keep the live mechanism search separate from this unsuccessful qualification.

[Review protocol and implementation](UTILITY_ACTION_REVIEW_PROTOCOL.md) · [Original paired grading results](../persist_utility_fresh_deployment_v1/RESULTS.md)
