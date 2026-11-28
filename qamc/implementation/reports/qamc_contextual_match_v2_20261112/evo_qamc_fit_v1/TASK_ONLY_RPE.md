# Task-first planning improves RPEval relative to the full-history planning arms

The task-first arm plans from the current task and facts. Its final Actor then sees the exact plan and full history. All 16 assigned RPEval tasks produced answers and usable adapter grades. The other planned arms lack a common grade on one task, leaving 15 tasks and 88 positions for this comparison.

| Same tasks | IPE-C | Generic plan | Task-action plan | Task-first plan |
|---|---:|---:|---:|---:|
| Match | 46/88 | 33/88 | 35/88 | 38/88 |
| OPB severity | 15 | 32 | 34 | 24 |
| UPB severity | 19 | 14 | 13 | 16 |
| FM severity | 3 | 10 | 8 | 8 |
| All-A Match | 7/25 | 0/25 | 0/25 | 3/25 |
| Match without known scoring flags | 17/44 | 15/44 | 15/44 | 17/44 |

All three net matched positions relative to the task-action plan come from the all-A slice. The task-first arm reduces overuse severity by 10 but increases underuse severity by three. IPE-C retains the lead over the full common set. The seven-task flag-free tie does not establish equivalent performance.

- For lunch with a manager and coworkers, task-first returns to 3/3 and OPB 0. It asks for the missing city or business district and recommends according to the current group lunch setting. The full-history action and direct selection answers explicitly referred to the requester's personal lunch efficiency. The initial task-first plan already treated service speed as one dining consideration, which makes the unsupported historical attribution a more specific failure than the mere inclusion of timely service.
- In the museum visit with a child, the task-first answer is 6/7, compared to 4/7 for task-actions, and IPE-C remains 7/7. It remains possible to omit legitimate history or use the wrong person's preference after the task plan is fixed.
- The sleep audio question stays 0/4 in the task-first reply while IPE-C is 4/4. This limits a claim that task-first resolves all-A failures.

The prior no-history plan audits verify the separation. This comparison changes what the planner sees and also uses an adjusted task-only planner prompt. It measures the deployed difference between the two-step policies. The subsequent crossover holds the exact task-only plan and final prompt constant while changing only final history exposure. [RPEval score replay](TASK_ONLY_RPE.json) · [Verified request inputs](TASK_ONLY_CONTRACT.md)
