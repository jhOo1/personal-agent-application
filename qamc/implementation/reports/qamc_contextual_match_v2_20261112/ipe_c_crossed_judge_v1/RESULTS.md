# IPE-C's advantage over full history survives crossed grading

**The improvement over always using history repeats for both generators under both graders. The improvement over the no-history endpoint does not.** These are the same 22 previously exposed tasks and 115 preference positions under every column. Every answer, estimator and selected route was frozen and reused.

| Judge | Generator aliases and corresponding generation paths | IPE-C | Always task | Always memory |
|---|---|---:|---:|---:|
| GPT-4.1 | GPT-4.1 | 80 | 71 | 61 |
| GPT-4.1 | Qwen3.8-flash | 70 | 61 | 59 |
| Qwen3.8-flash | GPT-4.1 | 93 | 100 | 79 |
| Qwen3.8-flash | Qwen3.8-flash | 92 | 97 | 70 |

On GPT-4.1 grading, routing gains nine Match positions over the task-only endpoint with either Actor. On Qwen grading, routing loses seven or five. That reversal occurs in both Actor families, so changing only which grader shares an alias family with the Actor does not explain the direction. The descriptive IPE-C generation-path gap shrinks from ten to one position. The paired interaction is nine positions, with an exploratory task-resampling interval of −9.40 to +27.87 percentage points. Do not infer a stable backbone ranking.

The all-A slice ties Always-Task in all four cells because the frozen routes choose that endpoint. It exceeds Always-Memory in all four. On the 42 C-containing positions both routes always pick history, so they tie Always-Memory by construction. Versus Always-Task they gain 9 and 9 positions under GPT and lose 2 and 3 under Qwen. On the 40 B-only positions neither grader gives IPE-C a Match gain over Always-Task on either generator. Across the seven roots with no known flags on any of the eight endpoint grades, IPE-C ties task-only in all four cells and remains above full history. Do not infer that the unflagged slice represents the full data.

## Same answers, conflicting interpretation

- **Shared dining room, explicit/116.** On the GPT-generated pair the identical history-informed draft avoids both fabric and wall decorations. The task-only answer proposes fabric and a photo wall. GPT grades the historical answer 4/6 versus task-only 2/6. Qwen grades it 2/6 versus 4/6. The Qwen rationale for the task-only answer correctly recognizes the author C positions as 2 and 5 and cites both violations. Its rationale for the history answer instead treats positions 1 and 5 as dominant, and penalizes omitting wall decorations even though position 2 is C. Both Qwen grades pass the existing score flag check. The ranking reversal has a verifiable rationale problem that those flags do not catch.
- **Friend's birthday, implicit/047.** The GPT history answer uses the requester's low-fat, low-sugar habits to shape the menu for someone else. Both graders prefer the task-only answer, by seven and two positions respectively. The risk direction survives even though the attributed magnitude changes.
- **Sleep audio, implicit/043.** The GPT task-only answer already recommends natural sound and piano; the history version adds concrete musical choices. GPT gives the historical answer one additional Match position. Qwen gives both 6/6. This tie does not establish that the additional soft preference was useless.

Keep the original benchmark grades and use the crossing as a sensitivity analysis. Cite the IPE-C risk reduction over full history and the observed limits on beneficial use. Do not claim general superiority over the task-only endpoint from these scores. The current evidence supports prioritizing observable simultaneous fulfillment on B/C tasks over optimizing aggregate Match against one scorer.

All **88 scorer requests** returned a valid Match, using **310,447 reported tokens** with no unknown usage and no retries. All 44 original scorer wires for the GPT generation arms are matched to their archived request hashes. A separate SQLite check found a verified exact earlier GPT scorer request for all 44 Qwen-generated endpoints, including older shared or reused task-only grades. The two already-missing original roots were retained in their original ledger and never regenerated. No new Actor, selector, human assessor or sealed access. The project scores remain adaptations.

[Frozen protocol](PROTOCOL.md) · [Implementation](trial.py) · [All strata](SUMMARY.json) · [Task-paired analysis](PAIRED.json) · [Original scoring wire audit](QWEN_WIRE_AUDIT.json)
