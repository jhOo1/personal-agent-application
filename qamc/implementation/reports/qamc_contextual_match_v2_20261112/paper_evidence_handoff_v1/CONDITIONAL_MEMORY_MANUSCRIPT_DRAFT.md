# When Should a Personalized Assistant Use Its History?
## Task-Level Memory Activation and the Limits of Preference Realization

**Working manuscript.** Results below are from exposed development data with documented scorer adaptations. Independent confirmation and author-protocol comparisons are open.

### Abstract

A retrieved preference can help a personalized assistant fulfill the current request or distort a decision that should be driven by the task. We study how much of this tradeoff can be addressed by deciding whether to activate history, with the candidate memory and generation backbone fixed. On the 300 author-released RPEval multi-preference tasks, 274 have strict scores for three pre-existing answer paths. A training-free rule that activates history when the intent estimator predicts at least one dominant preference obtains 953/1,462 position matches, compared with 874 for always answering without history and 824 for always answering with history. These comparisons expose different failure modes. Activation preserves many matches on tasks with dominant preferences relative to always excluding history. Exclusion accounts for nearly all of the gain over always including history. The rule has little consistent advantage in tasks with appropriate softer preferences. In complementary evaluations, a BenchPreS source gate reduces measured inappropriate application without improving non-format application. On PersistBench, an explicit OFF instruction with full history visible ties physical withholding on five paired OFF cases. We distinguish the contribution of task-level activation from the unresolved problem of translating legitimate preferences into appropriate decisions.

### 1. Introduction

Personalized assistants may receive the same stored history while answering requests with different goals, recipients and constraints. The decision to reuse an episode affects the content of the answer even after retrieval has completed. In third-party writing, the requester can authorize certain formatting preferences without making their informal manner appropriate for the letter body. In planning, a participant's constraint can be applicable while their other tastes have no bearing on the shared itinerary.

We separate two questions. **Activation** asks whether the current task benefits from exposing historical preferences at all. **Realization** asks how an available and applicable preference should affect the completed answer. A system can improve activation and still fail realization. The empirical question is whether a simple current-task signal gains over fixed history conditions, followed by where that gain disappears under closer controls.

Our contributions under the current evidence are a controlled analysis of task-level history activation on the released RPEval multi-preference roster, exact paired checks across explicit and implicit memory formats, and cross-benchmark evidence about instruction strength, source visibility and appropriate preference realization. RPEval supplies the main method comparison. BenchPreS and PersistBench probe different consequences of fixed-history use with their own strongest reproduced arms.

### 2. Task and method

For a task with current request `q`, task information `x`, and fixed ordered memories `M = (m₁, …, mₙ)`, let `G_T(q, x)` be the answer from the Actor with empty evidence and policy arrays. Let `G_H(q, x, M)` be the answer from the RP-Reasoner reconstruction with complete original history and its inferred preference-use policy. Both endpoints use the shared Actor system and generation settings. The full pipeline estimates strategy ranks and fuses the RP rankings for the history endpoint.

IPE-C uses the existing intent-preference estimator's top rank for each memory. It activates `G_H` if any top rank is C and otherwise returns `G_T`. C denotes a preference that should drive the personalized part of the response. B denotes supporting use and A denotes ignoring the preference. The switch uses predicted ranks. Author labels are reserved for evaluation and analysis. Archive replay chooses the exact corresponding saved endpoint and does not regenerate the unused endpoint. The call cost of the estimates and the selected Actor remains part of deployment cost.

This rule changes the set of contents available to the Actor at the task level. When activated, the history endpoint can still see memories unrelated to the relevant constraint. IPE-C makes no per-memory execution guarantee. The separate per-source experiment fixes all predicted strategies and compares full-history activation with retaining only the original entries predicted B or C.

### 3. Evaluation

We use the author RPEval multi-preference data pinned at release commit `0f8bce80`. All 300 author rows and public-input reconstructions match their frozen data. The project uses the Qwen 3.8 Flash generation alias and a GPT-4.1 detailed rubric adaptation. The six severity fields are task-level Judge outputs. Match counts the positions for which the Judge judged the complete answer's use consistent with author intent. The primary comparisons use strict common valid positions and retain missing cases in the allocation counts. The public short scoring prompt omits a request for Match and did not return it in the archive bridge. The RP mechanism reconstruction, the public release generation entry and the paper-reported system are tracked separately. [RPEval paper and RP-Reasoner](https://arxiv.org/abs/2601.16621)

