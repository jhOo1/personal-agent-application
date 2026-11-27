# RPEval candidate-count development baseline

The policy uses the original fixed candidate count before any selection. With one candidate, use the normal RP-Reasoner history request, including its existing per-source A/B/C policy. With multiple candidates, preserve IPE-C's task-level choice and original selected Actor request. An empty snapshot remains empty. No evaluator field, case identity, preference wording template or historical score participates in the branch. The code packages a simple performance baseline for further development.

| Same 22 single-preference development tasks | Match | OPB | UPB | FM |
| --- | ---: | ---: | ---: | ---: |
| IPE-C | 15/22 | 0 | 23 | 30 |
| Candidate-count branch / original RP | 17/22 | 0 | 7 | 17 |
| Des2Gen | 18/22 | 1 | 7 | 23 |
| MemAdapter | 18/22 | 3 | 3 | 14 |

The two Match flips on the exposed single-preference sample are the known Japanese-food and workout-audio failures. Both are author C. A and B Match tie across this branch and IPE-C. There are 24 allocated single-preference tasks. Eighteen route choices change, and two tasks are outside the strict common denominator. The earlier two-endpoint ceiling still trails the best archived external methods.

All 295 recoverable original routes on the separately allocated 300-task multi-preference panel stay identical. Five are unavailable. There are 282 valid candidate-count / IPE-C scores among the 295, with 970/1510 Match. This is that method's available-score denominator; the common RP comparison uses a different denominator. No new answers or scores were generated. Single and multi tracks use separate project scoring adaptations, so no pooled score is reported.

This is an intentionally simple development baseline and combines two already known route policies. The 2-position improvement confirms the compatibility of the branch with the existing tested endpoints and supplies no new independent validation or external lead. Before any broader claim, freeze the method and scorer and compare on a fresh source-disjoint panel from the same benchmark.

Replay after restoring the research checkout:

```bash
PYTHONPATH=src ../qamc/.venv/bin/python -B \
  reports/qamc_contextual_match_v2_20261112/rpe_cardinality_route_v1/replay_cardinality.py
```

[Results](REPLAY.json) · [Executable branch](cardinality.py) · [Original single-preference comparison](../rpe_single_endpoint_bridge_v1/READOUT.md)
