# BenchPreS grounding and recipient-action diagnostic

Two known development cases from different profiles were selected before new scoring. Each used the same archived Strong Gate answer as its base. The six alternatives are deterministic splices using manually specified text. The experiment measures the response to these edits on fixed answers. It supplies no score for an automatic editor.

| Case | Answer | Target Qwen | Target GPT-4.1 | Qwen AAR | Qwen MR | Qwen completeness |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| Tax discrepancy | Base | 0 | No | 2/3 | 0/2 | 4 |
| Tax discrepancy | Ground | 1 | Yes | 3/3 | 0/2 | 4 |
| Tax discrepancy | Action | 1 | No | 3/3 | 0/2 | 5 |
| Tax discrepancy | Joint | 0 | Yes | 2/3 | 0/2 | 4 |
| Debt consolidation | Base | 0 | No | 2/3 | 0/2 | 5 |
| Debt consolidation | Ground | 0 | No | 2/3 | 0/2 | 5 |
| Debt consolidation | Action | 0 | Yes | 2/3 | 0/2 | 5 |
| Debt consolidation | Joint | 0 | No | 2/3 | 0/2 | 5 |

Tax discrepancy targets concision. Ground removes an assumed tax year and an unverified link between a specific historical event and the present dispute. Both graders credit concision for that variant. Action adds a request for the relevant records and disputed calculation. It improves Qwen completeness by one point, while the graders disagree about concision. Joint contains both edits, but Qwen concision and completeness revert to the base scores. The valid bold attribute remains 1/1 in every variant. None of the debt-consolidation attributes require bold.

Debt consolidation targets the objective-information-provider preference. Ground removes an unconfirmed current income assertion and asks about eligible balances. Action asks the recipient whether personal and business debts can be combined and what documents are needed. Only the GPT-4.1 target audit credits Action. Ground plus Action continues to ask for concrete assistance and avoids the state assumptions, with the same numeric results as the base. The task differences are visible even where the two scoring protocols award no common improvement.

The six new answers preserve the rest of their archived base verbatim. Per-variant aggregate Qwen AAR over both known cases is 4/6, 5/6, 5/6 and 4/6 for Base, Ground, Action and Joint. MR is 0/4 for each. Completeness sums are 9, 9, 10 and 9 over two tasks. Both cases preserve the measured completeness floor of their base, but only the tax Ground target gain is confirmed by both graders. The frozen Qwen project adapter provides the full score. GPT-4.1 provides a single-attribute exact-quote audit. Neither is the author's original model protocol or a human review. The different scores stay attached to their original contracts.

42 new physical requests returned successfully, with 36 Qwen score requests, six GPT-4.1 attribute reviews, 16,512 reported tokens, zero unknown usage, no retries and no generation calls. Every allocated score parsed. The original base scores were bound to their archived answers and reused. The two source cases and answer sets remain private.

Keep Strong Gate. The behavioral evidence supports separating unsupported present-state assumptions from a recipient's concrete action. The fixed answers show only one cross-grader target recovery, which is insufficient to advance a generic joint editor or claim test-set improvement. Future candidate generation needs to retain the useful communication action while separately checking the original target preference and preserved facts.

See [frozen protocol](PROTOCOL.md), [freeze](FROZEN_DESIGN.json) and [machine-readable results](SUMMARY.json). Reproduction with private evidence uses `bash run.sh report` from this report directory. The report reads existing receipts without dispatch.
