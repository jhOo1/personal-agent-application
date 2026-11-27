# A query-only hard shutdown loses useful memory

Retrospective analysis of previously exposed development sources. The saved query-only decision was originally used to choose one of two evidence selectors. Here a positive decision directly exposes the full memory and a negative decision exposes none. This tests whether the second stage can be removed. The replay assigns the original GEPA Actor answer and original project GPT-4.1 adapted grade for the chosen exposure. It does not use the gold category to route. Category determines the metric after routing. For missing route receipts the outcome stays unknown. No new model calls or reruns.

| Confirmed passes / failures / unknown | Query switch | Full | Empty | Original selector | Selector nonempty opens all |
|---|---|---|---|---|---|
| Sycophancy, 12 roots, three draws | 11/1/0 | 5/7/0 | 11/1/0 | 11/1/0 | 9/3/0 |
| Cross-domain, 19 roots, three draws | 14/0/5 | 12/5/2 | 14/0/5 | 15/1/3 | 13/1/5 |
| Strict beneficial use, 18 roots, one draw | 7/6/5 | 17/0/1 | 2/16/0 | 12/0/6 | 13/0/5 |

All 93 risk decisions turned history off. Six of the 13 available utility decisions also turned history off. On those same six roots the grounding selector picked 3–5 memories, the selected and full answers each scored 3 on all six, and the empty answers scored 1 or 2. This is a direct six-root failure of treating the absence of a query-only request for history as sufficient evidence to suppress it. Even if all five missing utility outcomes passed, the binary switch would reach only 12/18 versus at least 17/18 for full. This does not establish that a specific selected memory caused each gain. The remaining five original router failures were never retried. The original study provides the risk repeat and severity rules and physical receipt provenance.

Decision: reject the query-only hard shutdown as a simplification. Retain the memory-aware grounding pass even for queries without an explicit personal information gap. Infer no independent leaderboard result or benchmark incompatibility. This archive reuses fixed exposed tasks and saved model outputs; this was an exploratory choice after development.
