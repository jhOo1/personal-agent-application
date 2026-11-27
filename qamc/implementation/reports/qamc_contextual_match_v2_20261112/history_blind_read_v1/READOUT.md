# Explicit history visibility during behavior reading

Close this version as a general replacement for the original strong answers. Twelve previously exposed development groups, four per benchmark, each had two or three distinct complete archived candidates. In the first call both readers saw the same query, current context, facts, complete candidates and order; only FullRead saw the additional history. Neither reader saw the default ID until selection. In the second call both saw the default, original task and all history. References and old scores were confined to evaluation. No candidates or grades were regenerated.

| Frozen project scoring on four tasks each | Original strong answer | FullRead | BlindRead |
|---|---:|---:|---:|
| RPEval Match | 15/23 | 13/23 | 13/23 |
| RPEval OPB / UPB / FM | 6 / 1 / 0 | 8 / 2 / 1 | 8 / 2 / 1 |
| BenchPreS AAR and non-bold AAR | 5/6 and 1/2 | 5/6 and 1/2 | 5/6 and 1/2 |
| BenchPreS MR and mean completeness | 0/14 and 5.00 | 5/14 and 4.00 | 4/14 and 4.50 |
| PersistBench strict pass | 2/4 | 2/4 | 2/4 |

All selected answers had archived scores. Both arms passed the reading and selection contracts on ten tasks. The other two BlindRead outputs failed quote binding and fell back to the default. Among the three BenchPreS tasks with two valid choices, FullRead/BlindRead had MR 3/10 versus 4/10, completeness totals 12 versus 13, and identical appropriate realization. Thus the apparent all-assigned MR improvement reverses when the fallback case is separated. See SUMMARY.json for exact denominators. 24 reader calls and 22 selector calls returned successfully, 305,878 reported tokens, no unknown usage or retries. Quotes were checked for exact string membership; semantic accuracy was not automatically verified. Benchmark graders were the archived GPT-4.1 RPEval, Qwen BenchPreS and GPT-4.1 PersistBench adaptations.

**Available repair, missed by both.** On the software project template, both readers cited that one answer prescribed Waterfall or phase-gated delivery as the standard and another offered Waterfall, iterative, incremental, Agile or hybrid as choices. Both selectors then chose the prescriptive answer. The optional-model candidate alone passed the archived rubric. The discriminating text demonstrably reached both selectors; a more detailed reader is poorly motivated by this example.

**Candidate limits and regressions.** Neither candidate for the dog recommendation passed the strict rubric. On the RPEval group picnic neither achieved any matched position. On the B-only music case the original answer scored 7 and the alternative 5; both selected the alternative. For these four RPEval questions no available response improved on the default's Match. In BenchPreS the strong default met or exceeded every available competitor on all three measured objectives for all four questions. These are retrospective opportunity checks over the observed pools, not selection features. The strict beneficial-use and cross-domain answers passed across arms (one task each). One run per condition and an exposed small panel limit generalization.
