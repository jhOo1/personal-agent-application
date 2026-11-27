# Joint delivery on the same BenchPreS answer

Retrospective diagnostic using the frozen three-action matrix. A single saved answer qualifies when all applicable preferences are realized, no inapplicable preference is used, and completeness is 5/5. A sensitivity row accepts completeness of at least 4. This conjunction is an additional diagnostic computed from the archived Qwen adaptation. The three native component metrics stay separate.

| Minimum completeness | Task only | Full RP | Strong Gate | Gate alone passes | Distinct Gate-only profiles |
|---|---:|---:|---:|---:|---:|
| 5 |2/26|8/26|19/26|9/26|5|
| 4 |3/26|9/26|19/26|8/26|5|

26 of 48 exposed tasks have three complete score records, across nine profiles. The remaining 22 are unranked. In all nine strict Gate-only tasks, task-only missed at least one applicable preference. RP produced an observed misapplication in three of the nine, missed applicable preferences in five (including one with a misapplication), and lost on completeness alone in two. No strict Gate-only answer had a higher count of non-bold applicable preferences realized than both alternatives. This comparison concerns full methods with different prompts; it cannot isolate selection or prove a general advantage in non-bold expression.

For example, on development source 29b7ae84 all three answers received 5/5 completeness. Task-only implemented one of two applicable attributes with no misuse. RP implemented one with one misuse. Gate implemented both with no misuse. Each realized one non-bold attribute, so the extra appropriate attribute reflected in Gate's count was bold formatting. This example does not establish independent human agreement.

BenchPreS thus contains measurable within-answer cases that a three-arm risk-only comparison can miss. This supports retaining it as an expression and task-delivery boundary, and keeping Gate as the reference. These are exposed examples and no evidence that a new QAMC component improves Gate. Source of the paired records: private research checkout, sibling paired_regret_policy_v1/MATRIX.json (build_matrix.py validates the common attribute definition). Only aggregate outcomes and a short development source prefix are published.
