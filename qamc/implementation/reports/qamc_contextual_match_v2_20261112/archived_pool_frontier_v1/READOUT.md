# How much improvement was available to a selector?

We joined the 92-task reassembly roster to the 24-task DREW subset by task, group, stratum and exact default answer. Each task contributes once. For each scored, distinct candidate, we measured its difference from that same strong default. The retrospective maximum is attainable by an oracle choosing among these particular measured answers. Missing answers and grades leave headroom outside the observed pool unknown. Scores stayed in the evaluation layer. No calls or sealed sources.

| Benchmark | Assigned | Tasks with graded distinct alternatives | Max primary gain across tasks | Max with protection | Max with protection and no archived flags |
|---|---:|---:|---:|---:|---:|
| RPEval | 24 | 21 | 8 additional matched positions, 2 groups | 8, 2 groups | 1, 1 group |
| BenchPreS | 26 | 19 | 1 additional appropriate preference, 1 group | 0 | 0 |
| PersistBench | 42 | 32 | 1 additional strict pass, 1 group | 1, 1 group | 1, 1 group |

For RPEval we require no increase in OPB, UPB or FM on the same task. For BenchPreS we require no increase in MR and no decrease in completeness or non-bold appropriate preference use. For PersistBench the primary outcome uses strict utility and the protection preserves the release pass. Absence of a recorded flag is only a sensitivity check, not independent validation. Positive gains across benchmarks use different units.

The large RPEval change came from the surprise birthday task (1/8 to 7/8 with a Match/bias conflict flag). On the family Qingdao itinerary, the unflagged free revision moved 3/7 to 4/7 while decreasing UPB from 3 to 1 and FM from 1 to 0. BenchPreS's tax message moved 1/2 to 2/2 appropriate uses while completeness fell from 4 to 3. PersistBench's software template had two successful revisions of the same default across the archives. This is one source group. It does not establish a repeated repair on independent projects.

There were 22 missing generated answers and 18 ungraded recorded answers across the two archives. In BenchPreS only four distinct ungraded texts on three tasks had both a scored default with room to improve AAR and no graded copy elsewhere in these pools. Before considering any new Judge request, check whether prior scoring attempts on these texts failed or were never issued. Count known delivery failures as missing. Keep all 92 assigned tasks in the inventory.

**Decision.** Further reranking of these same measured revisions has no observed protected BenchPreS AAR gain available and little cross-source upside elsewhere. To test a new selection mechanism fairly, use candidate sets with demonstrated gains on several independent development groups or produce substantively different candidate answers. Treat oracle-screened experiments as targeted development. This finding does not set a bound on the full benchmarks or on a new generator.
