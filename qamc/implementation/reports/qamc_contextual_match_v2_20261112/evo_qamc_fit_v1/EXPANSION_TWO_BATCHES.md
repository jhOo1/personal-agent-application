# Two expansion batches settled

The first 110 of 162 assigned exposed development tasks settled, with 84 RPEval, four BenchPreS and 22 PersistBench tasks assigned across the first two batches. Batch 3 has started under the frozen configuration. The unchanged run summary uses archived specialists and project scorer adaptations.

| Common primary result | Archived specialist | Direct | Parent | Scope |
|---|---:|---:|---:|---:|
| RPEval Match on 80/84 tasks | 253/407 | 180/407 | 198/407 | 203/407 |
| RPEval OPB / UPB / FM | 86 / 63 / 16 | 190 / 30 / 43 | 124 / 69 / 40 | 110 / 79 / 41 |
| BenchPreS AAR on four tasks, attributes only | 4/4 | 2/4 | 2/4 | 1/4 |
| PersistBench cross-domain pass | 8/8 | 3/8 | 6/8 | 8/8 |
| PersistBench sycophancy pass | 4/5 | 1/5 | 3/5 | 5/5 |
| PersistBench strict beneficial use | 7/7 | 7/7 | 7/7 | 7/7 |

The second RPEval batch alone reverses the Scope–parent Match ordering on its 41 all-arm common tasks, 103/208 versus 108/208. Across the two batches Scope wins seven source groups, loses five and ties 15 against the parent. Its leave-one-group position-weighted advantage ranges from 0 to +2.34 percentage points. On the 57 pairs without a known Judge flag from either method, both are 153/294; Scope has lower OPB (86 versus 91) and higher UPB (40 versus 34). On the 37 common tasks containing author C, Scope has 123/218 versus parent's 125/218, with UPB 46 versus 34. These task slices and aggregate grades do not assign individual C positions. Against archived IPE-C, Scope wins one source group, loses 15 and ties 11. The earlier RPEval improvement over the parent is therefore sensitive to new sources and flag handling.

PersistBench keeps the first-batch gains. The two-batch Scope advantage over PB_RUBRIC still corresponds to a single changed sycophancy outcome, the previously inspected project template. Scope adds no known failure on the common tracks. One second-batch PersistBench task has no complete comparison because both planned arms returned an evaluator response with no JSON object. BenchPreS still has only one profile and two complete all-arm rows. The attribute-only comparison retains the original result as a separate diagnostic. [First-batch behavior and format audit](EXPANSION_FIRST_BATCH.md)

The pairwise common equal-domain macro difference for Scope is +6.70 percentage points against the parent, +13.55 against Direct and −9.46 against the archived specialists. Under extreme missing-grade completion on the 110 assigned tasks, the Scope–parent interval is −2.39 to +13.06 points. Treat the comparison as provisional and keep the third batch frozen. PersistBench contributes most of the current macro gain, while RPEval and BenchPreS remain below the archived strong references.

The cumulative experiment has dispatched 879 actual requests with 3,281,539 reported tokens. There were 877 successful transport responses and two first-batch unknown deliveries. All 400 second-batch transports returned successfully; the two invalid PersistBench responses remain missing. No new response was generated for this readout, and no sealed cases were used.
