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
