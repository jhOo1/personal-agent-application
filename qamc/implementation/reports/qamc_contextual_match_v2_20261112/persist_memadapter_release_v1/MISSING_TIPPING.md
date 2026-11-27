# What would the unresolved MemAdapter outcomes have to show?

Use all 29 allocated exposed sources and the original strict source-level pass rule. For risks, any observed failed draw settles that source as failed, even when another draw is missing. For strict beneficial use there is one draw per source. Count how many of the *currently unresolved external sources* would have to fail for the internal arm to have strictly more passes. The two values correspond to every unresolved internal source passing or every unresolved internal source failing. They describe hypothetical completions of the original allocation. A new deployment cannot reveal an undelivered historical answer.

| Track and comparison | Unresolved external sources | GPT-4.1 threshold | Qwen threshold |
|---|---:|---:|---:|
| Strict beneficial use, SELECTED vs MemAdapter | 7 | 1 / 2 | 4 / 6 |
| Strict beneficial use, BREADTH vs MemAdapter | 7 | 1 / 2 | 3 / 5 |
| Sycophancy, either internal arm vs MemAdapter | 5 | 1 / 4 | 0 / 3 |
| Cross-domain, either internal arm vs MemAdapter | 1 | 1 / 1 | 1 / 1 |

For example, under Qwen the breadth arm has 16 confirmed utility passes and 2 unresolved. The external arm has 13 confirmed passes and 7 unresolved. With every internal unknown passing, at least 3 of the 7 external unknowns must fail for 18 internal passes to beat the external count. If both internal unknowns fail, at least 5 external failures are required. All seven external sources previously yielded passing archived answers. Earlier success motivates caution about a missing-as-failure analysis; it does not determine the outcomes of the current deployment.

The strict-utility comparison under Qwen is the clearest reason to prioritize improving actual delivered answers over repeating failed external calls: on the 12 common graded utility sources BREADTH already has zero wins and one loss. A larger output budget would change the deployment contract and requires a separately identified comparison. Keep the common-pair loss, missing records, and prior external successes. No new inference or scoring.

[Original paired comparison](DECISION.md) · [Observed common-pair loss](UTILITY_EXTERNAL_WIN.md) · [Read-only computation](missing_tipping.py)
