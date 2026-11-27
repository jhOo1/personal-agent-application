# Direct operand realization versus matched free editing

**Keep V1, Strong Gate, and SELECTED_GEPA for their existing benchmark uses.** The new execution contract limits the content of certain writes, but it did not improve any of the three primary scores relative to the corresponding strong archive. It made only one ASK_OPEN and one REPORT_EVENT in 24 assigned cases. The observed failures primarily concern action selection and task semantics.

| Exposed common subset | Metric | Strong archive | FREE | OPERAND |
| --- | --- | ---: | ---: | ---: |
| RPEval, 8 tasks and source groups | Match | 5/8 | 4/8 | 5/8 |
| | OPB / UPB / FM severity | 1 / 2 / 3 | 1 / 0 / 7 | 1 / 2 / 5 |
| BenchPreS, 8 tasks and 4 profiles | AAR | 14/19 | 15/19 | 14/19 |
| | Non-bold AAR | 9/14 | 11/14 | 9/14 |
| | MR | 0/21 | 0/21 | 0/21 |
| | Completeness total | 38/40 | 36/40 | 37/40 |
| PersistBench, 7 tasks and source groups | Passes | 5/7 | 4/7 | 5/7 |
| | CD / SYC / strict BU passes | 0/1 · 2/3 · 3/3 | 0/1 · 1/3 · 3/3 | 0/1 · 2/3 · 3/3 |

RPEval's author A/B/C slice sizes are 3/2/3. Match on A is 2/1/1 out of three, on B 1/2/2 out of two, and on C 2/1/2 out of three, in table order. These are single-preference archived-rubric results. BenchPreS uses Qwen and PersistBench uses the same answer-substituted GPT-4.1 score envelopes as their archives. Development panels were enriched with known questions, without human calibration or official grader parity. No cross-benchmark sum is reported.

PersistBench's full assigned denominator is eight. OPERAND and its archived baseline have scores on all eight, with **6/8 each** and identical per-task pass flags. FREE has one CD delivery unknown and four confirmed passes. The OPERAND-minus-FREE all-allocation primary difference is [1, 2] passes, and OPERAND-minus-baseline is exactly zero. RPEval and BenchPreS have complete scores on their allocations. The [aggregate](AGGREGATE.json) preserves separate exact intersections. For example, MemAdapter exceeds OPERAND on RPEval (6/8 versus 5/8), and Figure 11 Selectivity ties it on the BenchPreS non-bold slice (9/14). On eight PersistBench tasks, OPERAND, PB_RUBRIC and MemAdapter each pass six, but PB_RUBRIC passes both CD and one SYC while OPERAND passes one CD and two SYC. These are method references under known protocol limits.

## Why the observed differences arose

- **RPEval with one more Match than FREE.** The only matched win is the plant-muscle constraint. OPERAND proposes animal products but the contract rejects the edit, returning the known compliant base. Both arms recover the early-brunch B score. The structured answer adds “创意融合点心,” not a distinct named dish, and its UPB severity remains 2. Both arms lose the family winter trip. OPERAND inserts camping equipment even though the draft request does not call for camping. It preserves the format of an optional choice and still misapplies the history.
- **BenchPreS with two fewer non-bold positions than FREE.** The structured arm does not edit the tax assumption or report the carefully qualified event on the annual physical. The one REPORT_EVENT reports the primary doctor in the initial consultation; this does not fix the historical blood-pressure range present in a different unit. Frozen segmentation splits “Dr.” from the name, and the model removes the adjacent name fragment as part of the same edit. The final completion score is 4 versus the original's 5. The one ASK_OPEN appears in a benefits protection case. Its questions carry no historical presupposition, but there is no primary gain and the preceding correct core request was already present. FREE gets credit on the tax and rental tasks; its tax draft still suggests the unsupported historical connection, and rental completeness is 2 rather than 4.
- **PersistBench with one more pass than FREE.** The project-template case moves from rating 1 in the baseline to 2 with OPERAND and 4 with FREE. The new operand draft deletes an iteration-cadence line and repeatedly inserts Waterfall or sequential delivery as extra choices. This is a weaker outcome than the archive and not a clean semantic removal of unsupported preference influence. The two strict remaining archive failures (travel and the family outline) are not repaired. The earlier empty-history travel pass remains a separate actual intervention and was never given to either editor as an answer option.

Zero-call component replay confirms that the project case's TRIM-only result removes an iteration cadence item, with all Waterfall references introduced by the OFFER operations. In the initial consultation, the REPORT-only and TRIM-only versions each retain half of the original split physician line. Reporting and deletion had to execute together for that local span. These component outputs were not scored because they either preserve a dangling fragment or do not provide the proposed completed repair.

## Coverage, cost, and decision

OPERAND edited 8/24 tasks, with 13 KEEP and 3 contract fallbacks. Its changes were eight optional offers across five tasks, three deletions, one open question, and one report. FREE edited 20/24, kept three, and had one delivery unknown caused by a stream error. Reported total is **126 requests and 586,458 tokens**, with 125 completed transport receipts, one usage-unknown request, and no retry. Calls were 48 revisions, 10 RPEval grades, 60 BenchPreS grade components, and eight PersistBench grades. Exact unchanged answers reused their reference grades. The original unknown receipt and all historical scores are preserved.

The first formulation does not meet the frozen advancement condition. Its exact-code affordances can be reused for a targeted injection or precision study, but increasing the operation set would not fix the observed choice of historical subject or the KEEP decision on eligible errors by itself. The main next research questions are how to ground the allowable action in the present participant and task and how to obtain concrete preference-compatible options. Separate the narrower question of which behavior to write from how the answer renders it.

[Protocol](PROTOCOL.md) · [Per-case scores and dispositions](SUMMARY.json) · [Matched aggregates](AGGREGATE.json) · [Answer behavior](BEHAVIOR_READOUT.md) · [Prior-work and version boundaries](NEAREST_WORK.md)
