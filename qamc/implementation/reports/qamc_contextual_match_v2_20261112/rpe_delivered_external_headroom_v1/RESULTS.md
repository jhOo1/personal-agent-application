# RPEval: replace the active generator while preserving the IPE-C switch

**Retain the original generator.** Applying Des2Gen only on the original IPE-C history-on branch reduced underuse severity but increased overuse and reduced Match. This was an exploratory archived deployment replay on 300 exposed tasks. The reconstruction consumed zero new model calls. Real cold-start use would pay for both the IPE decision and the chosen branch.

| Paired answers | Match (IPE-C → composition) | OPB | UPB | FM |
|---|---|---|---|---|
| 280 tasks | 964 → 957 / 1502 | 255 → 304 | 266 → 228 | 53 → 76 |
| Both grades unflagged, 206 | 775 → 773 / 1145 | 174 → 200 | 138 → 119 | 43 → 62 |
| Contains C, 114 | 417 → 419 / 701 | 179 → 218 | 109 → 68 | 33 → 51 |
| B only, 49 | 150 → 145 / 286 | 14 → 21 | 102 → 101 | 9 → 9 |
| All A, 117 | 397 → 393 / 515 | 62 → 65 | 55 → 59 | 11 → 16 |

Of 282 scored IPE-C tasks, the composition lacked two Match values. Even allowing every possible score for those two, its net Match difference is between −13 and −5 positions. This bound excludes 18 tasks lacking a reference grade. On 274 three-way common tasks (1472 positions), original IPE-C scored 949, composition 942, and always-Des2Gen 704. A strong switch helps that generator, yet the combined algorithm falls short of the original.

## Why test it?

On 121 active-path tasks with at least one author B/C, source-by-source comparison verified the complete original ordered memories in the hashed original Actor wire and the exact saved IPE-C answer. Among clean pairs Des2Gen scored higher with no worse OPB/UPB/FM on eight tasks across six source groups; MemAdapter did so on six tasks across five groups. Applying each rival across its own clean paired subset produced only +2/471 and 0/444 net Match positions respectively. Picking only favorable cases uses scores and does not define an online selector.

For example, in explicit/097, a cold-weather dinner for a girlfriend, both answers supplied a mild, warm meal. Des2Gen specified a two-person menu and an overall cooking time, and the recorded underuse severity was 0 versus 2. The score does not identify which addition caused the improvement. On explicit/073, a family outing near Xi'an, Des2Gen organized a day around open sites with specific arrival and crowd-management suggestions. The original also discussed queues. These case differences justify examining concrete recommendations; they do not establish a universal missing behavior.

The score diagnostics and author's labels are used only in retrospective analysis. This experiment gives no independent or official leaderboard result. [Frozen composition](PROTOCOL.md) · [Scoring](compose.py) · [Source delivery audit](audit.py) · [All intersections](COMPOSITION.json)
