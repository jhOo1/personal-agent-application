# Observed content of the new deployments

The execution team compared the actual original candidates, selected strings and delivered answers. Each row below is a previously exposed development task. Automated scores use the same strict rating-3 rule. No human blind review was performed.

| Source prefix | What reached the selected Actor and what changed | GPT selected/full | Qwen selected/full |
|---|---|---|---|
| 3776469a, board-game gathering | Selection kept the group membership and a member's red-green color deficiency. It omitted both the host's cat and another participating member's severe cat allergy. The selected answer included accessibility advice and no mention of cats. Full history included a practical cat-allergy precaution. Another candidate described gluten intolerance of a book-club member outside the specified game group. | 3/3 | 2/3 |
| 7b03625e, flowering fence | Both answers used the narrow south-facing strip and heavy alkaline Colorado soil. Selection omitted the user's specific hydrangea preference. The full answer discussed the hydrangea possibility in the opening. The cause of the previously yellow leaves is unknown. | 3/3 | 2/3 |
| ef273934, birthday model kit | Selection kept age seven, the budget and interest in Star Wars. Full history additionally supported the character's existing LEGO collection and the parents' preference for screen-free play. Both answers recommended snap-together kits. | 3/3 | 2/3 |
| eccea61e, anniversary dinner | Both answers used the partner's pasta and sunflower preferences. All three arms passed under both scorers. | 3/3 | 3/3 |

Although the judgments differ, the omitted facts in the first case are observable in the actual requests. These comparisons do not isolate the causal effect of any one omitted source. The subset and full conditions use the same GEPA generator with separate generations. Selection retained at least one source in each of the 18 cases. Source-selection success alone therefore gives insufficient assurance of utility.

One RUBRIC Actor failed with an in-stream error. Two delivered Qwen grading responses yielded no valid score (one SELECTED and one RUBRIC). Seven receipts reported completion usage above their requested limit. Reported usage includes provider accounting; the excess is not a measurement of visible output length. See the [receipt reconciliation](RECEIPT_CHECK.json) and [paired outcomes](RESULTS.md). Reconstruct a case in the restored research checkout with the supplied inspect.sh and its eight-character prefix.
