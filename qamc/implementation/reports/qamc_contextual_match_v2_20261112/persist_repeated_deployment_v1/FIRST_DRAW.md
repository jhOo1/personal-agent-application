# PersistBench first deployment checkpoint

The first wave has settled. The predeclared three-draw primary endpoint for sycophancy and cross-domain leakage remains in progress. This checkpoint retains first-draw results separately and does not change any allocation or threshold.

| Track | Allocated per arm | SELECTED_GEPA passes / scored | PB_RUBRIC passes / scored | Full-history GEPA passes / scored |
|---|---:|---:|---:|---:|
| Sycophancy | 11 | 7/8 | 4/9 | 5/11 |
| Cross-domain | 8 | 6/6 | 8/8 | 8/8 |
| Strict beneficial use | 6 | 4/4 | 6/6 | 6/6 |

| First-draw comparison | Paired known / allocated | SELECTED_GEPA wins / losses | Failure-count difference range |
|---|---:|---:|---:|
| SYC vs. PB_RUBRIC | 6/11 | 2 / 0 | −6 to −1 |
| SYC vs. full-history GEPA | 8/11 | 4 / 0 | −5 to −2 |
| CD vs. either full-history arm | 6/8 | 0 / 0 | 0 to +2 |
| Strict BU vs. either full-history arm | 4/6 | 0 / 0 | 0 to +2 |

The range is SELECTED_GEPA failure count minus control failure count under all binary assignments of unknown outcomes. The anti-sycophancy advantage in this draw survives unfavorable assignments against both references. CD and strict BU cannot establish protection across the allocated panels. Both missing BU answers belong to SELECTED_GEPA: one selector parse failure and one incomplete Actor stream. These were the only planned BU draws. On the book-club case the full-history Rubric arm passes strict BU while leaving an allergy-related venue conflict open. See the [case behavior audit](UTILITY_BEHAVIOR_AUDIT.md).

The checkpoint has 66/75 complete answer-and-score positions. Its journal records 190 dispatched requests, 182 successful and eight with unknown delivery after missing stream completion. The parser failure separately affects one answer position. All 66 dispatched Judge requests completed; reported total usage was 1,195,235 tokens, with eight usage values unknown. No failed request was reissued. Scoring is the common project GPT-4.1 adaptation. [Frozen protocol](PROTOCOL.md) · [Bounds and protection checks](paired_bounds.py)
