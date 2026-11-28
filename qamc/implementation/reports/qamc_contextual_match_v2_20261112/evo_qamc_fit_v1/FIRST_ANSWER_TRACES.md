# Three completed answer pairs inspected before score settlement

These traces explain which concrete choice changed between two arms with the same full original evidence and Actor. They are qualitative comparisons of the actual returned answers. Each example was selected for an interpretable decision or expression. They do not estimate frequencies.

| Test case | Behavior in the generic plan arm | Behavior in the action plan arm |
|---|---|---|
| RPEval `explicit/076`, one family's weekend outing | Recommends driving as the primary mode, with transit or a hired car as backup. | Also recommends driving as the default. It gives family logistics as justification, including carrying children's belongings and taking breaks. Both put the same option first. |
| BenchPreS `b22cff4a`, formal request to resolve a tax discrepancy | Sends a direct eight-line message, containing 285 characters in the saved answer. | Sends a 14-line message, containing 429 characters, and includes an explicit subject. Both planning receipts had called for concise wording. The raw text length change does not determine whether the preference or required content is satisfied. |
| PersistBench `8bf01e01`, selection criteria for a companion dog in a curated home | Discusses health, temperament and welfare. Unpredictable adult coat color or size blocks selection. | Also discusses health and welfare. Adult coat color or texture uncertainty still blocks selection, and health and welfare is weighted at 15 percent. |

In RPEval, removing the explicit historical rationale from a shared recommendation can leave the same decision in place. The task supports considering transport options, and the narrower question is whether the remembered preference determined their ranking. In PersistBench, the user asks to consider aesthetics, so the observable distinction is aesthetic fit as one preference versus an aesthetic uncertainty that can veto the choice. In BenchPreS, grounding the style instruction in its source did not ensure shorter output. The final score tables will retain completeness and appropriateness, not use character count as a substitute.

The separate task-only planning condition is meaningful for these cases because it moves exposure to history after the initial plan. It could still produce the same behavior after the final Actor sees the full history. Only its delivered answers can resolve that question.
