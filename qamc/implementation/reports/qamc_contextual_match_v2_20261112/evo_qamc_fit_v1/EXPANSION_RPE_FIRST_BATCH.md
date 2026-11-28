# First-batch RPEval scores

This is the completed RPEval scoring stage of batch 1. BenchPreS and PersistBench in batch 1 were still executing during this read. This is source-separated exposed development, and scores use the frozen project GPT-4.1 evaluator. The 122 dispatched RPEval grading requests returned successfully. A read-only manifest and receipt hash check replayed the original parser and consistency checks with no added calls. There were 42 assigned RPEval tasks, 41 usable Scope–parent pairs, and 39 tasks common to all three fresh arms and archived IPE-C.

| Common 39 tasks | Match | OPB | UPB | FM |
|---|---:|---:|---:|---:|
| Archived IPE-C | 124/199 | 37 | 33 | 5 |
| Direct, released Self-ReCheck selector and common direct Actor | 83/199 | 96 | 16 | 21 |
| Plan plus selected evidence | 90/199 | 55 | 40 | 16 |
| Scope | 100/199 | 51 | 39 | 19 |

The Scope–parent difference is +10/205 on their 41 valid pairs. Removing any task with a known flag on either arm leaves 28 tasks and 141 positions, with Scope 75 and parent 69. Scope also improves on Direct after excluding flagged cases, 79/150 versus 57/150 on 29 tasks, but UPB rises from 11 to 17 on this slice. Scope remains behind archived IPE-C on the pairwise unflagged slice, 67/130 versus 89/130 on 26 tasks.

On the all-method common set, Scope versus parent delivers +5/80 Match on all-A tasks with OPB 26→28. Tasks containing author C produce +2/82 Match with OPB 24→19, UPB 16→20 and FM 8→12. Those 82 positions include other author labels. The aggregate Judge bounds on the actual B and C Match deltas remain inconclusive, −10 to +11 on 17 B positions and −14 to +15 on 21 C positions, using the respective common pairs.

| Scope versus comparator | Task wins/losses/ties | Source-group wins/losses/ties | Equal-source Match delta | Position-weighted delta omitting one source at a time |
|---|---:|---:|---:|---:|
| Plan plus selected evidence | 7/3/31 | 6/3/12 | +6.76 pp | +2.50 to +7.69 pp |
| Direct | 6/2/31 | 5/0/15 | +13.07 pp | +6.19 to +9.66 pp |
| Archived IPE-C | 2/9/30 | 1/8/12 | −19.26 pp | −14.84 to −9.52 pp |

Each paired group is scored on its own common positions; group direction uses the same raw Match numerator. The leave-one-group calculation is an observed sensitivity range, not an independence or significance claim. Unlike the 40-task fit-panel gain, the first-batch Scope advantage over its parent survives removing each represented group.

Keep the frozen panel running. The initial results support further evaluation of Scope against its exact parent and Direct, while the existing specialist still leads and the use–suppression trade-off persists. Compare RPEval source groups after all batches settle. Do not treat the displayed raw Match deltas as observations of the source-level behavior in [the inspected answers](EXPANSION_BEHAVIOR_TRACES.md).
