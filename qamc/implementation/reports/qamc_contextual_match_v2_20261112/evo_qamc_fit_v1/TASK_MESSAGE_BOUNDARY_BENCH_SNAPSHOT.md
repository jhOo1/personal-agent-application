# BenchPreS receipt snapshot while scoring is in flight

This is a read-only snapshot, not the final state of the task-message trial. All 12 final drafts are saved. The common Qwen adaptation had 69 of 72 complete attribute/completion requests at the time of replay. The last three requests remained in flight, so two answers lacked a complete grade. Reconstructing from the raw receipts yielded 10 metric-valid answers.

| Comparison | Common tasks | Appropriate use | Misuse | Completion sum |
| --- | ---: | ---: | ---: | ---: |
| Task last versus task first | 3/4 | 4/5 vs 4/5 | 2/10 vs 1/10 | 14 vs 15 |
| Separate versus task last | 2/4 | 2/3 vs 2/3 | 2/7 vs 2/7 | 9 vs 9 |
| Separate versus Strong Gate | 3/4 | 3/4 vs 3/4 | 4/11 vs 1/11 | 13 vs 15 |

The full-assignment bounds on appropriate-use gains are [−1, 0], [−2, +1], and [−1, +1], respectively. These are separate common populations. The missing receipts are not treated as wrong answers. The valid separate-message comparison already shows more misuse and lower completion than the archived strong reference on its matched cases. Wait for finalized scores before pooling or reporting a final rank. No extra requests were issued for this snapshot.

Run `bash run.sh task-message-replay --domain BenchPreS` in the original experiment archive to reproduce the same calculation on the receipts currently available. The raw snapshot remains in the private run. See [behavior observations](TASK_MESSAGE_BOUNDARY_BEHAVIOR.md) for the benefits-update case.
