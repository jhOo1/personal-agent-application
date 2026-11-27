# Direct feature-demonstration results

Retain IPE-C. Nine exposed development source groups, 56 author positions, all three answers valid on all nine. Match: frozen IPE-C 38, task-feature illustration 40, memory-feature illustration 31. OPB severity sums 9/5/12, UPB 6/9/9, FM 1/2/2. Against the generic illustration the memory illustration wins two, loses four and ties three tasks. Against IPE-C it wins none. All 18 generation and 18 judging requests returned OK, 80,150 reported tokens, zero unknown usage. Verified every actual Actor request recovers the archived request hash after removing the illustration. Single generations and project-adapted GPT-4.1 Judge. Human reviewers: zero.

The entire net nine-position difference between the two demonstrations is concentrated in two cases. For implicit/070, both answers satisfy the child's no-cartoon requirement. The generic Judge awards 6/6 for CAAAAA while praising the answer for using the other five preferences; the memory arm gets 1/6 and is penalized for similar styling. For explicit/089 (warm dinner for a girlfriend), neither Actor received personal history. Both propose hot tomato-and-beef dishes; the memory illustration's answer includes cooking times and easy preparation. Its Judge attributes efficiency and other properties to the user's history and scores 0/4; the generic answer scores 4/4. This can measure similarity to hidden preferences but cannot demonstrate transmission of this user's history through the empty source block. Neither issue overwrites primary scores. Post-hoc exclusion of both tasks gives 33/46, 30/46 and 30/46 respectively. Three history-B tasks alone give 11/19, 9/19 and 9/19. No evidence for transferring this standalone illustration to the other two benchmarks.

The peer's separate suggestion of a contrasting conditional substitution demonstration (Xi'an) was not tested by this trial. The earlier [two-state draft review](../native_residual_v1/RPE_CONTINGENCY_RESULTS.md) found zero fully protected incremental changes on four prospectively targeted roots. Any future contrastive demonstration would need a different actual intervention and explicit unmet action. The present pilot uses authored examples of an existing choice, not full teacher answers, and compares explicit preference framing with generic task utility. Example wording differs as documented in the protocol. No independent confirmation or SOTA claim.
| Stratum | UID suffix | positions | IPE-C / generic / memory Match | OPB | UPB | FM |
|---|---|---:|---|---|---|---|
| history_B | implicit/057 | 5 | 2 / 2 / 1 | 0 / 0 / 0 | 3 / 3 / 4 | 0 / 0 / 0 |
| history_B | explicit/030 | 8 | 5 / 4 / 5 | 1 / 2 / 2 | 1 / 1 / 1 | 0 / 0 / 0 |
| history_B | implicit/078 | 6 | 4 / 3 / 3 | 0 / 0 / 0 | 1 / 2 / 2 | 0 / 1 / 0 |
| history_C | implicit/070 | 6 | 1 / 6 / 1 | 4 / 0 / 4 | 0 / 0 / 0 | 0 / 0 / 0 |
| history_C | implicit/019 | 8 | 5 / 5 / 4 | 2 / 2 / 2 | 1 / 1 / 2 | 1 / 1 / 1 |
| history_C | explicit/149 | 7 | 5 / 4 / 5 | 2 / 1 / 1 | 0 / 2 / 0 | 0 / 0 / 0 |
| task_all_A | explicit/084 | 6 | 6 / 6 / 6 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| task_all_A | implicit/090 | 6 | 6 / 6 / 6 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| task_all_A | explicit/089 | 4 | 4 / 4 / 0 | 0 / 0 / 3 | 0 / 0 / 0 | 0 / 0 / 1 |

Match {'IPE-C': 38, 'TASK_FEATURE': 40, 'MEMORY_FEATURE': 31, 'tasks': 9, 'positions': 56}
OPB {'IPE-C': 9, 'TASK_FEATURE': 5, 'MEMORY_FEATURE': 12, 'tasks': 9, 'positions': 56}
UPB {'IPE-C': 6, 'TASK_FEATURE': 9, 'MEMORY_FEATURE': 9, 'tasks': 9, 'positions': 56}
FM {'IPE-C': 1, 'TASK_FEATURE': 2, 'MEMORY_FEATURE': 2, 'tasks': 9, 'positions': 56}
Receipts {'OK': 36} reported tokens 80150 unknown usage 0
