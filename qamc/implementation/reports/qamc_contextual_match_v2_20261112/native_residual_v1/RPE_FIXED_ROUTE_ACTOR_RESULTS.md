# RPEval fixed-route Actor development results

Keep frozen Qwen IPE-C as the reference. The GPT-4.1 Actor substitution improves the task-only all-A slice, but does not improve recorded applicable B or C use on this panel.

The audit verified all 20 live Actor requests against archived Qwen hashes after changing only the requested model alias back to qwen3.8-flash. The responses come from different time windows. GPT-4.1 is also the project Judge alias, so shared-model judging could affect the comparison. Only the frozen exposed development panel was used.

| Matched slice | Valid / assigned | Qwen Match | GPT-4.1 Match | OPB Qwen → GPT | UPB Qwen → GPT | FM Qwen → GPT |
|---|---:|---:|---:|---:|---:|---:|
| Total | 17/20 | 58/91 | 61/91 | 19 → 12 | 16 → 22 | 4 → 1 |
| History, B without C | 5/6 | 17/27 | 13/27 | 3 → 3 | 7 → 11 | 0 → 0 |
| History, C present | 6/8 | 18/34 | 18/34 | 13 → 9 | 5 → 11 | 2 → 1 |
| Task-only, all A | 6/6 | 23/30 | 30/30 | 3 → 0 | 4 → 0 | 2 → 0 |

Match: 3 wins, 4 losses, 10 ties. On 13 valid roots from groups outside the earlier Actor comparison, Match was 45 → 52/69 and UPB 10 → 12. On four valid roots from reused groups it was 13 → 9/22 and UPB 6 → 10. Groups and all cases are development exposures. OPB, UPB and FM are Judge severity sums. The task-only all-A slice had no original history in either Actor request, so the observed difference does not establish progress in choosing memories or protecting legal use.

Practical archived comparisons on each method's own common set, with distinct generation pipelines: RP reconstruction 50 versus 61/91 (17), Des2Gen 36 versus 61/91 (17), MemAdapter 42 versus 56/84 (16), GEPA selected bounds 24 versus 39/59 (11). GPT-4.1 had higher UPB in each of these slices. These figures do not establish SOTA or substitute for protocol-matched outside comparisons.

The 40 physical requests consisted of twenty returned Actor answers and twenty grading requests. There were 39 OK receipts, two of whose grading outputs had invalid Match denominators or ranges, and one grading request had unknown delivery and usage. No retry. Reported usage: 57,176 tokens. Answer and grading payloads are retained in the private run. Reproduce the summary from the saved manifests and receipts with the companion audit script, which makes no calls.
