# BenchPreS diagnostic on grounding and recipient action

Use the two known independent-profile, Qwen/GPT-4.1 agreement cases from the fixed Strong Gate versus Figure 11 Selectivity census. The cases are a tax discrepancy email and a debt consolidation inquiry. Each candidate is a manually specified, localized edit to the exact Strong Gate completion from draw 2. This is a mechanism diagnostic on known development cases. The variants do not constitute an automatic editor or an estimate of test-set performance.

| Arm | Calibrate an unconfirmed present-state or causal assertion | Add a concrete recipient request |
| --- | --- | --- |
| BASE | No | No |
| GROUND | Yes | No |
| ACTION | No | Yes |
| JOINT | Yes | Yes |

The two edit families are bound to disjoint exact source spans. The compiler preserves all remaining bytes and the original supported emphasis. In the tax message, GROUND removes the assumed year, unconfirmed cause and unsupported linkage to particular materials. ACTION asks which record or calculation is disputed and which material is needed. The recipient can respond without the letter claiming an identified cause. In debt consolidation, GROUND changes assumptions about current balances and income into an inquiry about eligible balances. ACTION asks whether personal and business obligations may be combined and what documentation is needed for prequalification. It adds no budget or balance claims. The exact source texts, author fields and manual span edits stay private. The public configuration records their hashes.

Freeze all six variants before new grading. Base grades are exact archived outcomes and are reused. Apply the established full-answer Qwen BenchPreS adapter per new answer, using all five attribute slots and the completeness score. Apply the same frozen GPT-4.1 reflection adapter to the target attribute only, with the original exact-quotation contract. Report AAR, target and other appropriate outcomes, MR, completeness, missing fields, and the actual fact/recipient/action changes. The two automated judges have distinct contracts and provide no human truth labels. Compare each pair at its native grading allocation. Report disagreement as observed rather than changing grades.

Call ceiling is 36 full-protocol Qwen scoring requests and six single-attribute GPT-4.1 requests, with zero generation calls. Exact request reuse can reduce physical calls. No generation or selection stage consumes target labels or old scores. No other historical input or sealed case is read to produce these variants. A stable gain here can motivate an automatic source-grounded editor on a broader matched development panel. It does not establish general advantage.

Reproduce in the private checkout with `bash reports/qamc_contextual_match_v2_20261112/bench_action_grounding_diagnostic/run.sh report`. The restored run directory must contain the exact `MANUAL_EDITS_PRIVATE.json` and output inventories. [Evidence and previous paired result](../benchpres_repeat_matched_v1/CONSENSUS_HEADROOM.md)
