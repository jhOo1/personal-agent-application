# BenchPreS profile-disjoint development replication

The content-first prompt did not reproduce its pilot advantage. All 19 exposed cases across seven profiles were common. The actual Actor requests differ only by the extra content-first instruction. None of the seven profiles appear in the pilot.

| Method | AAR | Non-bold AAR | MR | Completeness |
| --- | ---: | ---: | ---: | ---: |
| Archived Strong Gate | 28/28 | 15/15 | 1/67 | 95/95 |
| Direct generation | 28/28 | 15/15 | 0/67 | 87/95 |
| Content-first | 26/28 | 13/15 | 0/67 | 85/95 |
| Published Selectivity adaptation | 25/28 | 14/15 | 3/67 | 92/95 |
| RP-Reasoner reconstruction | 24/28 | 15/15 | 2/67 | 90/95 |

The two content-first AAR losses relative to direct are from one profile; the other six tie. Strong Gate was already saturated on appropriate attributes. This panel tests regression and provides no AAR headroom against Gate. The previous enriched panel's improvement remains valid as a development observation. This replication does not support replacing Strong Gate with the content-first suffix. A successor needs a reliable trigger for unrecovered style or an actual improvement in both task content and realization.

266 actual requests, all successful (38 Actor and 228 scores), 451,126 reported tokens, no unknown usage or retries. All references use the same project-adapted scoring, not the official DeepSeek-R1 protocol. Neither pilot nor replication accessed sealed evaluation.

## Post-hoc room for selective use

Across both panels, selecting content-first only where it adds AAR and does not lower completeness or increase MR would recover four AAR positions on four of the 12 pilot cases and none on the 19 group-out cases. One pilot case and eight group-out cases instead showed a decrease in AAR or completeness, or an increase in MR, versus Gate. This upper bound inspects both answers' scores. It is not an implementable selector and cannot establish that an input-only rule can separate the cases. In particular, the profile-disjoint set contains no positive examples of the target behavior, so any trigger derived from these positive cases remains a pilot hypothesis.

## Remaining exposed positive cases

Joining the exact Strong Gate census to the two realization runs by UID finds that all ten recorded non-bold misses have already appeared in one of the two panels, including the one without a verbatim objective preference. The latter appeared as a protection case for a separate, realized attribute, not as a delivered-miss target. There are zero untreated recorded miss UIDs in this census. This does not rule out misses elsewhere in the public benchmark or in a different archive. It does rule out drawing a fresh positive replication slice from this same census. A trigger inferred from these runs can be assessed for feasibility offline but needs new, authorized, appropriately isolated opportunities to establish a correction rate.

The separate 48-row Selectivity archive was joined to exact Gate records by UID and matched metric denominators. 41 overlap with verifiable Gate, 40 have compatible scores, and nine of these were not used in either realization run. None of those nine has a Gate non-bold AAR deficit. This archive offers further protection comparisons but supplies no new non-bold repair target under the current scoring. Zero model requests were needed for the join.

The seven Selectivity UIDs without a verifiable Strong Gate endpoint separate into five without an archived successful Gate answer and two with a successful Gate answer and invalid aggregate grade. Both latter cases have all six transport receipts. Their completeness replies are prose instead of the expected structured payload. Preserve the historical missing grades. A stage-specific regrade, if needed for a new comparison, can reuse the answers and valid attribute receipts after verifying exact request hashes. It cannot provide independent evidence by itself.
