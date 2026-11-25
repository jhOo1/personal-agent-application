# Native Actor optimization headroom

The reviewer identified a concrete defect in the previous search panel. Its four BenchPreS cases already had full AAR. Offline recomputation against available exposed archives confirms the defect.

| Benchmark | Search history-enabled cases with remaining primary positions | Full exposed archive cases with remaining positions | Archive distinct groups with headroom |
| --- | ---: | ---: | ---: |
| RPEval | 6/6 | 187/282 | 43 |
| BenchPreS | 0/4 | 10/41 | 3 |
| PersistBench | 2/7 | 6/50 | 6 |

The archive totals count available requests with a scored reference, not final optimization eligibility. In particular the RPEval archive count can include no-history reference routes, which must remain bypassed for the NRO intervention. A headroom count establishes the possibility of score movement, not that an instruction can fix the error. BenchPreS has at most three archived groups with AAR losses, so reserve one such group for group-out development and include ceiling groups as regression controls. A group-out split here remains previously exposed development, with no claim of independent confirmation.

The next comparison should generate candidates from paired failures on the search groups, against an equally funded whole-policy mutation. Freeze both best nonempty policies before reading group-out outcomes. Record deployment rejection separately. Four prewritten rules and the score-only feedback implementation cannot prove the effect of trajectory-driven search. No new requests were used for this inventory.
