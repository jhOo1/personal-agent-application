# RPEval negative control for memory-use attribution

The fixed-exposure study supplies a control where the Actor receives no original sources. This audit checks each recorded request against the frozen digest, checks the archived task-only planner input, and reads the unchanged Project GPT-4.1 RPEval grades. All 124 graded no-history answers also have empty current-context and Facts fields. Their plan may use what the current question says. The audit makes no model calls, reads no sealed data, and preserves the original scores.

| Author task stratum | Assigned | No-history strict Match | Positive OPB grades | Among cases without known flags |
|---|---:|---:|---:|---:|
| All A | 59 | 155/240 across 58 tasks | 10/58, 7 source groups | 4/41 |
| B only | 15 | 31/84 across 14 tasks | 5/14, 3 source groups | 4/12 |
| Contains C | 52 | 136/310 across 52 tasks | 22/52, 12 source groups | 18/48 |
| All | 126 | 322/634 across 124 tasks | 37/124, 16 source groups | 26/101 |

The operation makes actual causal influence from a supplied source impossible. It does not guarantee high task quality or prevent generic suggestions from coinciding with an old preference. A positive OPB grade in this control cannot identify influence from *supplied* memory. For B and C, access to history is intentionally removed; legal memories can be omitted and UPB is expected there. The all-A row is the more direct test of overuse attribution. The original judge always reads the complete rubric input including the preferences expected to be ignored.

In the four unflagged all-A examples, each got zero Match. The tasks ask for a cozy living room, a family road trip with explicitly retired parents, a bedroom with lived-in warmth, and an inviting children's room. The judge reasons attribute ordinary advice about lighting, soft furnishings and subdued colors to invisible history. For the road trip, the reason explicitly concedes that the response does not directly cite any persona and penalizes accommodating the parents' mobility and rest anyway. Those participants are specified in the current request. The example analysis is an unblinded review of saved answers and rationales. It does not adjudicate every listed task error or furnish a frequency estimate beyond this development panel.

## Consequence for search

On the first 12-task whole-Actor fit, a birthday recommendation has no JCC history in any compared call. Scope and the two optimized Actors all provide general party options using the friend's possible interests. The saved judge calls Scope 0/7 with OPB 3, then scores both optimized answers 7/7 with OPB 0. No existing arithmetic flag catches the swing. This is the only protected RPEval improvement in the first-round JCC oracle inventory. Removing that zero-exposure all-A case from that diagnostic leaves no protected gain at all. Different prompts can still improve answers when memory is absent. This example cannot establish a seven-position memory-control repair.

Keep the official-style scores as reported, and separate actual visible evidence, changes in the action or delivery, and the grader's attribution. A paper claim about better use of memory needs evidence beyond score changes on zero-exposure cases. This is not a replacement metric or a statement that all BenchPreS, PersistBench or RPEval grades are wrong.

[Negative-control counts](NO_HISTORY_RPE_GRADES.json) · [Exposure protocol](EXPOSURE_CONTROLS_PROTOCOL.md) · [Whole-Actor stored-answer frontier](FIRST_PASS_FRONTIER.json)
