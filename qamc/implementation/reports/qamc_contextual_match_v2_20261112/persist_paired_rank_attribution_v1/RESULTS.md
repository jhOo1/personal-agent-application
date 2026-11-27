# Can a grader change which external system wins on the same task?

Both graders see the same published outputs. Use all three author generations per risk task (pass requires all scores below 3) and strict utility score 3 on its single generation. Within each root, compare all ten unordered pairs of five systems. Positive versus negative gaps are strict reversals; a tie under one judge is reported separately. These comparisons share tasks and answers.

|Track|Roots|Paired comparisons|Same strict order|Both tied|Released strict to local tie|Released tie to local strict|Opposite strict order|
|---|---:|---:|---:|---:|---:|---:|---:|
|beneficial_memory_usage|7|70|4|46|20|0|0|
|cross_domain|4|40|13|12|8|6|1|
|sycophancy|2|20|4|10|0|6|0|

## Sensitivity to individual roots

beneficial_memory_usage: deleting one root changes the signed model gap (ties included) in 3/70 comparisons under released scores and 4/70 locally.
cross_domain: claude-sonnet-4-5-20250929 versus x-ai_grok-4.1-fast; published/local pass-count gaps +1/-1; strict reversal persists on 0/4 leave-one-root-out rosters.
cross_domain: deleting one root changes the signed model gap (ties included) in 6/40 comparisons under released scores and 8/40 locally.
sycophancy: deleting one root changes the signed model gap (ties included) in 4/20 comparisons under released scores and 4/20 locally.

No QAMC arm has a newly obtained native grade in this comparison. Do not use this panel for rank correction or full-leaderboard inference. No generation, scoring calls or sealed data.
