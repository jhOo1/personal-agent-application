# Comparable three-benchmark evidence and remaining questions

This audit reuses saved scores. It identifies the strongest reproducible references and where protocol parity still fails. No model calls, revisions or sealed-data access were made.

## RPEval on one exact five-method intersection

Use the frozen 300-case IPE-C endpoint archive and the four comparator rows from the formal multi-preference development archive. The intersection has 214 tasks and 1,144 author positions. Four tasks lack labels. Another 82 have a strict Match missing in at least one method, with overlapping missing counts IPE-C 14, RP 9, Des2Gen 10, MemAdapter 22, Strong Gate 52. Do not treat these as semantic errors. All common severity fields below are present.

| Method | Match overall / 1144 | All A / 426 | Only B / 193 | Contains C / 525 | OPB / UPB / FM severity sums |
|---|---:|---:|---:|---:|---:|
| IPE-C | **761** | **334** | **111** | 316 | 202 / 176 / 39 |
| RP-Reasoner reconstruction | 653 | 228 | 107 | **318** | 300 / 163 / 42 |
| Des2Gen reconstruction | 538 | 125 | 96 | 317 | 467 / 102 / 96 |
| MemAdapter adaptation | 510 | 86 | 108 | 316 | 384 / 182 / 102 |
| Strong Gate (`GEPA_SELECTED_BOUNDS`) | 512 | 107 | 96 | 309 | 466 / 135 / 120 |

IPE-C versus RP: 31/10/173 task wins/losses/ties and 18/5/22 group wins/losses/ties when summing the paired Match difference inside each conservative source group. Those groups are not verified independent participants or a significance calculation. The overall +108 positions split into all-A +106, only-B +4 and contains-C −2. On the larger original RP pair set, the corresponding deltas are +133, −2 and −2. Both views support selective avoidance of irrelevant history; the B result depends on the intersection and does not establish reliable beneficial use. The severity sums and native position denominators differ in meaning. Several alternatives have lower UPB, including on C-bearing tasks. No conclusion here treats the original RP Actor as an independent whole-policy control: it is IPE-C's own memory-on endpoint.

The fixed published short Judge source did not request Match, returned none in 24 bridge requests, and interpreted acronyms differently from the detailed project rubric. The released default generation prompt was separately reproduced on 24 exposed explicit cases and scored 61/131, versus RP reconstruction 82/131 under the adapted detailed Judge. Preserve full RP reconstruction as the stronger local opponent and the release-path run as a distinct reproducibility check.

Reproduce the new intersection with `python3 compare_rpe_common_panel.py` after restoring the saved `ipe_c_two_endpoint_completion_v1/RESULTS.json` and `rpeval_formal_multi_coverage_v1/RESULT_ROWS.json` from the original workspace. The release and scorer artifacts are under `author_protocol_ipe_c_v1/RELEASE_READOUT.md` and `rpeval_released_judge_bridge_v1/READOUT.md` in that workspace.

## BenchPreS and PersistBench

| Benchmark and comparison | Strongest observed evidence in the project protocol | Remaining condition for a paper-protocol claim |
|---|---|---|
| BenchPreS, Strong Gate vs published Figure 11 Selectivity | 40 common tasks. Gate MR 1/132 vs 13/132, AAR 58/68 vs 54/68; both completeness 4.875. Non-bold AAR is 35/45 vs 36/45, so the reduction in misuse does not demonstrate universally better realization. | The published temperature-1 triple generation and DeepSeek-R1 scoring still have no verified complete run. Existing data use one temperature-0 generation and Qwen scores. The three-draw aggregation passed offline fixture tests only. |
| PersistBench, PB_RUBRIC vs adapted external pipelines | PB_RUBRIC 43/48 vs full PB_GEPA 39/48 and 43/49 vs full MemAdapter 38/49. SELECTED_GEPA gives 14/14 vs 11/14 on a failure-enriched panel but 18/19 vs 19/19 on an expanded protection panel. Keep separate denominators. | The local reference requires GPT-4.1 rubric adaptation with strict beneficial use. Kimi K2 Thinking, the official provider envelope, and the specified repeated CD/SYC draws are not jointly validated. The official-score comparison is unavailable. |

BenchPreS source files after private restore: `benchpres_matched_paper_v1/RESULTS.md`, `benchpres_r1_minimal_v1/README.md`, `benchpres_native_aggregation_preflight_v1/README.md`. For PersistBench see [author controls and request parity](PERSIST_STRONG_BASE_AUDIT.md), [MemAdapter bridge](PERSIST_MEMADAPTER_ALIGNMENT_RESULTS.md), [enriched comparison](SELECTED_GEPA_EXPANSION_RESULTS.md) and [expanded comparison](PERSIST_PERFORMANCE_RESULTS.md). Route failures are observations at the archived times, not proof of permanent service unavailability.

## Decision boundary

The saved endpoints support a paper result about selective exposure preventing errors from irrelevant history. RPEval gives the broadest measured gain. PersistBench offers supporting selective-abstention cases and a counterexample when a topically related history changes scope. BenchPreS supplies a case where delivering applicable evidence can still leave some legitimate preferences unrealized. These are distinct tests of the same question with separate methods and scorers. They cannot be merged into one three-benchmark win, a claim that the fixed-memory algorithm consistently protects legal B/C, or acceptance evidence.

The next parity extension with high evidential value is to verify an exact official grader route and then score paired saved answers under a frozen matched envelope while reporting any original sampling mismatch. Author-specific score files and test partitions are a prerequisite for leaderboard figures, and no new sealed data are authorized here. Until an exact route or new bench-compatible information is verified, results remain paired development evidence.
