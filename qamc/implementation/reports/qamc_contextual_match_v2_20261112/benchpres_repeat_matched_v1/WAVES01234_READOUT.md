# BenchPreS comparison after five of six repeat waves

Five frozen waves have settled. Of 40 exposed tasks, 36 contribute 104 same-task, same-draw pairs. Both methods use the same Qwen3.8 Flash alias, temperature 1.0 and Qwen grading adaptation. Each retains its own frozen Actor input and policy. The final wave has started. [Protocol](PROTOCOL.md) · [Primary replay](WAVES01234_REPLAY.json)

| Common paired metric | Strong Gate | Author Selectivity |
| --- | ---: | ---: |
| MR | 1/339 | 42/339 |
| AAR | 152/181 | 135/181 |
| Bold AAR | 59/61 | 41/61 |
| Non-bold AAR | 93/120 | 94/120 |
| Mean completeness | 496/104 | 492/104 |

On 32 tasks with all three draws scored under both methods, MR is 1/315 and 39/315, and non-bold AAR is 84/108 on each arm. Gate has lower MR in nine profiles with one tie. Selectivity's same-case misuse labels include 34 literal inappropriate nicknames. Gate has zero literal inappropriate nicknames on those 104 positions. Three additional Selectivity answers contain the corresponding nickname without being flagged by the adapted Judge. [Profiles](WAVES01234_PROFILE_TRACE.json) · [Misuse trace](WAVES01234_MISUSE_TRACE.json)

## A non-bold omission at selection and remaining answer-side misses

On 117 of the 120 paired non-bold positions, the exact normalized attribute is visible in Gate's selected original text and in Selectivity's input. Of these, 82 receive credit from both, 14 from neither, and the totals are 93 and 92. The other three draws concern one objective-information preference in a debt-consolidation request. The expression is missing from Gate's original evidence and fixed facts, whereas Selectivity sees it and gets credit on two of the three draws. The previous one-draw source audit also identified this case. It is an upstream loss on one task, alongside the previously traced failures after successful delivery. The original scorer still cannot distinguish unsupported factual linkages from the strength of stylistic realization. [Delivery replay](WAVES01234_DELIVERY_TRACE.json) · [Grounding case](OBJECTIVITY_GROUNDING_TRACE.md)

## Missingness, repeat identity and cost

A separate fieldwise replay uses valid individual grades without replacing original strict outcomes. The 40-task allocation permits MR differences from −44 to +5 positions across 396 applicable-to-MR slots. It preserves the direction of overall AAR (+9 to +26 positions) and bold AAR (+15 to +24) under all score assignments. Non-bold AAR (−6 to +2) and completeness (−55 to +5 points summed over the 120 draws) can change direction. On the 30 tasks with historical single-draw and current complete grades, MR is 1/99 vs 10/99 historically and 1/297 vs 37/297 currently. The service fingerprint difference precludes interpreting that numerical shift as the isolated effect of temperature. [Fieldwise bounds](WAVES01234_FIELDWISE.json) · [Matched historical draws](WAVES01234_STABILITY.json)

There are 1,590 physical requests, 1,589 successful transports, one failed stream with unknown delivery and usage, three invalid aggregate scoring contracts, and zero automatic retries. Reported usage totals 2,212,825 tokens. Strong Gate and Selectivity use 993,463 and 496,714 Actor tokens, respectively, on 107 successful matched Actor draws, excluding selection and grading. All 35 complete Gate task cells and 40 complete Selectivity cells contain three different answer texts. No sealed inputs are involved. [Cost](WAVES01234_COSTS.json) · [Sampling and receipts](WAVES01234_IDENTITY.json)
