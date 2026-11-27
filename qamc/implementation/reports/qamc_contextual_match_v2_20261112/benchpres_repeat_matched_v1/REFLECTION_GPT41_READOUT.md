# Fixed-answer BenchPreS comparison across two evaluators

All 28 GPT-4.1 requests completed and returned usable votes, giving 14 paired attribute judgments over 14 source-distinct tasks and nine profiles. The answer text, single-attribute review prompt and 14 pairs were frozen before independent model output. The original Qwen observations and failed GPT-6.1-sol requests remain separate. [Protocol](REFLECTION_GPT41_PROTOCOL.md) · [Original route settlement](REFLECTION_MODEL_READOUT.md)

| Selected stratum | Pairs | Original Qwen Gate / Selectivity “yes” | GPT-4.1 Gate / Selectivity “yes” |
| --- | ---: | ---: | ---: |
| Appropriate non-bold | 9 | 4 / 4 | 7 / 7 |
| Inappropriate non-nickname | 3 | 0 / 3 | 0 / 2 |
| Inappropriate nickname | 2 | 0 / 2 | 0 / 2 |

The evaluators agree on 21 of 28 votes. All six non-bold changes are Qwen “no” to GPT-4.1 “yes”. Both originally Gate-only pairs become “yes” for both arms. One of two originally Selectivity-only pairs also becomes “yes” for both. Two of the three shared non-bold misses acquire at least one positive vote. The two shared-success pairs remain positive. On this panel, the equal non-bold totals survive the evaluator change while several individual outcomes depend on the evaluator. The non-nickname disagreement is an expressive-tone attribute. Both nickname controls retain the original judgments. [Paired vote transitions](REFLECTION_GPT41_RESULTS.json)

This is an enriched measurement audit. It provides a direct comparison of two automated judgments on fixed answers and cannot determine which evaluator is correct, estimate disagreement on all BenchPreS tasks, or establish causal policy advantage. The exact quote requirement is a provenance check on the cited excerpt. It cannot prove correct semantic interpretation. The all-available-answer literal check remains separately interpretable. [Literal occurrences](REFLECTION_LITERAL.json)

There were 28 physical Judge calls, 9,530 reported tokens, zero unknown usage, zero retries, zero Actor calls and zero human judgments. No original grades were replaced and no sealed data were accessed. Raw review requests and returned quotes remain private.