BenchPreS checks inappropriate application (MR), appropriate application (AAR) and task completeness. The local Figure 11 Selectivity comparison uses a common Qwen single-draw adaptation. The paper uses temperature 1, three generations and DeepSeek-R1 attribute judging. PersistBench results use the project GPT-4.1 rubric adaptation and one evaluation per generated answer, with strict utility evaluated separately. The author implementation specifies Kimi K2 Thinking and repeated CD and SYC generation. We use these benchmarks as complementary evaluations and preserve their separate denominators. [BenchPreS](https://arxiv.org/abs/2603.16557v3) · [PersistBench](https://proceedings.mlr.press/v306/pulipaka26a.html) · [PersistBench implementation](https://github.com/ivaxi0s/PersistBench)

### 4. Results

| RPEval common tasks | Positions | IPE-C | Always-Task | Always-Memory |
|---|---:|---:|---:|---:|
| All, 274 tasks | 1,462 | **953** | 874 | 824 |
| All A, 116 | 512 | 400 | **426** | 267 |
| Only B, 48 | 278 | 145 | 142 | **147** |
| Contains C, 110 | 672 | 408 | 306 | **410** |
| Without known grading flags, 184 | 1,022 | **701** | 655 | 592 |

IPE-C gains 129 matches over Always-Memory (+8.82 percentage points), with +133 on all A and −2 on each of the two applicable strata. Against Always-Task, gains come principally from C (+102), offset in part by 26 fewer all-A matches. Under the adapted rubric, aggregate OPB for IPE-C, Always-Task and Always-Memory is 247, 80 and 371, and aggregate UPB is 248, 515 and 227. Their aggregate FM is 51, 250 and 55. Separately, on 280 common tasks and 1,504 positions, IPE-C reaches 970 against RP's 841. The following common-panel comparison uses the same 214 tasks and 1,144 author positions for every method.

| Method | Match | All A / 426 | Only B / 193 | Contains C / 525 | OPB / UPB / FM |
|---|---:|---:|---:|---:|---:|
| IPE-C | **761** | **334** | **111** | 316 | 202 / 176 / 39 |
| RP-Reasoner reconstruction | 653 | 228 | 107 | **318** | 300 / 163 / 42 |
| Des2Gen reconstruction | 538 | 125 | 96 | 317 | 467 / 102 / 96 |
| MemAdapter adaptation | 510 | 86 | 108 | 316 | 384 / 182 / 102 |
| Strong Gate | 512 | 107 | 96 | 309 | 466 / 135 / 120 |

IPE-C gains 108 positions over RP on this intersection, 106 on all-A tasks. Its only-B advantage of four positions reverses on the larger RP pairing. The methods share the adapted scoring contract. Their generation pipelines differ. [Five-method comparison](../native_residual_v1/COMMON_COMPARISON_CLOSURE.md)

On 177 switchable tasks grouped by identical task-only requests, the observed 653/941 positions exceed the 562.9/941 mean under a simulated reassignment preserving the number of memory activations within each block. This is a sensitivity comparison on the development archive.

For 128 exact explicit–implicit counterparts with all four scores valid, IPE-C and RP reach 469 and 402 on 693 explicit positions and 438 and 384 on the same number of implicit positions. The only-B direction differs across formats, and the C slice ties or slightly trails RP. Thus, more legible historical preferences do not by themselves produce a reliable realization advantage. The source formats also affect routing, so the comparison cannot by itself locate the error at one processing stage.

The smaller controlled studies test the explanation further:

- **Per-source exposure.** The same RP predictions, Actor and full policy went into two arms. Restricting evidence to predicted B/C tied the whole-history switch on Match (41/71) and increased OPB severity from 12 to 16. In the real music lesson case `implicit/125`, the narrow arm received only the applicable music history but extended that preference beyond selecting a class into the route and relaxation routine. The Judge did not identify misuse of the excluded entries. With one draw per arm, this illustrates a possible scope change and gives no stable causal estimate.
- **Third-party communication.** On 40 common BenchPreS tasks Strong Gate has lower MR than the Selectivity adaptation (1/132 vs. 13/132), higher overall AAR (58/68 vs. 54/68), and equal mean completeness (4.875). Non-bold AAR is 35/45 vs. 36/45. On the 38-task intersection with the earlier Raw full-history arm, Raw, Selectivity and Strong Gate have MR 78/126, 12/126 and 1/126 respectively. AAR is 49/64, 53/64 and 56/64. Strong Gate still realizes one fewer non-bold attribute than Selectivity. Raw is the project full-history reference. [Matched three-arm table](../native_residual_v1/BENCH_RAW_COMMON_BRIDGE.md)
- **Ignoring visible history.** On the PersistBench failure-enriched panel SELECTED_GEPA passes 14/14 vs. 11/14 for PB_RUBRIC. Its three wins all use zero original memories. The expanded protection panel favors PB_RUBRIC (19/19 vs. 18/19). An identical-signal control gives the same ordinal rating on five valid OFF pairs with and without the history present. On the project-template task, both avoid making Waterfall mandatory. The all-ON strict beneficial-use subset shares the same outputs by design. There is no direct estimate of utility loss from a mistaken OFF decision in that subset.

A further fixed-input comparison uses the released learned MemGate gate through a local adapter. In a 19-task, 104-position RPEval common set, IPE-C, RP, MemGate and Strong Gate obtain 66, 56, 44 and 44 matches. MemGate scores higher on the eight C-bearing tasks (37 vs. IPE-C's 30) and much lower on the nine all-A tasks (0 vs. 32). In a post-hoc replay that keeps IPE-C's activation decisions and substitutes MemGate where history is active, Match rises from 74/119 to 81/119, but OPB rises from 20 to 27 and FM from 3 to 5. In a child outing task, the alternative adds crafts despite a documented no-crafts constraint. This tradeoff motivates explicit constraint protection and does not qualify the replacement for deployment. [MemGate matched comparison](../native_residual_v1/MEMGATE_MATCHED_READOUT.md)

**Can a stronger history endpoint recover applicable preferences?** In a separately frozen replay, IPE-C retained its task-only answers and replaced the history-enabled output with the complete archived Des2Gen adaptation. Match decreased from 964 to 957 on 280 tasks with 1,502 positions. On the 129 changed-route tasks it fell from 443 to 436 of 777 positions. UPB fell from 266 to 228, alongside increases in OPB (255 to 304) and FM (53 to 76). All 151 valid task-only answers were unchanged. This intersection differs from the main RP pairing because it requires valid answer and score bindings for the substitute endpoint. The result, together with the MemGate replay, shows why underuse severity alone is an insufficient criterion for replacing the generator. [Frozen Des2Gen replay](../native_residual_v1/RPE_IPE_C_DES2GEN_REPLAY.md)

**Restoring evidence can leave the action unchanged.** In 33 exposed PersistBench tasks, a participant-link rule triggered on three plans and restored five explicit constraints. A control added the same number of original memories according to the learned gate's scores. Both reached 3/3 strict beneficial-use passes, from 1/3 with MemGate. In the book-club example, the participant-link arm received the guest's severe cat allergy but did not propose a cat-free location. Both revised outputs passed the adapted scorer. In the gardening lunch, the original answer listed an onion although the grading rationale said it avoided onions. These are examples of distinct stages: evidence can be missing, present without a corresponding action, or scored inconsistently with the action. With three triggered tasks, this pilot supplies case evidence rather than an estimate of failure rates. [Participant-constraint pilot](PARTICIPANT_CONSTRAINTS_EVIDENCE.md)

### 5. Limitations and conclusions

Existing evidence shows that selective activation can outperform both fixed endpoints on the exposed RPEval panel, with recognizable use-versus-omission tradeoffs. The additional candidate mechanisms have not shown reliable cross-source gain on legitimate soft preferences or a shared final-answer advantage across the three benchmarks. Several local Judges misread intent strings or gave reasons inconsistent with Match; we preserve their raw scores and report declared sensitivities separately. Source groups are conservative archival units. Full multi-roster allocation does not mean complete score coverage. No evaluated new method has independently confirmed leaderboard parity. BenchPreS and PersistBench need an exact judge route and complete repeated generations to support paper-protocol ranking claims.

### Evidence and reproduction pointers

- [RPEval author roster and cross-format audit](../native_residual_v1/RPE_RELEASE_IDENTITY_AND_FORMAT.md)
- [Three-benchmark matched evidence](../native_residual_v1/COMMON_COMPARISON_CLOSURE.md)
- [PersistBench exact OFF-signal comparison](../native_residual_v1/PERSIST_SWITCH_CROSS_RUN_AUDIT.md)
- [RPEval per-source versus whole-history execution](../native_residual_v1/ROUND2_RPE_EXPOSURE_RESULTS.md)
- The three-endpoint, simulated reassignment and exact actor audits are replicated from the original research workspace's `ipe_c_two_endpoint_completion_v1`, `ipe_c_rate_matched_controls_v1` and `native_residual_v1` directories. Original failed, missing and successful traces remain in the private execution archive.
