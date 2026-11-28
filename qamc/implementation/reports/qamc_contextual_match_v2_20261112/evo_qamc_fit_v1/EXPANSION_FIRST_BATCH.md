# First expansion batch settled

The first 57 of 162 assigned exposed development tasks settled. Batch 2 is running the precommitted configuration. All three new arms use the same selected evidence from the released Self-ReCheck selector. Parent and Scope also share the same task-only plan and differ by one Actor instruction. Archived specialists are compared on each task under the same project scoring adapters.

| Measure on the all-arm common tasks | Archived specialist | Direct | Plan plus selected evidence | Scope |
|---|---:|---:|---:|---:|
| RPEval Match, 39/42 tasks | 124/199 | 83/199 | 90/199 | 100/199 |
| RPEval OPB / UPB / FM | 37 / 33 / 5 | 96 / 16 / 21 | 55 / 40 / 16 | 51 / 39 / 19 |
| BenchPreS AAR, 2/4 tasks, one profile | 2/2 | 1/2 | 1/2 | 0/2 |
| BenchPreS MR / task completeness | 0/8 · 10/10 | 0/8 · 9/10 | 1/8 · 9/10 | 0/8 · 10/10 |
| PersistBench cross-domain pass | 3/3 | 0/3 | 1/3 | 3/3 |
| PersistBench sycophancy pass | 1/2 | 0/2 | 1/2 | 2/2 |
| PersistBench strict beneficial use | 5/5 | 5/5 | 5/5 | 5/5 |

The BenchPreS applicable preference on each of the two common tasks is bold formatting. On one, the shared selector passes no preferences. On the other it passes four attributes including the applicable preference. Direct and the parent implement the bold preference on that second task, while Scope misses it despite the same evidence and a completion grade of five. Two other generated answers have an invalid completeness rating, one in Scope and one in Direct. The Scope–parent pair has three complete grades, with AAR 1/3 versus 2/3, MR 0/12 versus 1/12, and completeness 15/15 versus 13/15. This profile captures both a shared selection gap and a separate realization loss. It cannot establish performance on other profiles or semantic style.

The frozen equal-domain macro on comparator-specific common cases puts Scope +13.66 percentage points over the parent, +20.90 over Direct and −6.24 behind the archived specialist combination. Scope versus the archived combination ranges from −14.86 to −4.35 points under extreme missing-value assignments within this completed batch. PersistBench's short initial safety track contributes substantially to the improvement; report the original track denominators. RPEval's Scope–parent gain spreads across multiple groups, while the specialist wins in eight groups and loses in one. [RPEval response and source-group details](EXPANSION_RPE_FIRST_BATCH.md)

Cost was 479 physical requests and 1,640,280 reported tokens. There were 477 successful transport responses and two unknown deliveries with unreported usage, one planning and one Actor request. The archived specialist scores and six exact selector replies were reused. Expanding the benchmark claims requires the remaining batches and protocol-matched evaluation. This readout does not decide the final method.
