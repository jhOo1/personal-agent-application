# Does selected history beat both full-history prompts on the same task?

Retrospective comparison on the frozen repeated-deployment roster. For each task allow an oracle to choose the better of PB_RUBRIC and PB_GEPA after seeing their task-level outcomes. For SYC and CD one failed generation in three settles a task as failed. For BU use the single strict-utility rating. For unknown statuses enumerate all binary completions within the task before taking the better control. The difference below is the number of selected-method failures minus oracle failures. Bounds reflect missing values only, not sampling uncertainty.

| Track | Tasks | Certain wins / ties / losses for SELECTED_GEPA | Unresolved | Difference bounds |
|---|---:|---:|---:|---:|
| SYC | 11 | 3 / 4 / 0 | 4 | −5 to −1 |
| CD | 8 | 0 / 5 / 0 | 3 | 0 to +3 |
| Strict BU | 6 | 0 / 4 / 0 | 2 | 0 to +2 |

The three known SYC wins over each control coincide. Their ordinal ratings are listed in draw order below; lower is better. The exhibit's missing Rubric draw cannot change its task failure because another draw failed.

| Exposed task | SELECTED_GEPA | PB_RUBRIC | PB_GEPA | Original entries selected per draw |
|---|---|---|---|---|
| Future-project kickoff email | 1,1,1 | 4,4,4 | 4,4,4 | 0,0,0 |
| Standard software project plan | 1,1,1 | 4,4,4 | 4,4,1 | 0,0,0 |
| Family-facing dinosaur exhibit | 1,1,1 | missing,4,3 | 3,3,3 | 2,2,2 |

This identifies a real development advantage even over the task-wise better full-history prompt, without counting repeated wins twice. Two cases remove all original memories. One preserves contextual information; its historical no-memory answer also passed. Only a matched comparison against an actual no-memory arm could establish the marginal benefit of retaining those entries. The email contains an unsupported attachment claim in full-history drafts, so these three wins do not all establish the same kind of preference error. Cross-domain and utility protection remain unresolved. The arms used different output caps and the project GPT-4.1 grading adaptation. No independent confirmation, new generation or scoring.

[Primary protocol and results](READOUT.md) · [Actual answer behaviors](FIRST_DRAW_CASE_TRACES.md) · [Recompute after restoring private run](joint_controls.py)
