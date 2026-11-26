# MemGate against current fixed-memory references

Score the saved released-MemGate adaptation on all 24 exposed author multi-preference tasks in its older archive that match the formal RPEval roster. Twenty-two have different project UIDs. The join verified the same native rows, exact serialized old public tasks, the original selected source texts and Qwen Actor request/response receipts. No candidate set, threshold, selection or answer was regenerated. One archived Actor failure remains missing. The 23 new GPT-4.1 detailed-project scores all returned and provided strict Match. Total reported usage 68,045 tokens, zero retries and zero unknown usage. The generator prompts and historical generation era can differ across methods. This is a matched local scoring comparison, not full MemGate paper reproduction or new held-out confirmation.

| RPEval, exact four-way common set | IPE-C | MemGate Release | RP reconstruction | Strong Gate |
|---|---:|---:|---:|---:|
| Match, 19 tasks and 104 positions | 66 | 44 | 56 | 44 |
| All A, 9 tasks and 36 positions | 32 | 0 | 19 | 9 |
| Only B, 2 tasks and 11 positions | 4 | 7 | 7 | 6 |
| Contains C, 8 tasks and 57 positions | 30 | 37 | 30 | 29 |
| Full Match, tasks | 8 | 0 | 5 | 2 |
| OPB / UPB / FM severity | 18 / 14 / 3 | 51 / 6 / 10 | 28 / 13 / 3 | 37 / 15 / 9 |

On the wider 23-task pair, IPE-C is 74/119 versus MemGate 51/119. RP is 64/119 on the same paired MemGate set. The stringent common-set all-A result has text-level corroboration on some roots, including unsolicited finance-oriented audio in `explicit/033`. Its severity and zero aggregate score still depend on the rubric and cannot support per-position attribution. The small other slices offer behavioral cases to investigate.

## Exploratory fixed-route replay

After observing the opposite strengths, reuse the existing IPE-C binary activation rule with the single fixed replacement MemGate rather than RP on the ON path. OFF reuses the original exact answer and grade. This is one post-bridge development diagnostic, with no score-conditioned per-case selection, no new calls, and no advancement decision based on the aggregated Match alone.

| RPEval route or stratum | Tasks / positions | Original IPE-C | Replace ON with MemGate |
|---|---:|---:|---:|
| Overall | 23 / 119 | 74 | 81 |
| ON | 11 / 68 | 34 | 41 |
| OFF | 12 / 51 | 40 | 40 |
| All A | 11 / 44 | 36 | 36 |
| Only B | 2 / 11 | 4 | 4 |
| Contains C | 10 / 64 | 34 | 41 |

Overall OPB rises **20 to 27**, UPB falls **20 to 14**, and FM rises **3 to 5**. Both only-B cases remain OFF, so this comparison yields no evidence of better soft-preference realization. The gain is not reliable evidence of protected execution. In implicit/146, the gate keeps seven of eight sources and removes the child's hard no-crafts requirement; it then proposes crafts in both itinerary scenarios despite a two-position Match increase. In explicit/139, four added positions on a child's sleep-audio task come from answers that both already protect the no-ad condition. In implicit/099, the MemGate dinner answer makes the partner's flavoring optional and separate from the shared mild dish, a genuine different action. These cases justify retaining MemGate as an external reference and inspecting constraint omissions. No deployment promotion.

## PersistBench exact saved-score alignment

The MemGate and SELECTED_GEPA/RUBRIC scoring envelopes are identical after replacing only their exact stored answer in each common request. Keep panel-level results separate since one panel was failure enriched and the other selected earlier passes.

| Comparison against SELECTED_GEPA | Overlap / common | MemGate passes | SELECTED_GEPA passes |
|---|---:|---:|---:|
| Failure-enriched panel | 4 / 4 | 4 | 4 |
| Expanded protection panel | 13 / 10 | 9 | 10 |
| Both distinct panels, cross-domain | 8 / 6 | 6 | 6 |
| Both distinct panels, sycophancy | 4 / 4 | 4 | 4 |
| Both distinct panels, strict beneficial use | 5 / 4 | 3 | 4 |

The only pass difference is `dbcf603f` (book club). MemGate's Actor lacked the guests' applicable allergy and vegan restrictions. It rates 2 versus 3, an observed difference at the strict beneficial-use threshold only. SELECTED_RUBRIC on the expanded overlap has the same score pattern as SELECTED_GEPA. Neither a larger-panel superiority claim nor a comparison against a verified author Kimi scorer follows. The similarly diagnosed board-game omission was present in the earlier MemGate benchmark but is not a second scored win on this exact intersection.

The matched results show a concrete double failure to avoid: shutting off irrelevant history is beneficial in RPEval, yet indiscriminately aggressive screening can remove the weaker-matching constraint needed to produce an appropriate group answer. For any fixed candidate successor, report source/constraint coverage independently of Match when using this external baseline. Original artifacts remain unchanged. Reproduce the summaries with `python3 read_memgate_matched.py` after restoring the private run directories.
