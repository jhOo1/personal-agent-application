# Same-task comparison with archived opponents

The generic illustration has the highest raw Match on the seven tasks where all methods returned usable Match and severity fields. Removing the two previously documented Judge disputes reverses its ordering relative to IPE-C and RP. Keep the complete primary panel. The smaller slice is a sensitivity check on known disputes. No new model requests or new participants were involved.

| Common set | IPE-C | Task feature | Memory feature | RP reconstruction | Des2Gen reconstruction | MemAdapter adaptation | Internal Strong Gate |
|---|---:|---:|---:|---:|---:|---:|---:|
| 7 tasks / 41 positions, Match | 28 | 31 | 22 | 24 | 15 | 25 | 17 |
| Same tasks, OPB | 5 | 2 | 9 | 7 | 13 | 10 | 12 |
| Same tasks, UPB | 5 | 6 | 7 | 8 | 7 | 7 | 6 |
| Same tasks, FM | 0 | 1 | 1 | 1 | 2 | 4 | 2 |
| 5 tasks / 31 positions after the sensitivity exclusions, Match | 23 | 21 | 21 | 23 | 14 | 22 | 16 |

Pairwise Match against RP is 38/40/31/34 (IPE-C/task feature/memory feature/RP) over 9 tasks and 56 positions. Against Des2Gen the same panel gives 38/40/31/24. Against MemAdapter, 8 tasks and 49 positions give 33/36/26/29; against Strong Gate, 8 tasks and 48 positions give 33/35/27/21. Requiring every opponent loses two different tasks. All comparisons match exact UIDs and position counts; the archive reports the same project GPT-4.1 Judge variant. Pipeline inputs, generation costs and sampling dates differ. The larger [IPE-C external comparison](../native_residual_v1/RPE_IPE_C_EXTERNAL_COMPARISON.md) remains the stronger evidence for the frozen route; these nine are development cases, each with one draw per new arm. The observed UPB remains a task-level severity assessment.

Reproduce using `python3 compare_archive.py` after restoring the panel, both trial receipts and the formal multi-method result archive. See the [paired trial](RESULTS.md) for the case-level readout. No independent confirmation or leaderboard claim.
