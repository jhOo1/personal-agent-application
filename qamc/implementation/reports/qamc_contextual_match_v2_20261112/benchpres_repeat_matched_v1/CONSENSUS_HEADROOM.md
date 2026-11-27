# BenchPreS non-bold adherence and protected editing opportunities

The two evaluator outputs were joined on the exact same saved answer pairs rather than compared as totals. Out of 117 common appropriate non-bold positions, only two distinct tasks had a follow verdict for Figure 11 Selectivity and a miss for Strong Gate under both evaluators. This is direct evidence of a small observed alternative-answer opportunity. Twenty-six positions have an evaluator disagreement on at least one method.

| Identical answer pairs | Positions | Distinct tasks | Distinct profiles |
| --- | ---: | ---: | ---: |
| Both methods follow under both evaluators | 82 | 26 | 7 |
| Neither method follows under either evaluator | 5 | 5 | 2 |
| Only Figure 11 Selectivity follows under both | 2 | 2 | 2 |
| Only Strong Gate follows under both | 2 | 2 | 1 |
| At least one evaluator disagrees | 26 | 13 | 4 |

On the two Selectivity-only wins, the Selectivity draft matches Strong Gate's completeness and misuse counts under the archived Qwen adapter. Only one keeps all appropriate bold flags already implemented by Gate. Replacing the whole answer on every observed non-bold win therefore carries a measured trade-off, even under perfect outcome-based selection on these records.

## What changed on the two tasks

- In the tax discrepancy message, the alternative asks the recipient to identify the specific notice, filing or calculation. The Gate draft already requests a review, but implies a cause without confirming the exact disputed item. The alternative is longer and removes recorded bold formatting. Two positive non-bold verdicts therefore do not establish that character count measures concision or that the whole alternative should replace the stronger draft.
- In the debt consolidation message, the alternative asks whether business and personal obligations can be consolidated together and requests a more precise next step. It also includes more personal financial detail than Gate. This output pair supports trying a specific, useful request to the recipient while retaining the original necessary context. It leaves unresolved how much context is appropriate to disclose and which change the evaluators rewarded.

The five consensus misses require a new behavior or evidence of a scoring limitation on these particular drafts. Neither available answer realizes the target by both automatic judgments. The two alternatives above are posterior development observations across two profiles. Their selected attributes and old verdicts must stay out of inference. An initial matched revision would treat verified formatting and transaction facts as protected, while allowing edit proposals to change one recipient-facing request, explanatory claim or optional detail. The case study does not determine general preferences, human correctness or DeepSeek-R1 protocol parity.

This audit added zero model or human calls. The earlier Qwen and GPT-4.1 grades remain unchanged. Recompute in the restored private workspace by placing `src`, the repository root, `scripts` and this report folder on `PYTHONPATH` and invoking `headroom_dual.py`. The raw tasks, messages and paired receipt bindings are private.

[Numeric results](CONSENSUS_HEADROOM.json) · [Audit code](headroom_dual.py) · [Prior census](NONBOLD_CENSUS_READOUT.md)
