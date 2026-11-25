# PersistBench author-control terminal results

This author-control stage is complete; the overall research Goal is not. All 13 saved waves replay identically with model initialization and HTTP blocked. No new calls or score changes were made by this report.

## Scope and comparability

60 exposed development roots, six methods, one development generation per cell. Generator/selector alias: qwen3.8-flash, temperature 0; adapted GPT-4.1 FR@1 grading. Model aliases are not certified weights. This does not reproduce the native repeated-generation Kimi/Google Vertex protocol and does not establish held-out SOTA. GEPA uses the released optimized prompt, without rerunning its optimizer. The filter uses the complete released prompt and a strict local original-string subset parser; native-runner parity is not claimed. PB_FILTER_COMMON uses the shared Actor; PB_FILTER_NATIVE uses the author presentation. Their differences are a combined presentation/prompt contrast, not an isolated filter effect.

## Full available-score table

Entries are failures / valid roots; lower failure is better in each category. Different denominators must not be compared as if the same cases were available.

| Method | Answers / 60 | Valid / 60 | Cross-domain | Sycophancy | Beneficial-use failure |
|---|---:|---:|---:|---:|---:|
| PB_FILTER_COMMON | 54 | 54 | 6/18 | 16/17 | 0/19 |
| PB_FILTER_NATIVE | 49 | 49 | 4/16 | 7/13 | 0/20 |
| PB_FULL | 50 | 50 | 2/18 | 9/14 | 0/18 |
| PB_GEPA | 51 | 51 | 2/19 | 8/14 | 0/18 |
| PB_NO_MEMORY | 51 | 51 | 1/17 | 2/14 | 9/20 |
| PB_RUBRIC | 50 | 50 | 1/20 | 5/12 | 0/18 |

## Same-root paired comparisons

Right better/worse counts mean fewer/more failures on common valid roots only. They are development diagnostics, not significance claims.

| Left | Right | Category | Common | Left failures | Right failures | Right better / worse / tie |
|---|---|---|---:|---:|---:|---:|
| PB_FULL | PB_GEPA | cross_domain | 17 | 1 | 2 | 0 / 1 / 16 |
| PB_FULL | PB_GEPA | sycophancy | 13 | 9 | 7 | 3 / 1 / 9 |
| PB_FULL | PB_GEPA | beneficial_memory_usage | 18 | 0 | 0 | 0 / 0 / 18 |
| PB_FULL | PB_RUBRIC | cross_domain | 18 | 2 | 1 | 1 / 0 / 17 |
| PB_FULL | PB_RUBRIC | sycophancy | 12 | 7 | 5 | 2 / 0 / 10 |
| PB_FULL | PB_RUBRIC | beneficial_memory_usage | 18 | 0 | 0 | 0 / 0 / 18 |
| PB_FULL | PB_FILTER_NATIVE | cross_domain | 15 | 2 | 4 | 0 / 2 / 13 |
| PB_FULL | PB_FILTER_NATIVE | sycophancy | 13 | 8 | 7 | 1 / 0 / 12 |
| PB_FULL | PB_FILTER_NATIVE | beneficial_memory_usage | 18 | 0 | 0 | 0 / 0 / 18 |
| PB_FULL | PB_FILTER_COMMON | cross_domain | 16 | 2 | 6 | 1 / 5 / 10 |
| PB_FULL | PB_FILTER_COMMON | sycophancy | 13 | 8 | 12 | 0 / 4 / 9 |
| PB_FULL | PB_FILTER_COMMON | beneficial_memory_usage | 17 | 0 | 0 | 0 / 0 / 17 |
| PB_FULL | PB_NO_MEMORY | cross_domain | 16 | 2 | 1 | 2 / 1 / 13 |
| PB_FULL | PB_NO_MEMORY | sycophancy | 13 | 8 | 1 | 7 / 0 / 6 |
| PB_FULL | PB_NO_MEMORY | beneficial_memory_usage | 18 | 0 | 8 | 0 / 8 / 10 |
| PB_FILTER_NATIVE | PB_FILTER_COMMON | cross_domain | 16 | 4 | 6 | 1 / 3 / 12 |
| PB_FILTER_NATIVE | PB_FILTER_COMMON | sycophancy | 13 | 7 | 12 | 0 / 5 / 8 |
| PB_FILTER_NATIVE | PB_FILTER_COMMON | beneficial_memory_usage | 19 | 0 | 0 | 0 / 0 / 19 |

## All-six common subset

```json
[
  {
    "category": "cross_domain",
    "common_roots": 13,
    "failures": {
      "PB_FILTER_COMMON": 6,
      "PB_FILTER_NATIVE": 3,
      "PB_FULL": 1,
      "PB_GEPA": 1,
      "PB_NO_MEMORY": 1,
      "PB_RUBRIC": 0
    }
  },
  {
    "category": "sycophancy",
    "common_roots": 11,
    "failures": {
      "PB_FILTER_COMMON": 10,
      "PB_FILTER_NATIVE": 6,
      "PB_FULL": 7,
      "PB_GEPA": 6,
      "PB_NO_MEMORY": 1,
      "PB_RUBRIC": 5
    }
  },
  {
    "category": "beneficial_memory_usage",
    "common_roots": 17,
    "failures": {
      "PB_FILTER_COMMON": 0,
      "PB_FILTER_NATIVE": 0,
      "PB_FULL": 0,
      "PB_GEPA": 0,
      "PB_NO_MEMORY": 7,
      "PB_RUBRIC": 0
    }
  }
]
```

## Missingness and accounting

360 cells: 305 successful answers and 305 valid scores; 55 NA. Actor statuses: {"OK": 305, "FAILED": 41, "PRIOR_ATTEMPT_RETAINED": 10, "UNISSUED": 4}. All successful answers have valid scores. UNISSUED cells are the two nonverbatim filter contracts affecting four Actor cells, documented separately. Retained prior attempts are not new calls and are not rerun.

This namespace made 587 real requests: {"OK": 546, "KNOWN_LENGTH_FAILURE": 38, "FAILED_DELIVERY_UNKNOWN": 3}. Known provider-reported total tokens: 4,809,264; 3 calls have unknown usage, not zero. These are stage-only physical counts, not whole-Goal costs. Cached/imported/aliased logical outputs are not independent new generations. No pending physical records remain. Length-truncated answers are NA, and delivery-unknown requests were not resent.

## Interpretation and next step

No-memory removes useful personalization in beneficial-use cases; it cannot serve as a universal solution merely because it has fewer cross-domain or sycophancy failures. Compare the paired tables before attributing differences to method design. The common/native filter presentation contrast is material and must not be reduced to a claim that memory filtering alone helps or hurts. The observed rankings remain development results with missing cells and adapted automated scoring. No uniform method is promoted by this control stage.

The already-frozen draft-origin four-method window is the next running experiment. Its own gates, fixed candidates, and controls remain in force; this report does not change its prompts, allocation, or confirmation boundaries.

Plan file SHA-256: `c18003a4a00262fda7f38f4e86944f51569f0afab81a7eb11a45a2c000b9f9ff`. Immutable summary: `reports/qamc_contextual_match_v2_20261112/persist_author_controls_v2/terminal_summary_v1/5a62cdfc5b4ea40513ef07f93c900a1be709bf41c8941481892b60e0ab115bb1.json`.
