# Which class must contain a mismatch?

|Panel (C-bearing tasks)|Endpoint|Class|Positions|Mismatch range|Tasks forced to miss at least one|Tasks where a miss is possible|
|---|---|---|---:|---:|---:|---:|
|all|IPE-C|A|459|62–264|44|110|
|all|IPE-C|B|65|0–65|0|57|
|all|IPE-C|C|148|0–148|0|110|
|all|better saved score|A|459|58–255|42|107|
|all|better saved score|B|65|0–63|0|55|
|all|better saved score|C|148|0–145|0|107|
|no recorded flag|IPE-C|A|306|44–185|27|67|
|no recorded flag|IPE-C|B|49|0–49|0|42|
|no recorded flag|IPE-C|C|99|0–99|0|67|
|no recorded flag|better saved score|A|306|42–179|26|65|
|no recorded flag|better saved score|B|49|0–47|0|40|
|no recorded flag|better saved score|C|99|0–97|0|65|

For a task with n positions, k in the named class and d scored mismatches, the number in that class lies between max(0, d - (n-k)) and min(k, d). Summing task bounds gives attainable marginal limits conditional on the recorded counts. Upper bounds for different classes need not be jointly attainable. Source groups can share tasks; counts here are per task. No per-position judgments are inferred from severity ratings or free-text reasons.

The better-score oracle still necessarily misses at least 58 author-A positions on 42 C-bearing tasks. The Match totals require zero C errors at minimum and permit 145; for IPE-C the analogous interval is 0–148. Thus a proposal to repair C omissions across these tasks needs separate evidence that the constrained actions are wrong. An A mismatch does not identify which memory changed which action or whether the scorer read the answer correctly. The [separate frozen behavior review](../paper_rpe_behavior_alignment_v1/READOUT.md) found all C actions realized on nine of twelve IPE-C tasks despite zero exact Match on this enriched panel; it also documents a real seafood conflict with no numeric flag. Neither observation supplies new benchmark scores. No model calls, retries or sealed inputs.
