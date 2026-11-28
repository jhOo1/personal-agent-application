# A single attribute replacement did not improve the strong draft

The editor received each of the 24 first-wave IPE-C drafts, original task and fixed source texts. It saw no UID, author labels, scores or competing draft. The two arms each used one call with the same Actor and cap. Each could preserve the answer or replace one exact, uniquely located substring with source support. The experimental arm additionally required a separately named object in the same sentence as the old value. The target and some scores were known to the designers. This is an exposed development test.

| Same 24 tasks, 139 positions | Match | Whole tasks | OPB | UPB | FM |
|---|---:|---:|---:|---:|---:|
| Original IPE-C | 90 | 9 | 19 | 20 | 6 |
| Generic local revision | 83 | 6 | 26 | 27 | 5 |
| Attribute-value replacement | 79 | 7 | 20 | 27 | 7 |

In the experimental arm six edits executed, nine proposals failed the contract and nine returned KEEP. The six executed edits produced zero Match wins, three losses and three ties versus the exact base. The generic arm executed 19 edits, with four KEEPs and one invalid proposal. Removing cases with any pre-existing automatic flag across the three scores gives 16 roots / 97 positions: base 65, generic 59, experimental 61. Judge score changes can exceed the number of changed decisions. All original scores and flags are preserved.

- Bedroom: the experimental model tried to replace a whole curtain sentence and append a bright accent. The contract rejected it. The generic suggestion of a bright accent scored the same 2/5 as the base. This test used the first draft, which already offered a vintage-red rug. It does not establish what editing the second draft would do.
- Spanish travel: generic changed memorizing 20 travel words into repeating them aloud and correcting a recording. The preference explicitly supports imitation and correction. Match stayed 2/4. The experimental proposal appended a pronunciation instruction to a full sentence and was rejected.
- Manager lunch: generic attributed the group recommendation to the requester's efficiency preference (3/3 to 2/3). Experimental KEEP preserved 3/3. Both arms kept the Chinese dinner for the user's wife.
- Hainan family holiday: the experimental arm appended a personal challenge rationale to the existing light surfing suggestion. It passed exact-span checks, yet it kept the old activity and added an attribution. The Judge scored 6/6 to 0/6 and described unused all-A history in terms of underuse. This is evidence of an undesired edit plus a disputed score magnitude.
- Solo exhibition: changing an unpopular exhibition to an unpopular or unusual-themed exhibition met the execution contract. Both edited arms fell from 5/5 to 1/5. The experimental grader said the first preference appeared and also that curiosity was missing. Four lost positions cannot be causally assigned to the one change.

The frozen advancement criteria failed. The original routed drafts remain the RPEval reference. The contract both rejected desirable-looking proposals and admitted a rationale presented as a value; simply easing the locator cannot account for the losses among accepted edits. No transfer or sealed evaluation was launched. The current detailed GPT-4.1 grader is the project's adapter; this is not an external ranking or human review. Total 48 editor calls and 25 fresh grades, all successful; 23 unchanged drafts reused the original grades. 281,065 reported tokens, zero retries or unknown usage. Separate comparisons of both arms with new scores conditional on editing would select different tasks.

[Protocol and eligibility examples](PROTOCOL.md) · [Source and model prompts](run.py) · [Strata and request counts](SUMMARY.json) · [Input and receipt checks](verify.py)
