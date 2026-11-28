# Keep current commitments when admitting historical evidence

This test addresses a difference between memories relevant to the topic and memories allowed to undo a decision which the current request already made. The Rome and Florence case illustrates the issue: the requester asked to plan those destinations with a current partner, and a lone source from an earlier relationship pushed the answer to another city. The topic was relevant. The earlier decision had different scope. This trial does not use that example in the online prompt.

One shared model call returns the normal relevance selection and, separately, possible conflicts with explicitly settled current decisions. The program verifies exact spans on both the Query and implicated source. It can only remove a source that the relevance arm would expose. A source with another valid use should survive; this and same-decision status remain model judgments. Conflicts with unstated intentions, mutable preferences or merely related topics do not qualify. There are no candidate answer rewrites, no action patches, no new stored information and no model weight changes.

- Both arms generate with the same Qwen prompt, model alias, decoding and task facts. The relevance arm sees the normal retained set. The commitment arm sees the same set minus verified conflicting sources. Neither receives the audit, explanatory text, author labels, prior answers or grades. The surviving original sources remain byte-identical and in the original order. Both arms share a physical call when their input is identical.
- On the previously exposed 92-row strong-answer archive, select three nonperfect RPEval all-A and three nonperfect B/C roots, four PersistBench sycophancy roots already failing PB_RUBRIC and two strict beneficial-use controls, and two BenchPreS formal delivery roots. Use deterministic UID hashes and one case per conservative source group per benchmark. Archived scores define those development strata and a reference only. The old strong answers are reported as separate method references because the Actor prompt differs. The fixed original score adaptations are unchanged.
- Proceed to new final answers only if at least two roots have different exact Actor requests and at least one root is from RPEval or PersistBench. That trigger is coverage, not an advance decision. Do not call a suppressed memory causal unless exposure is matched and behavior agrees. To advance, require actual preservation of the current decision at two distinct roots relative to both reference paths, a native metric gain over the matched relevance arm, and no observed systematic loss of useful B/C, strict beneficial use, task completeness or factual delivery. Record uncertainty and any failures on all assigned roots. This is a directed development test.
- Preserve prior results, the sealed inventory and the physical request journal. Maximum 14 shared audits, 28 final actors and 48 scoring requests. Unknown deliveries remain unknown and are not redispatched.

The previous singleton veto discarded any one selected source without a concrete conflict test and had no confirmed source-level win. Referent-bundle routing selected among existing complete answers and required positive evidence to turn history on. This intervention instead removes a specific incompatible input only when the settled current value is directly quoteable, and compares the resulting answer with the same Actor reading its otherwise identical set.

Run the fixed dependency entry from the original checkout with the private archive:

```bash
bash reports/qamc_contextual_match_v2_20261112/evo_qamc_fit_v1/run.sh current-commitment-gate check
bash reports/qamc_contextual_match_v2_20261112/evo_qamc_fit_v1/run.sh current-commitment-gate run
```
