# Symmetric delivery fallback on the 49 exposed roots

This is an offline exact-answer replay. Both policies must budget for both pipelines. The branch uses successful delivery of a nonempty primary Actor response only. It never considers a score. Reversing which answer has priority gives a fair control with the same two pipelines. Archived responses approximate available alternatives; concurrency and delivery times were not measured prospectively.

| Track | SELECTED-first vs RUBRIC-first, GPT-4.1 | SELECTED-first vs RUBRIC-first, Qwen |
|---|---|---|
| Sycophancy, 12 roots | 11 vs 4 pass, 7 wins / 0 losses | 12 vs 8 pass, 4 wins / 0 losses |
| Cross-domain, 19 | both 16 pass / 1 fail / 2 unknown | 16 vs 17 pass, 3 vs 2 unknown; all 16 common tie |
| Strict beneficial use, 18 | both 18 pass | 15 vs 14 pass, 2 wins / 1 loss / 15 ties |

All 36 risk deployments for sycophancy had both answers. The entire sycophancy advantage is inherited from the original choices. Six utility deployments had only a RUBRIC answer, so both policies returned that exact same answer. The other twelve had both. On these six shared fallback answers GPT-4.1 passed six and Qwen passed four. An observed full-roster utility comparison for this two-pipeline policy does not repair the six historically missing SELECTED generations, estimate single-pipeline utility, establish noninferiority, or constitute a new deployment. No new requests.

[Rule frozen before replay](PROTOCOL.md) · [Implementation](replay.py) · [Aggregate scores and availability](SUMMARY.json)
