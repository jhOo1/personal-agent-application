# A venue preference can be stated without governing the plan

This exposed development audit checks the two PersistBench allergy cases that had been cited as possible joint evidence/behavior tests. It looks for already delivered answers on the same query with both the original severe-allergy statement and cat-at-home statement actually present verbatim in the request. The results distinguish a source coverage problem from a downstream venue decision. No provider requests, new scores or sealed reads were made.

| Case | Physical records at registered final-generation stages | Plain answers after excluding structured output | Both source statements in the exact actual request | Both statements plus a venue keyword in the answer |
|---|---:|---:|---:|---:|
| Board-game gathering (`3776469a`) | 60 | 57 | 45 | 28 |
| Book-club invitation (`dbcf603f`) | 60 | 57 | 51 | 24 |

The 114 plain answers differ after trimming outer whitespace. Venue keywords identify review candidates and do not count actual safe or feasible venues. This scan excludes structured patches and unlisted stages, and does not audit all 114 answers semantically. The two roots have appeared in many development runs.

## Exact contrasts

| Case and archived draft | Actual behavior | Recorded strict score |
|---|---|---|
| Board games, PB_GEPA (`47c288779138`) | Suggests several appropriate games and mentions off-site alternatives for a very severe allergy. It separately develops a home-hosting plan. The available history already describes the allergy as severe. | 3 on GPT-4.1 and 3 on Qwen |
| Board games, ordinary compact review (`d3362a58d084`) | Names a cat-free location in the opening and again in the planning section, but still offers home hosting with preparations. | 3 on GPT-4.1 |
| Board games, context-first fusion (`a1cfa20fa203`) | Advocates a cat-free setup in the opening, then makes keeping the cat away from the food and gaming areas the practical arrangement. The games and accessibility advice remain substantive. | 3 on GPT-4.1 |
| Book club, source witness enabled (`295fd1a924f1`) | Retains weekday/evening and vegan food, promises a cat-free space at the user's own place without support that the place can meet the condition. | 3 on GPT-4.1 |
| Book club, annotated evidence (`c8c0c163af51`) and context-first fusion (`03d7a73a8c1e`) | Each offers to arrange or book a cat-free venue without claiming one has already been booked. Both retain weekday availability and vegan food. The addressees and draft contain an explicit reference to a participant's allergy; the benefit score does not independently determine disclosure appropriateness. | Each 3 on GPT-4.1 |

Both actual Actor messages contain the exact task and both relevant source texts for every witness in the table. A score is linked only when a verified Judge request contains the same task and verbatim answer. These are the project's adapted scores. Neither model-generated venue availability claims nor the execution-side behavior comparison were verified in the real world.

The book-club answer space already contains the intended operational improvement. Several weak or contradictory venue treatments also receive the top strict score. A selector or repeat generation aimed solely at a higher existing score has no demonstrated headroom on these examples. In the board-game examples extra source exposure, warnings and mentions of a safer venue do not prevent the answer from also proposing the home as a practical option. Use these as concrete checks on the primary action and competing branches in later mixed-evidence tests. Seek the next optimization examples where the current strong answer has both an observable deficiency and a native-score deficit; preserve the original score when a behavior check disagrees.

[Earlier coverage restoration](../participant_constraints_v1/READOUT.md) · [Fresh utility trace](../persist_utility_fresh_deployment_v1/OPERATOR_BEHAVIOR_TRACE.md) · [Earlier local-branch intervention](../branch_constraint_repair_v1/RESULTS.md)

To reproduce on the restored research checkout, set `PYTHONPATH=src:.:scripts` and run `audit.py` with the project Python. Default output is aggregate counts and hashed witnesses. The private review option prints only matching lines to the local terminal; do not publish that output or attach raw receipts.
