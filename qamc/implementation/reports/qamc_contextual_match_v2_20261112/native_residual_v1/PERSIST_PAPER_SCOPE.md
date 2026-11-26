# Paper scope and the key confirmation experiment

Status as of 2026-11-26: proposal for discussion. Live experiments and sealed data remain paused.

The proposed paper studies whether a task-conditioned decision to expose or withhold stored history changes the final response, and whether withholding reduces inappropriate use while preserving useful personalization and task completion. This is an inference-time intervention with a fixed memory store.

## Results that motivate the paper

- In the frozen PersistBench development panel, SELECTED_GEPA passed 13/13 common items against 10/13 for archived PB_RUBRIC and 9/13 for an exact-request fresh draw. Its three wins over archived PB_RUBRIC on the full 14-item comparison all used empty evidence. Under the common Rubric-informed generation strategy, selected exposure scored 13/14 against 11/14 for full history with an advisory note. Advisory presentation differed between arms. See [matched exposure](PERSIST_EXPOSURE_RESULTS.md) and [expansion](SELECTED_GEPA_EXPANSION_RESULTS.md).
- The project-template task tests whether a historical preference for Waterfall becomes the common default. The dog-adoption task tests whether aesthetic preference outranks welfare and household compatibility. The kickoff-email task additionally tests factual grounding about an attachment. It requires separate behavioral attribution and should not be counted as clean evidence of the same preference mechanism.
- The RPEval mixed-history comparison tied on Match at 41/71 and per-source execution had higher OPB severity. BenchPreS provides a separate realization boundary: an applicable concise or objective style can already be visible and still not appear in the output. See [mixed-history results](ROUND2_RPE_EXPOSURE_RESULTS.md).

## One confirmatory experiment

Freeze a single deployable task-conditioned switch, a development-independent source-group panel, baselines, per-track thresholds, generation repeats, and a beneficial-use and task-completion non-inferiority margin before opening any authorized evaluation data. Keep the actor backbone and scorer fixed. Use the official PersistBench Kimi route and published repetition/threshold protocol for claims against published results. Report any strict beneficial-use diagnostic separately if it differs from the official threshold. Record paired gains and losses by source group and category, missing or unsupported results, inference calls, and tokens.

Use the same switch output in the physical-exposure and full-history advisory arms. The same policy metadata and presentation must be visible to both; the exposure alone should change. This is the mechanism comparison. Include always-off to estimate the utility cost of abandoning memory, and full-history Rubric-informed and released GEPA as performance references. Compare against the closest feasible external static or query-dependent alternative, including released filtering and MemAdapter where implementation and budget parity can be established. Report mismatched published rows separately. An ordinary preparation control with the same inference budget tests whether any gain needs the switch.

The primary success criterion is a prespecified reduction in inappropriate use with both beneficial use and task quality protected. A valid exposure comparison plus a matched strong-baseline win supports a selective exposure method; a gain limited to sycophancy supports a narrower claim. If the matched strong defense ties, report the boundaries of the intervention and its costs rather than claiming a new performance leader. The three existing development wins cannot estimate a benchmark-wide effect.

External protocol and baselines: [PersistBench paper](https://proceedings.mlr.press/v306/pulipaka26a.html), [author implementation](https://github.com/ivaxi0s/PersistBench), [MemAdapter](https://arxiv.org/abs/2610.05162), [Structured Memory](https://openreview.net/pdf/70599ac9dad9e0dbf8f3c62262a500164dac2f31.pdf).
