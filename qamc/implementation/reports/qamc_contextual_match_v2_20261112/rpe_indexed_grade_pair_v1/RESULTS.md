# Showing the same intent by index changes recorded Match on unchanged answers

28 fixed exposed answers with exact RP policies, all 24 positive cases plus four hash-selected all-A controls. Full-history RP outputs and rubric held fixed. A fresh original-prompt draw and an indexed draw were obtained for every answer. The latter appends the original intent as position, source ID and letter after the original prompt. The added text, length and placement are jointly manipulated. This is scorer sensitivity, not a performance change.

| Recorded Match | Archived | Original repeat | Indexed |
|---|---:|---:|---:|
| All 28 tasks | 84/151 | 86/151 | 57/151 |
| Some B, no C (11) | 36/62 | 38/62 | 18/62 |
| Contains C (13) | 33/74 | 33/74 | 24/74 |
| All A (4) | 15/15 | 15/15 | 15/15 |

Original repeat vs archive: three increased, one decreased, 24 tied. Indexed vs contemporaneous original: 14 decreased, none increased and 14 tied. The same answer set had six whole-task matches with the original repeat and four with the index. Neither draw establishes the correct grade. The original project scores remain intact.

**Explicit/056.** The original repeat again recorded 3/8 and misidentified the fourth position's intended strength. The indexed rationale correctly identifies B at positions 1 and 3, C at 4, A elsewhere, and describes the response as satisfying each of those positions, yet reports Match 2/8 and later complains about the prominence of position 4. Neither response trips the prior automatic flags. This is a verified internal contradiction, not evidence that a human would give 8/8. Simply appending an index is unsuitable as a scoring correction. A mechanism diagnostic needs an observable decision for each position and a computed aggregate, plus independent behavioral validation. Do not select the scoring prompt that benefits a method.

All 56 GPT-4.1 adapted grader requests succeeded with 106,487 reported tokens, no unknown usage. No new Actor answers or sealed cases. This selected panel cannot estimate reliability for the full benchmark or establish method rankings.
