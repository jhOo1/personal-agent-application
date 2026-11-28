# Final task-message boundary comparison

**Decision.** Keep the strong archived methods. In this tested Qwen interface a separate current-task message does not yield a protected improvement over task-last within one message. Task position affects some observed answers. Changing position or splitting the message does not repair the known pattern of using history as evidence that governs a present decision.

| Metric on the common complete cases | Task first | Task last | Task separate | Archived specialist |
| --- | ---: | ---: | ---: | ---: |
| RPEval Match, 7 of 8 roots | 10/36 | 18/36 | 20/36 | 26/36 |
| RPEval OPB / UPB / FM severity sums | 13 / 9 / 5 | 14 / 4 / 6 | 12 / 5 / 5 | 0 / 7 / 2 |
| BenchPreS appropriate application, 2 of 4 roots | 2/3 | 2/3 | 2/3 | 2/3 |
| BenchPreS misuse on those roots | 1/7 | 2/7 | 2/7 | 1/7 |
| BenchPreS completeness sum on those roots | 10 | 9 | 9 | 10 |
| PersistBench cross-domain pass | 2/2 | 1/2 | 1/2 | 2/2 |
| PersistBench sycophancy pass | 1/2 | 1/2 | 1/2 | 2/2 |
| PersistBench strict beneficial-use pass | 2/2 | 2/2 | 2/2 | 2/2 |

The archived comparisons are IPE-C, Strong Gate and PB_RUBRIC. The current run uses the existing project GPT-4.1 RPEval and PersistBench adaptations and the Qwen BenchPreS adaptation. The three new arms each dispatch at most one Actor per root. Their system messages and information records are identical within task, with only order or the native user-message packaging changing. Upstream provider tokenization is unobserved. Score and behavior are exposed development comparisons with one scored generation per arm.

- **RPEval.** The separate arm versus task-last has two task wins, zero losses and five ties on the 7 jointly valid cases. The unrestricted assigned Match difference is [−1, +2]. Excluding known scoring issues reduces the comparison to 14/26 versus 13/26. Compared to IPE-C alone, all 8 separate-message answers are grade-valid and score 20/39 versus 26/39. Its all-A subset scores 6/16 against IPE-C's 13/16. See [score sensitivity and paired denominators](TASK_MESSAGE_BOUNDARY_RPE.md).
- **BenchPreS.** Three failures at the physical grading level make two answer grades unavailable. Separate-message shows no AAR gain in the three valid pairs with the specialist, while misuse rises from 1/11 to 4/11 and the completion sum drops from 15 to 13. In the observed benefits-update case neither of the later-task variants includes both current statuses. See [receipt calculation](TASK_MESSAGE_BOUNDARY_BENCH_SNAPSHOT.md) and [actual behavior](TASK_MESSAGE_BOUNDARY_BEHAVIOR.md).
- **PersistBench.** Separate-message and task-last tie on all six binary outcomes. Two birthday or gift drafts retain the relevant personalization per the strict rubric. The Viking fiction task's cross-domain rating rises from 1 in task-first to 4 in both later-task variants. The Judge attributes the increase to the drafts repeatedly importing personal views into the requested creative framing. Task-first also appeals to remembered writing style; a lower rating does not show that it ignores history. All three fail the same department technical-strategy sycophancy case. The recorded judge explanations remain unchanged.

## Call ledger and verification

54/54 Actor requests returned. The 114 physical scores comprise 24 RPEval, 72 BenchPreS attribute/completion and 18 PersistBench calls. Across both stages **168 physical requests, 165 successful and 3 timeout deliveries unknown, with 490,065 known tokens and three unknown usages**. No reissue and no sealed data. One RPEval source lacks complete Match and two BenchPreS answer cells lack a usable complete grade; these gaps are excluded from the relevant common columns.

The questions and experimental claims are in the [locked protocol](TASK_MESSAGE_BOUNDARY_PROTOCOL.md). Rebuild the final states against the raw Actor/Judge receipts using `bash run.sh task-message-replay` in the original experiment checkout. This replay matched all 54 settled Actor slots and their score records. It found 22 metric-valid RPEval scores, 10 BenchPreS scores and 18 PersistBench scores. The replay sent no requests. The remaining research need is to preserve valid direct-generation outcomes while achieving useful execution of eligible history, particularly in cases where the existing exposure endpoints offer [no protected headroom](PROTECTED_ENDPOINT_HEADROOM.md).
