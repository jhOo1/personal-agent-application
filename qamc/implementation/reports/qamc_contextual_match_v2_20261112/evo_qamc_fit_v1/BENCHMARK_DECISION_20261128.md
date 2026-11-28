# Benchmark scope decision after the matched exposure study

Keep all three current tracks through the frozen joint-context comparison. Give BenchPreS an explicit role as a formal-delivery effectiveness and regression track. In a paper centered on changes in contextual applicability, use RPEval for preference-use intensity and PersistBench for leakage, sycophancy, and beneficial use. BenchPreS currently does not supply direct within-profile evidence of an applicability reversal.

## What the matched runs established

- **RPEval:** on the same 122 exposed development tasks, Scope with no history scored 314/624, selected history 294/624, full history 278/624, and ordinary Gate 300/624. Archived IPE-C scored 387/624. Even hindsight choice over the three new Scope endpoints reaches only 371/624. On all-A tasks, clearing history yielded 151/236 versus 80/236 with selected history. On tasks containing a C obligation the respective figures were 132/304 and 173/304, across all positions in those tasks. Clearing history trades misuse against missed obligations. IPE-C uses a different generation contract. Under the pre-existing scoring-flag filter the endpoint ceiling and specialist were 211/332 and 207/332.
- **BenchPreS:** the four matched expansion tasks all came from one profile. The ordinary Gate cleared history on all four, giving AAR 0/4, versus 1/4 selected, 3/4 full and 4/4 for the archived strong Gate. MR was 0/16 throughout. Mean completeness was 5 on three jointly valid completeness records. The separate locked release audit counted 0 reference label flips across 37,050 within-profile same-preference comparisons. Those comparisons reuse the same 10 profiles and 390 tasks. The score can measure implementation and suppression across formal tasks, while the label variation cannot identify a within-profile applicability reversal. The release uses DeepSeek-R1 for preference scoring. The local Qwen adaptation and unreliable official scoring route constrain publication-level comparisons.
- **PersistBench:** on 29 jointly valid development tasks, no history passed 17, selected and ordinary Gate passed all 29, full history 26, archived PB_RUBRIC 28. Strict beneficial use falls from 13/13 with selected evidence to 1/13 with no history. This is a useful performance and protection signal, with substantial ceiling on that slice and scores from a frozen GPT-4.1 rubric adaptation.

The different results are compatible with a shared method for task-conditioned memory exposure and realization. They disconfirm universal history suppression and show that a better selector alone has limited headroom with the current fixed Actor context. They do not identify the model provider as a cause. A fixed-source, fixed-Actor test that changes only the generated plan is now frozen separately.

## When a scope change is justified

Consider reducing BenchPreS to a secondary guardrail if the paper's central claim is counterfactual applicability and the audited release lacks that contrast, or if the official protocol remains unavailable for the required external comparison. Retain its archived MR, AAR and task completeness evidence. If the central contribution includes appropriate formal expression, keep it in the main study and use a profile-diverse comparison before drawing conclusions.

PairPref free generation is the first replacement to qualify for a claim about contextual reversal. The preference and request stay fixed while the situation changes, and the generated pair is scored for matched preference use and task fit. Its published procedure excludes answers that hedge with both branches. Qualify downloadable author data and scorer reproducibility, group by target preference, report coverage before hedging exclusions, and run the external comparator under identical rules. No released runnable data or scorer was verified in this check. PairPref does not directly substitute for a third-party-expression evaluation. Poor scores on an existing track and better scores on a replacement are insufficient grounds for removing a track.

## Joint review and PairPref asset check

QAMC-v3.2 independently agreed that the zero-flip audit warrants excluding BenchPreS from a direct test of contextual reversal while retaining its formal-delivery track. The PairPref authors name the evaluation file and the 1,227-pair export in Appendix B. The arXiv source archive was downloaded and its 60 member names examined. It did not contain a JSONL, CSV, Python file or ZIP. Searches for an author distribution of the named export or a runnable scorer did not yield a verified source. The authors also state in Appendix H that their human audit did not annotate freely generated answers. These facts leave the applicability design promising and the replacement unqualified.

If the assets become available, compare the author's stronger Mitigate prompt (not just plain full-history generation) on the same cases and evaluator. Keep the author's retained-pair results alongside total assigned coverage, with the frequency of the hedging exclusion and a missingness sensitivity. The reported mitigation comparison is separate from the default table, and model substitutions require new protocol-matched results.

## Evidence

- [Matched exposure results](EXPOSURE_FINAL.md)
- [Prior scope review and release audit provenance](BENCHMARK_SCOPE_REVIEW.md)
- [BenchPreS evaluation protocol](https://arxiv.org/html/2603.16557#S3.SS3)
- [PersistBench paper](https://proceedings.mlr.press/v306/pulipaka26a.html)
- [PairPref experimental protocol](https://arxiv.org/html/2609.34526v1#S4.SS1)
- [Joint Context Control freeze](JOINT_CONTEXT_PROTOCOL.md)

No benchmark was dropped, no sealed item was accessed, and no model requests were made for this scope review.
