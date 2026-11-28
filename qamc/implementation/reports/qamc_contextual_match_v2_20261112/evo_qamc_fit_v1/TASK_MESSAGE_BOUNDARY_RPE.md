# RPEval substage of the task-message comparison

Read-only reconstruction from the 24 original Actor answers and 24 GPT-4.1 grading receipts. All 24 judge calls returned and parsed. One task-first and task-last pair lacks a usable Match comparison, so delivery and Match coverage are reported separately. This is the exposed-development frozen scorer configuration.

| Prespecified comparison | Joint tasks | Match, new / comparison | Task wins / losses / ties | Full assignment Match difference |
| --- | ---: | ---: | ---: | ---: |
| Task-last vs task-first | 7/8 | 18/36 vs 10/36 | 3 / 0 / 4 | [+5, +11] |
| Separate message vs task-last | 7/8 | 20/36 vs 18/36 | 2 / 0 / 5 | [−1, +2] |
| Separate message vs archived IPE-C | 8/8 | 20/39 vs 26/39 | 1 / 2 / 5 | [−6, −6] |

Task-last versus task-first gains 2/26 Match positions after excluding the known scoring flags in either arm, versus 8/36 on the original matched scores. Separate-message versus task-last goes from +2/36 to +1/26 under the flag exclusion. Relative to IPE-C, separate-message results without flags are 14/26 versus 21/26. Preserve all original scores.

The most pronounced loss versus IPE-C is on the four all-A tasks: 6/16 versus 13/16, with OPB severity 11 versus 0. In the paired boundary comparison the two all-A arms both score 6/13, and OPB is 8 for separate versus 7 for task-last. The higher Match versus task-first does not establish reduced inappropriate use. See [observed case behavior](TASK_MESSAGE_BOUNDARY_BEHAVIOR.md).

The paired bounds allow ungraded positions to take either endpoint. Rerun the RPEval calculation with `bash run.sh task-message-replay --rpe-only` from this experiment's directory in the original archive. No grading calls are dispatched by replay. BenchPreS and PersistBench are reported at full settlement.
