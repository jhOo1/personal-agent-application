# RPEval soft-preference action intervention on frozen drafts

An analyst supplied the previously verified preference-specific action or an approximately equally specific generic action at the same unique span in each saved no-history draft. The original draft and everything outside that span were fixed. This tests score sensitivity to the action on three exposed roots. It does not estimate whether an automatic method can find the target and produce the action.

| Saved Actor | Project Judge | Original Match | Source-specific | Generic-specific |
| --- | --- | ---: | ---: | ---: |
| GPT-4.1 | GPT-4.1 | 11/18 | 11/18 | 11/18 |
| Qwen | GPT-4.1 | 13/18 | 13/18 | 13/18 |
| GPT-4.1 | Qwen | 16/18 | 18/18 | 16/18 |
| Qwen | Qwen | 13/18 | 16/18 | 14/18 |

- Bedroom decor: implementing the requester's warm, bright accents, in place of a neutral accent, gave the Qwen Judge gains of 3→5/5 and 2→4/5 over generic specificity on the GPT and Qwen drafts. GPT Match tied both edits on both drafts. One Qwen-draft GPT grading had a Match/bias inconsistency in every arm.
- Family travel: adding an appropriate local folk activity beat neither equally specific sightseeing nor the GPT-scored originals. Qwen scored both edits of its own draft 6/7 versus 5/7 originally, with a flag on the generic edit.
- Sleep audio: named preferred musicians and generic instrumental tracks both moved Qwen's score of its own draft from 5/6 to 6/6. GPT Match remained tied. This case supplies no evidence that the score required a preference-specific action.

Qwen reductions in underuse severity for the source edit were 2→0 and 4→0 on the two Actor families. GPT underuse was 6→6 and 4→3, respectively. The complete per-root flags, OPB and FM are in the [summary](SUMMARY.json). Only one root showed a unique Match lift over the equally specific generic alternative, under one Judge. This is insufficient evidence to invest in another general automatic soft-action editor or to claim a cross-Judge gain. The behavior gap remains real even when a scorer is insensitive to it.

The input, single-span edits, grader configurations and receipts were linked by hashes. Pre-dispatch code and protocol were committed as `1d799544c2`. All 24 prospective scoring requests returned successfully and parsed for Match. Reported tokens 74,281, zero unknown usage, zero retries, zero Actor or Selector requests. Historical scores were reused. The two Judges evaluate the same edited texts and are not independent replications. No sealed data and no human adjudication. [Frozen design](PROTOCOL.md)
