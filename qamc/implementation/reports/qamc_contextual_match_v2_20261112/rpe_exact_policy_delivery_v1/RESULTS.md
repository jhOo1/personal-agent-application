# Correct RP policy versus recorded final-answer Match

Offline evaluation on the exposed formal 300. Four cases lack an Actor request and nine more lack a matched answer/grade. For 287 tasks, verify the ordered IDs in the actual Actor request, the stored answer hash, and the archived RP Match. The author labels enter only after generation. These are full-history RP, not the routed IPE-C answers. An exact policy has every A/B/C equal to the author label.

| Exact-policy tasks | Tasks | Positions | Final Match | Entire answer matched |
|---|---:|---:|---:|---:|
| All A | 17 | 72 | 72/72 | 17/17 |
| Some B, no C | 11 | 62 | 36/62 | 1/11 |
| Contains C | 13 | 74 | 33/74 | 0/13 |
| All | 41 | 208 | 141/208 | 18/41 |

Across all 287 tasks there are 680 recorded misses in 1,540 positions. For each task let m be its recorded missed positions, n its length, and d its incorrect predicted labels. At least max(0,m-d) and at most min(m,n-d) of its recorded misses would have to overlap correct predictions under any position assignment consistent with the Match count. Summed range 241–488. This does not reconstruct per-memory judgments, or imply that every recorded miss is a real behavioral error. Strata are observational and may differ in difficulty. Among the 33 exact-policy tasks without pre-existing diagnostic flags, recorded Match is 123/179; absence of a flag is not validation.

## Counterexample to allocating the residual to generation

Explicit/056 asks for a Zhangjiajie itinerary for older adults and children. The fourth memory explicitly rejects high-altitude activities including cable cars, glass walkways and skybridges. The predicted and author strings are both BABCAAAA. The answer explicitly excludes those activities and offers a ground-level walk and a sightseeing train. The archived Judge records 3/8 and itself repeats BABCAAAA, yet describes positions 2, 4 and 5 as supportive obligations (their actual codes are A, C and A) and penalizes making the altitude restriction central. This record had no previous diagnostic flag. The contradiction establishes a misreading in the rationale; it does not establish a corrected total or that every other travel suggestion was sound.

Decision: keep original grades. Before optimizing generation on exact-policy positive tasks, use an index-explicit scorer diagnostic on the same stored answers, paired against the original rubric, and check whether direct behavioral changes clear the discrepancy. Never pass author labels to the Actor. The marked discrepancy was found post hoc. No new model requests, independent raters or sealed inputs.
