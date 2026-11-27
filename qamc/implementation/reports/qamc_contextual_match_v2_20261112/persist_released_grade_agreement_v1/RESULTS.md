# Same-answer comparison against released PersistBench ratings

All 65 first draws come from the author's unfiltered single-turn external baseline release. The 13 matching exposed roots each contribute five models. The release identifies the judge as Kimi K2 Thinking via OpenRouter. The project uses its frozen GPT-4.1 adaptation. Only the answer, original query, memories and grading instructions enter the project judge.

| Category and rule | Roots | Assigned | Valid | Exact ordinal | Same decision | Only Kimi passes | Only project passes |
|---|---:|---:|---:|---:|---:|---:|---:|
| beneficial_memory_usage, strict | 7 | 35 | 35 | 28 | 28 | 0 | 7 |
| beneficial_memory_usage, relaxed | 7 | 35 | 35 | 28 | 35 | 0 | 0 |
| cross_domain, single draw | 4 | 20 | 20 | 14 | 17 | 3 | 0 |
| sycophancy, single draw | 2 | 10 | 10 | 8 | 10 | 0 | 0 |

Physical grading requests: 65. Status: {'OK': 65}. Reported tokens: 381,052; unknown usage: 0. No new Actor requests.

The agreement counts describe these answers. A high agreement on predominantly passing answers does not establish sensitivity to failures. Model outputs share roots. Neither a three-draw risk failure rate nor official Kimi grades for QAMC can be inferred from this comparison.

[Freeze](PROTOCOL.md) · [Grader and matching](trial.py) · [Ordinal counts](ORDINAL.json)
