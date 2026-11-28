# The released selector's exposure on the 40-task fit panel

Audit of the 40 frozen final-Actor request bodies before the end-answer benchmark scores were available. The audit verifies task equality, exact source texts and original order. The RPEval author labels and BenchPreS attribute applicability enter only this offline audit.

| Benchmark | Exposed / available original sources | Empty requests |
|---|---:|---:|
| RPEval | 41/96 | 0/16 |
| BenchPreS | 25/61 | 3/12 |
| PersistBench | 39/117 | 0/12 |

On RPEval the external selector sends all 13 B and seven C sources to the final Actor. It also sends 21 of 76 A sources, including 14 of 25 on the five all-A tasks. Each all-A request still contains history. Thus the selector has preserved candidate coverage for the fit panel's B/C positions, but the remaining A evidence can still affect recommendations.

On BenchPreS, all 60 evaluated attribute strings could be uniquely aligned verbatim to original sources. The selector exposes 17/23 appropriate and 8/37 inappropriate attributes. The prior full-history action arm realized 17/23 with 22/37 misuses, so there is a concrete trade-off to test. A selected source may remain unused, and a response can independently exhibit a style even when the source was omitted. Selection counts cannot predict either bound on the final answer's native grade.

On PersistBench the selector exposes 7/37 sources for cross-domain, 16/44 for sycophancy and 16/36 for strict beneficial use. These are descriptive and there is no reference source-necessity label for this audit.

The same filtered inputs are frozen for two next planning arms, one generic and one action-oriented. On one BenchPreS task all sources were retained, so both original outputs will be reused. The other 39 tasks receive filtered inputs. The parent Actor's outcomes do not affect which sources are frozen. [Exposure audit](SELF_RECHECK_EXPOSURE.json)
