# When Should a Personalized Assistant Use Its History?
## Task-Level Memory Activation and the Limits of Preference Realization

**Working manuscript.** Results below are from exposed development data with documented scorer adaptations. Independent confirmation and author-protocol comparisons are open.

### Abstract

Fixed long-term history can help a present task or steer it inappropriately. We study both effects by changing which history a fixed Actor can read. On 12 exposed PersistBench sycophancy sources with three deployments each, full history fails on 7, a same-signal whole-history switch on 3, and per-source exposure on 1 under the project rubric. On 18 strict beneficial-use sources, those methods respectively have 17, 13 and 12 confirmed passes, with 1, 5 and 6 unknown. Two adapted graders also disagree on whether per-source exposure preserves utility on a separate deployment. On 274 common development tasks in RPEval, a separate task-level activation rule reaches 953/1,462 position matches, compared with 874 for task-only generation and 824 for complete history. A no-history control shows that an evaluator assigns overuse in the absence of supplied history. BenchPreS provides a complementary boundary for realizing legitimate expression in formal deliverables. These studies distinguish history availability, its effect on task decisions, and how that effect is measured.

### 1. Introduction

Personalized assistants may receive the same stored history while answering requests with different goals, recipients and constraints. The decision to reuse an episode affects the content of the answer even after retrieval has completed. In third-party writing, the requester can authorize certain formatting preferences without making their informal manner appropriate for the letter body. In planning, a participant's constraint can be applicable while their other tastes have no bearing on the shared itinerary.

We separate two questions. **Activation** asks whether the current task benefits from exposing historical preferences at all. **Realization** asks how an available and applicable preference should affect the completed answer. A system can improve activation and still fail realization. The empirical question is whether a simple current-task signal gains over fixed history conditions, followed by where that gain disappears under closer controls.

PersistBench supplies the main controlled risk–utility comparison. RPEval supplies paired mechanism checks on tasks with mixed preference applicability and a wider task-level activation comparison. BenchPreS tests the realization of legitimate expression and formal delivery. The two implemented activation paths share control over what the Actor sees, with different selection policies and generation contracts.

### 2. Task and method

For a task with current request `q`, task information `x`, and fixed ordered memories `M = (m₁, …, mₙ)`, let `G_T(q, x)` be the answer from the Actor with empty evidence and policy arrays. Let `G_H(q, x, M)` be the answer from the RP-Reasoner reconstruction with complete original history and its inferred preference-use policy. Both endpoints use the shared Actor system and generation settings. The full pipeline estimates strategy ranks and fuses the RP rankings for the history endpoint.

IPE-C uses the existing intent-preference estimator's top rank for each memory. It activates `G_H` if any top rank is C and otherwise returns `G_T`. C denotes a preference that should drive the personalized part of the response. B denotes supporting use and A denotes ignoring the preference. The switch uses predicted ranks. Author labels are reserved for evaluation and analysis. Archive replay chooses the exact corresponding saved endpoint and does not regenerate the unused endpoint. The call cost of the estimates and the selected Actor remains part of deployment cost.

This rule changes the set of contents available to the Actor at the task level. When activated, the history endpoint can still see memories unrelated to the relevant constraint. IPE-C makes no per-memory execution guarantee. The separate per-source experiment fixes all predicted strategies and compares full-history activation with retaining only the original entries predicted B or C.

The PersistBench pipeline uses a query router to choose Style or Grounding selection instructions. A memory-aware selector can return an empty set or a subset of the original memory. The same-signal GROUP control uses that same selector receipt, giving no history for an empty selection and full history otherwise. FULL and EMPTY are fixed endpoints with the same GEPA Actor. The full-history PB_RUBRIC is a separate complete-method reference. Identical requests within a deployment share the physical receipt across experimental arms.

### 3. Evaluation

We use the author RPEval multi-preference data pinned at release commit `0f8bce80`. All 300 author rows and public-input reconstructions match their frozen data. The project uses the Qwen 3.8 Flash generation alias and a GPT-4.1 detailed rubric adaptation. The six severity fields are task-level Judge outputs. Match counts the positions for which the Judge judged the complete answer's use consistent with author intent. The primary comparisons use strict common valid positions and retain missing cases in the allocation counts. The public short scoring prompt omits a request for Match and did not return it in the archive bridge. The RP mechanism reconstruction, the public release generation entry and the paper-reported system are tracked separately. [RPEval paper and RP-Reasoner](https://arxiv.org/abs/2601.16621)

