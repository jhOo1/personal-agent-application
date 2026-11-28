# Benchmark roles and a same-answer scoring audit

## Scope recommendation

Keep RPEval and PersistBench as primary evaluations for a training-free method controlling the influence of fixed history. Keep BenchPreS's complete scores as a formal-delivery and appropriate-expression check. Use the existing cohorts and scoring adaptations. This recommendation narrows the proposed paper claim and experiment priority. It does not remove an existing evaluation or establish a combined ranking.

- **RPEval:** In the matched exposed 274-task panel, selective IPE-C scored 953/1,462 versus 874/1,462 for the exact no-history endpoint and 824/1,462 for the full-history RP reconstruction. The small mixed-preference comparison of itemwise selection versus the whole-history gate tied at 41/71, with OPB respectively 16 and 12. This supports selective exposure on the large panel and leaves the value of itemwise selection unresolved.
- **PersistBench:** The first draw on ten additional exposed roots yielded eight jointly scored cases for SELECTED and the same-signal GROUP gate, with 7/8 and 6/8 passes. The single disagreement was the yoga studio scenario. The source identifying the requester as a mentor was compatible with preserving the founder's choice, and the empty-history answer also passed. On the two strict beneficial-use roots, the surviving history-enabled answers passed while EMPTY failed both. There were two exact overlaps with the released author runs, with ties against the best matched saved answers on the adapted scorer. These are reasons to continue measuring both risk and benefit, with broader competitive and repeat evidence still required.
- **BenchPreS:** Strong Gate scored 38/44 AAR and 1/86 MR on 26 common tasks. The six missed appropriate realizations came from the concise and objective-expression profiles. Gate received the applicable preference verbatim in five of the six cases. The archived three-path protected upper bound was also 38/44. A separate fixed implementation of MemAdapter scored 23/40 AAR on the 24 shared tasks where Gate scored 34/40. The last two observations concern specific candidate pools and do not prove general benchmark saturation. The prior source audit found zero reference applicability flips among 37,050 same-preference within-profile task pairs in the locked release. That limits what the benchmark can demonstrate about contextual flips, while its formal-delivery scoring addresses an important failure the other two benchmarks do not directly target.
- **PairPref as a candidate:** The paper reports 1,227 pairs across 45 preferences, with fixed request and preference and a change in situation, plus selection and free generation. This is relevant if a controlled applicability flip becomes the paper's primary mechanism. The available paper was verified. Author-distributed rows and a runnable evaluator were not independently verified. The free-generation track also uses automatic grading and does not close the formal-delivery measurement gap, so there is no qualified replacement for BenchPreS in this role.

Retain the current dataset scope and sealed boundary. Allocate additional performance work to the mechanism with a demonstrated matched advantage. Re-open a BenchPreS method experiment if the intervention addresses realization from already-visible evidence and can be tested on distinct profiles with the required facts, MR and completeness protected. Add a replacement only when its runnable public protocol and matched strong opponents are verified and it addresses a material gap in the paper's question.

## Zero-call audit of archived RPEval scores

The complete exposed 300-task IPE-C endpoint panel contains 120 author all-A tasks. 118 had a valid saved no-history answer and grade. For each, the audit verifies the exact Actor request hash, cached response bytes, empty `source_evidence` and `preference_use_policy`, and reconstructed Judge wire and strict grade. The Actor request may contain fixed current-context or task facts. Groups fix Actor request, verbatim answer and the author all-A position count. Repeated identical Judge wires are counted only once in each group.

| Quantity | Count |
|---|---:|
| Distinct exact Actor-and-answer groups | 49 |
| Groups with multiple distinct Judge wires | 7 |
| Distinct Judge-wire pairs in those groups | 14 |
| Pairs with different Match counts | 4 |
| Pairs with positive versus zero UPB | 4 |
| Pairs with positive versus zero OPB | 0 |
| Pairs with neither grade carrying a known score flag | 8 |
| Unflagged pairs with different Match counts | 0 |

The four Match differences come from one group and are not independent errors. Identical no-history answers scored 4/4 under some judging inputs and 0/4 with UPB 5 under others. The latter grades were already flagged. The Judge requests can differ in more than the historical evidence representation, and provider sampling is uncontrolled. This identifies a concrete scoring sensitivity without explaining the overall RPEval ranking or the increase in OPB in the mixed-preference comparison. Original grades remain intact. This audit made zero API calls and did not touch sealed data.

To reproduce in the restored private research workspace, load the Python path from the `evo_qamc_fit_v1/run.sh` launcher and execute `same_answer_grade_audit.py` using the project interpreter. The audit reads the exposed-only archived lineage under `ipe_c_two_endpoint_completion_v1` and `ipe_c_full_exposed_panel_v1`. Public copies contain the script and aggregate counts, without private receipts or answers.

Sources and adjacent evidence are indexed in [Benchmark scope review](BENCHMARK_SCOPE_REVIEW.md) and [No-history RPEval grades](NO_HISTORY_RPE_GRADES.md). See the [RPEval author release](https://github.com/XueyangFeng/RPEval), [BenchPreS paper](https://arxiv.org/html/2603.16557), [PersistBench author release](https://github.com/ivaxi0s/PersistBench) and [PairPref paper](https://arxiv.org/html/2609.34526v1).
