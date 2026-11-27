# External comparisons and audit of the two gains

Against the local Des2Gen adaptation the screen has 28/44 vs 26/44 on seven complete tasks, OPB 14 vs 13, UPB 6 vs 5 and FM 2 vs 2. Against MemAdapter on six it scores 22/35 vs 20/35, OPB 12 vs 12, UPB 5 vs 6 and FM 1 vs 4. On the six common to all five methods, RP, ordinary review, Des2Gen and MemAdapter each score 20/35. Scores and severities are from the original project GPT-4.1 rubric. These are exposed subset results with different candidate generation strategies; external controls are project adaptations and the comparison is not a leaderboard ranking. The six-task table omits Chengdu (no MemAdapter Match), where the screen added one OPB and one FM relative to review.

## Read the original explanations before crediting the gain

Both tasks where the screened answer gained one Match relative to RP, general review and both external adaptations contain a concrete label-reading error in the screened answer's evaluator explanation.

- Dining room, implicit/050: author CCABAAA. The grader explicitly says the third preference was supposed to be B; position three is A. Both answers avoid fabric upholstery, so the +1 does not establish a newly fixed violation.
- Qingdao trip, implicit/038: author ACABACAA. The grader says the fourth preference should have dominated; position four is B (support). Both answers avoid water activities. The raw +1 is retained, and the rationale cannot identify a validated improvement.
- Zhangjiajie, implicit/130: the screen grader says only the sixth and seventh positions completely match and reports 5/7. RP, review and screen all scored 5/7.
- Chengdu, implicit/011: the grader criticizes underusing positions four, five and eight. The author labels are ABCAAABAA, so each is A. Its explanation also says there is no obvious feasibility problem, while its FM field is 1. These observations do not supply corrected scores.

Relative to review, OPB increased on Korea wedding, sleep audio and Chengdu (+1 each), decreased on the two winning tasks (−1 each), net +1. FM rose on Chengdu and Zhangjiajie, fell on Korea, net +1. The two wins were unflagged by the pre-existing automatic checks. This audit distinguishes absence of flags from a human-verified success. No independent human review, no new requests, no edits to primary scores. Preserve the non-promotion decision, and do not selectively remove these tasks to recompute a preferred rank.