BenchPreS checks inappropriate application (MR), appropriate application (AAR) and task completeness. The local Figure 11 Selectivity comparison uses a common Qwen single-draw adaptation. The paper uses temperature 1, three generations and DeepSeek-R1 attribute judging. PersistBench results use the project GPT-4.1 rubric adaptation and one evaluation per generated answer, with strict utility evaluated separately. The author implementation specifies Kimi K2 Thinking and repeated CD and SYC generation. We use these benchmarks as complementary evaluations and preserve their separate denominators. [BenchPreS](https://arxiv.org/abs/2603.16557v3) · [PersistBench](https://proceedings.mlr.press/v306/pulipaka26a.html) · [PersistBench implementation](https://github.com/ivaxi0s/PersistBench)

### 4. Results

#### 4.1 Actual exposure in PersistBench

A risk root fails when any of three reported ratings reaches the failure threshold, and stays unknown if no observed failure resolves it and a required rating is missing. Strict beneficial use uses one rating and requires a rating of 3. Each cell is confirmed pass / failure / unknown.

| Track | FULL | GROUP | SELECTED | EMPTY | PB_RUBRIC |
|---|---:|---:|---:|---:|---:|
| Sycophancy, 12 sources | 5/7/0 | 9/3/0 | 11/1/0 | 11/1/0 | 4/8/0 |
| Cross-domain, 19 | 12/5/2 | 13/1/5 | 15/1/3 | 14/0/5 | 12/1/6 |
| Strict beneficial use, 18 | 17/0/1 | 13/0/5 | 12/0/6 | 2/16/0 | 18/0/0 |

SELECTED improves two sycophancy roots over GROUP. Across the 12 nonempty strict-subset draw comparisons it repairs two draws and worsens one. One narrower answer retains a public exhibit's scientific framing, and another retains multiple legitimate writing directions in a student welcome message. On a family-relationships book prompt the current request already expresses its stance and all five arms fail on the final draw. These cases delimit what can be explained by exposure. A separate utility repeat delivers both SELECTED and FULL answers on all 18 sources. GPT-4.1 grades both 18/18, while Qwen records SELECTED 14 passes, three failures and one unknown and FULL 18/18. Strict-utility protection remains unresolved. [Exposure settlement](../persist_exposure_fr3_v1/FINAL.md) · [Utility repeat](../persist_utility_fresh_deployment_v1/RESULTS.md)

#### 4.2 Task-level activation and realization

| RPEval common tasks | Positions | IPE-C | Always-Task | Always-Memory |
|---|---:|---:|---:|---:|
| All, 274 tasks | 1,462 | **953** | 874 | 824 |
| All A, 116 | 512 | 400 | **426** | 267 |
| Only B, 48 | 278 | 145 | 142 | **147** |
| Contains C, 110 | 672 | 408 | 306 | **410** |
| Without known grading flags, 184 | 1,022 | **701** | 655 | 592 |

IPE-C gains 129 matches over Always-Memory (+8.82 percentage points), with +133 on all A and −2 on each of the two applicable strata. Against Always-Task, gains come principally from C (+102), offset in part by 26 fewer all-A matches. Under the adapted rubric, aggregate OPB for IPE-C, Always-Task and Always-Memory is 247, 80 and 371, and aggregate UPB is 248, 515 and 227. Their aggregate FM is 51, 250 and 55. Separately, on 280 common tasks and 1,504 positions, IPE-C reaches 970 against RP's 841. Requiring valid scores for both fixed endpoints and all external comparators yields the following 211-task intersection with 1,124 positions.

| Method | Match | All A / 426 | Only B / 185 | Contains C / 513 | OPB / UPB / FM |
|---|---:|---:|---:|---:|---:|
| IPE-C | **751** | 334 | **106** | 311 | 198 / 171 / 38 |
| Always-Task | 691 | **363** | 103 | 225 | 60 / 386 / 198 |
| RP-Reasoner reconstruction | 643 | 228 | 102 | **313** | 296 / 158 / 41 |
| Des2Gen reconstruction | 529 | 125 | 92 | 312 | 462 / 97 / 95 |
| MemAdapter adaptation | 501 | 86 | 104 | 311 | 381 / 175 / 100 |
| Strong Gate | 503 | 107 | 92 | 304 | 457 / 134 / 118 |

Relative to RP, 106 of the 108 gained positions come from all-A tasks. Relative to Always-Task, 86 positions are gained on tasks containing C, while all-A loses 29. The methods share the adapted scoring contract. Their generation pipelines differ. [Common-panel comparison and coverage](../native_residual_v1/COMMON_COMPARISON_CLOSURE.md)

On 177 switchable tasks grouped by identical task-only requests, the observed 653/941 positions exceed the 562.9/941 mean under a simulated reassignment preserving the number of memory activations within each block. This is a sensitivity comparison on the development archive.

For 128 exact explicit–implicit counterparts with all four scores valid, IPE-C and RP reach 469 and 402 on 693 explicit positions and 438 and 384 on the same number of implicit positions. The only-B direction differs across formats, and the C slice ties or slightly trails RP. Thus, more legible historical preferences do not by themselves produce a reliable realization advantage. The source formats also affect routing, so the comparison cannot by itself locate the error at one processing stage.

The smaller controlled studies test the explanation further:

- **Per-source exposure.** The same RP predictions, Actor and full policy went into two arms. Restricting evidence to predicted B/C tied the whole-history switch on Match (41/71) and increased OPB severity from 12 to 16. In the real music lesson case `implicit/125`, the narrow arm received only the applicable music history but extended that preference beyond selecting a class into the route and relaxation routine. The Judge did not identify misuse of the excluded entries. With one draw per arm, this illustrates a possible scope change and gives no stable causal estimate.
- **Third-party communication.** On 40 common BenchPreS tasks Strong Gate has lower MR than the Selectivity adaptation (1/132 vs. 13/132), higher overall AAR (58/68 vs. 54/68), and equal mean completeness (4.875). Non-bold AAR is 35/45 vs. 36/45. On the 38-task intersection with the earlier Raw full-history arm, Raw, Selectivity and Strong Gate have MR 78/126, 12/126 and 1/126 respectively. AAR is 49/64, 53/64 and 56/64. Strong Gate still realizes one fewer non-bold attribute than Selectivity. Raw is the project full-history reference. [Matched three-arm table](../native_residual_v1/BENCH_RAW_COMMON_BRIDGE.md)
- **Ignoring visible history.** On the PersistBench failure-enriched panel SELECTED_GEPA passes 14/14 vs. 11/14 for PB_RUBRIC. Its three wins all use zero original memories. Across three reconciled development batches and seven previously unissued protection tasks, SELECTED_GEPA reaches 47/49 versus 43/49 for PB_RUBRIC (+5 wins, −1 loss). This includes 11/12 versus 7/12 sycophancy passes, 18/19 versus 18/19 cross-domain passes, and 18/18 strict beneficial-use passes in both arms. On separate exact intersections it also exceeds the released flat GEPA prompt (45/47 vs. 38/47) and the saved full MemAdapter adaptation (46/48 vs. 37/48). A previously dispatched output with unknown delivery remains outside these pairs. The cohorts include a failure-enriched batch, and model aliases and score envelopes are project adaptations of the source benchmarks. [Matched PersistBench comparisons](../persist_selected_gepa_completion_v1/READOUT.md) An identical-signal control gives the same ordinal rating on five valid OFF pairs with and without the history present. On the project-template task, both avoid making Waterfall mandatory. The all-ON strict beneficial-use subset shares the same outputs by design. There is no direct estimate of utility loss from a mistaken OFF decision in that subset.

A further fixed-input comparison uses the released learned MemGate gate through a local adapter. In a 19-task, 104-position RPEval common set, IPE-C, RP, MemGate and Strong Gate obtain 66, 56, 44 and 44 matches. MemGate scores higher on the eight C-bearing tasks (37 vs. IPE-C's 30) and much lower on the nine all-A tasks (0 vs. 32). In a post-hoc replay that keeps IPE-C's activation decisions and substitutes MemGate where history is active, Match rises from 74/119 to 81/119, but OPB rises from 20 to 27 and FM from 3 to 5. In a child outing task, the alternative adds crafts despite a documented no-crafts constraint. This tradeoff motivates explicit constraint protection and does not qualify the replacement for deployment. [MemGate matched comparison](../native_residual_v1/MEMGATE_MATCHED_READOUT.md)

**Can a stronger history endpoint recover applicable preferences?** In a separately frozen replay, IPE-C retained its task-only answers and replaced the history-enabled output with the complete archived Des2Gen adaptation. Match decreased from 964 to 957 on 280 tasks with 1,502 positions. On the 129 changed-route tasks it fell from 443 to 436 of 777 positions. UPB fell from 266 to 228, alongside increases in OPB (255 to 304) and FM (53 to 76). All 151 valid task-only answers were unchanged. This intersection differs from the main RP pairing because it requires valid answer and score bindings for the substitute endpoint. The result, together with the MemGate replay, shows why underuse severity alone is an insufficient criterion for replacing the generator. [Frozen Des2Gen replay](../native_residual_v1/RPE_IPE_C_DES2GEN_REPLAY.md)

**Restoring evidence can leave the action unchanged.** In 33 exposed PersistBench tasks, a participant-link rule triggered on three plans and restored five explicit constraints. A control added the same number of original memories according to the learned gate's scores. Both reached 3/3 strict beneficial-use passes, from 1/3 with MemGate. In the book-club example, the participant-link arm received the guest's severe cat allergy but did not propose a cat-free location. Both revised outputs passed the adapted scorer. In the gardening lunch, the original answer listed an onion although the grading rationale said it avoided onions. These are examples of distinct stages: evidence can be missing, present without a corresponding action, or scored inconsistently with the action. With three triggered tasks, this pilot supplies case evidence rather than an estimate of failure rates. [Participant-constraint pilot](PARTICIPANT_CONSTRAINTS_EVIDENCE.md)

**Generation interface.** A required opening request and ordered message blocks were tested on 12 failure-enriched BenchPreS tasks. Across the 11 with complete paired scores, the renderer and Direct both realized 16/23 appropriate non-bold preferences, with completeness totals of 48 and 49. Content-first achieved 17/23 and completeness 51. All three and Strong Gate recorded 0/28 inappropriate applications. The renderer did not advance. [Structured generation comparison](../bench_speech_act_renderer_v1/READOUT.md)

**Stability across recorded source groups.** Pairwise group resampling on the same development scores gives IPE-C an overall Match advantage of 8.82 percentage points over Always-Memory (95% percentile interval 3.09 to 14.86) and 5.40 points over Always-Task (2.37 to 8.34). Removing any one group leaves both overall advantages positive, while the sign of the B-only effect relative to Always-Memory changes across omissions. The Strong Gate reduces BenchPreS MR by 8.73 points relative to Selectivity (−12.00 to −4.39); its non-bold AAR effect is −2.33 points (−9.62 to 6.06). On PersistBench, SELECTED_GEPA gains 8.16 points against PB_RUBRIC (0.00 to 18.37), with all 49 leave-one-task effects positive. These intervals describe sensitivity to grouping on the scored development panels. [Paired source-group audit](../paired_source_stability_v1/READOUT.md)

**Zero-exposure attribution check.** Of 124 RPEval answers produced without supplied history or retained current facts and context, 37 nevertheless receive a positive OPB score. The counts are 10/58 for all-A items and 4/41 for all-A items after excluding known flags. A positive OPB is therefore insufficient to infer influence from the supplied history. [Zero-exposure results](../evo_qamc_fit_v1/NO_HISTORY_RPE_GRADES.md)

**Backbone and fixed-context checks.** A controlled crossover provides no consistent improvement in the selected-versus-OFF effect of DeepSeek. Only one of 18 sources has scores for all eight conditions; complete-assignment bounds include zero. One formal draft also includes private scheduling details available in fixed Facts. Candidate-history withholding alone cannot remove that input path. The one-source intervention changing auxiliary Facts did not return a usable replacement answer, leaving its effect unresolved. [Crossover settlement](../evo_qamc_fit_v1/BACKBONE_INTERFACE_FINAL.md) · [Auxiliary input diagnostic](../evo_qamc_fit_v1/USE_ONLY_QUALIFICATION.md)

### 5. Limitations and conclusions

Existing evidence shows that selective activation can outperform both fixed endpoints on the exposed RPEval panel, with recognizable use-versus-omission tradeoffs. The additional candidate mechanisms have not shown reliable cross-source gain on legitimate soft preferences or a shared final-answer advantage across the three benchmarks. Several local Judges misread intent strings or gave reasons inconsistent with Match; we preserve their raw scores and report declared sensitivities separately. Source groups are conservative archival units. Full multi-roster allocation does not mean complete score coverage. No evaluated new method has independently confirmed leaderboard parity. The retired original Vertex Kimi service prevents repeating the exact PersistBench managed judge route. Calibration on common authored outputs is required before treating a cross-provider same-checkpoint result as comparable. The current studies use exposed development sources. They do not establish independent benchmark-wide superiority or a common winning algorithm.

### Evidence and reproduction pointers

- [RPEval author roster and cross-format audit](../native_residual_v1/RPE_RELEASE_IDENTITY_AND_FORMAT.md)
- [Three-benchmark matched evidence](../native_residual_v1/COMMON_COMPARISON_CLOSURE.md)
- [PersistBench exact OFF-signal comparison](../native_residual_v1/PERSIST_SWITCH_CROSS_RUN_AUDIT.md)
- [RPEval per-source versus whole-history execution](../native_residual_v1/ROUND2_RPE_EXPOSURE_RESULTS.md)
- The three-endpoint, simulated reassignment and exact actor audits are replicated from the original research workspace's `ipe_c_two_endpoint_completion_v1`, `ipe_c_rate_matched_controls_v1` and `native_residual_v1` directories. Original failed, missing and successful traces remain in the private execution archive.
