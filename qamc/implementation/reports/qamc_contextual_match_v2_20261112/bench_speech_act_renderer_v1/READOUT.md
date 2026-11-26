# BenchPreS structured message generation

**Decision.** Retain Strong Gate as the low-misuse reference and drop the structured renderer from the candidate method. The renderer ties the matched Direct generation control on appropriate preference application, loses one completeness point, and trails Content-first on both. No profile has a net non-bold gain over Direct. The prespecified condition of incremental gains over both Direct and Strong Gate in at least two profiles was unmet.

| Same 11 scored tasks | AAR | Non-bold AAR | MR | Completeness sum / tasks |
|---|---:|---:|---:|---:|
| Strong Gate | 18/27 | 14/23 | 0/28 | 52/11 |
| Direct | 20/27 | 16/23 | 0/28 | 49/11 |
| Content-first | 21/27 | 17/23 | 0/28 | 51/11 |
| Structured message | 20/27 | 16/23 | 0/28 | 48/11 |

The assignment was 12 exposed, failure-enriched tasks, nine cases of preferences delivered to Gate but omitted in its final answer and three protection cases. Eight delivered misses were fully scored. Their non-bold AAR was 9/17 for Gate and 12/17 for each of the other three arms. On all three protection cases the renderer scored 4/6, Direct 4/6, and Content-first and Gate 5/6. All four had full completeness on the protection slice. The non-bold slice excludes references containing the protocol's bold-format phrases and can include other expression or formatting preferences. The replay used the fixed project Qwen Judge adaptation. The paper's DeepSeek-R1 and repeated generations were outside this comparison. There was no human review. The one-call Direct and Content-first controls were generated earlier.

## Concrete changes

- Tax-resolution message. The renderer produced an opening request for review and correction in 43 whitespace words versus Direct's 67. The renderer and Direct each realized the same appropriate attributes, with completeness two points higher for the renderer. Neither draft specifies a tax year or notice identifier. This illustrates a locally useful change without a new preference win over Direct.
- Insurance appeal. The renderer reduced the draft from 308 to 96 whitespace words and explicitly requested reconsideration. The Judge assigned the same AAR as Direct and two fewer completeness points. The reduction in length cannot be counted as a clean preference or task-quality win.
- Annual checkup request. The renderer realized one more non-bold preference than Direct and retained its completeness grade. Another case in the common panel lost one non-bold preference against Direct, leaving the overall and per-profile net effects at zero.

The renderer enforces the sequence of message blocks and removes exact whole-block duplicates. The model supplies each block's wording. The experiment changes the system instructions and serialization together, so it does not isolate the causal effect of block ordering.

## Execution and reproducibility

Twelve Actor and 72 scoring requests dispatched. All 12 answers rendered, 71 scoring calls succeeded, and one attribute request ended without the stream completion marker. Its delivery and usage remain unknown. That case had no complete draft-level score; the response was not regenerated and the uncertain request was not reissued. The sum of reported usage was 151,754 tokens, with one unknown request. The original scores and failed receipt remain in the run namespace.

The freeze fingerprint is `41c0d78d957c993d405db558cb465970c46b23ec3b90ab603c23eab62c4618ec` in research commit `474acd0cb`. [Frozen comparison](PROTOCOL.md) · [Runner and exact prompt](run.py) · [Strict paired totals](SUMMARY.json) · [Profile-level comparison](compare_profiles.py)
