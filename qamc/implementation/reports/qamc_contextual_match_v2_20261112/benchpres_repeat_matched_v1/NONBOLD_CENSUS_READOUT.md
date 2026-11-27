# BenchPreS non-bold preferences under a second evaluator

The complete planned single-attribute re-evaluation of saved answer pairs has settled. Both scoring procedures return a small and uncertain advantage for different methods on the same 117 positions. This result supports evaluator sensitivity and does not establish an advantage for either method on non-bold preferences. The earlier large difference in nickname use can be directly checked in saved texts and was measured separately. [Frozen protocol](NONBOLD_CENSUS_PROTOCOL.md) · [Literal nickname trace](REFLECTION_LITERAL.json)

| Scope and scorer | Strong Gate | Figure 11 Selectivity | Gate minus Selectivity |
|---|---:|---:|---:|
| Strict common positions, original Qwen | 91/117 | 94/117 | −3 |
| The same strict common positions, GPT-4.1 | 106/117 | 104/117 | +2 |
| All jointly judged GPT-4.1 positions | 111/123 | 109/123 | +2 |

The exact 117-position intersection covers 29 tasks and seven profiles. Exploratory percentile intervals from 5,000 profile-cluster resamples are −7.87 to +6.93 percentage points for the original Qwen Gate contrast and −1.84 to +9.47 for GPT-4.1. The change in contrast is +4.27 points, with an exploratory interval of +0.94 to +7.84. Only three of seven profiles contribute to this shift and the other four tie. The primary measurement cannot resolve a ranking. The follow-up excluding the earlier diagnostic tasks has 63 positions, 17 tasks, and seven profiles. Gate's net difference is −5 with Qwen and +1 with GPT-4.1, with each evaluator's within-procedure contrast still spanning zero. [Profile replay](NONBOLD_CENSUS_PROFILES.json)

Across the available fixed answers, agreement with Qwen is 108/126 for Strong Gate and 109/125 for Selectivity. Cohen's κ is 0.481 and 0.550, respectively. Qwen no to GPT-4.1 yes flips are 17 for Gate and 14 for Selectivity, compared with one and two in the reverse direction. The masked GPT-4.1 packet contains the single preference text and complete answer. It omits the task context, original methods, and labels. Judge model and presentation both differ, so the contrast cannot be attributed to model identity alone. GPT-4.1 is an automatic diagnostic, with zero human reviews and no DeepSeek-R1 protocol parity. The existing Qwen grades remain unchanged.

The frozen allocation is 153 positions. Both Actor answers exist for 129. GPT-4.1 yielded a valid binary judgment from both arms on 123 positions. In the fixed 129-pair scope, arbitrary outcomes for the ungraded positions bound the Gate minus Selectivity gap to 0 to +6. Retaining all 153 positions, including those without both Actor answers, widens the bound to −24 to +30. No result is imputed or substituted for a missing original answer.

There were 258 logical scoring jobs and 18 exact-request and same-service cache matches. All 240 new requests returned. Six failed the original exact-quotation contract, three per arm. They were excluded as unavailable. No request was resent. The gateway reported 82,967 tokens with zero unknown usage. No Actor request or human annotation was added. [Numeric report](NONBOLD_CENSUS_RESULTS.json) · [Execution and replay](run_reflection_nonbold_census.py)
