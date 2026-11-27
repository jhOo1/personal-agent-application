# Fixed-answer model reflection diagnostic

This is a separate automated robustness check on the BenchPreS repeat comparison. It keeps the original Qwen labels and does not substitute for independent human judgments. Every input contains one preference and one exact saved answer. Author appropriateness, the original verdict, method identity, task grouping and research findings are kept outside the model request.

The panel freezes 14 distinct exposed tasks across nine profiles before independent model outputs. It contains two pairs per direction of Qwen non-bold disagreement, three shared non-bold misses, two shared non-bold successes, three non-nickname misuse disagreements, and two nickname disagreements as observable controls. Selection prefers profiles with fewer chosen cases, then uses opaque-seed hashes. Every pair has complete original Qwen grades. The panel is enriched for disagreement and cannot estimate benchmark-wide accuracy, MR or AAR.

Both arms use the same single-attribute evaluator and retained GPT-6.1-sol minimal streaming configuration. No explicit temperature or output cap is sent on this transport. A usable reply requires the expected alias, a completed stream and an exact-quote-validated ternary classification. Unknown delivery and malformed outputs remain in the ledger. A one-minute cooldown separates a failed attempt from another not yet dispatched. A second consecutive failure or authentication rejection ends this small diagnostic. No former request is retried. The maximum is 28 calls and no new Actor answer.

Use [the diagnostic runner](run_reflection_model.py) from the original checkout with the existing blind inventory, private seed, transport helper `phase2_7_rpeval_scoring_attribution_20261116/gpt61_blind_review_v1/nonstream_probe.py`, and the current authorized service. The original answer and Judge records remain in place. The public archive contains the selection rules and aggregate only. [Frozen answer inventory](REFLECTION_VALIDATION.md)

## Retained first attempt and completion-parser revision

The first two requests ended under the original parser. One stream returned the requested alias, a completion marker and finish reason `completed`, which the parser had restricted to `stop`. Another returned a stream error and no model alias. Neither yields an accepted vote. The first reply body was not retained by the original parser, so that result cannot be recovered locally.

The revised parser accepts `completed` or `stop` only with the requested alias, complete stream, and valid label and quote contract. It retains safe visible replies even when they fail validation. This revision applies only to unissued requests from the same frozen 28-item plan. It keeps the original two records and the one-minute cooldown. The original stop marker remains in place. The revised parser writes its own terminal marker and never reissues a registered request.
