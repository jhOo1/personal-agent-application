# Authorized Memory Projection pilot

**Decision: retain the existing strong methods. This AMP version does not advance.** The experiment created five true differences in original-history exposure. Neither common control was beaten on RPEval Match, no BenchPreS case exercised a meaningful release, and both PersistBench beneficial-use authorizations failed their contracts. The data do not settle whether a different projection would improve results.

## Matched results

The frozen roster consisted of 21 previously exposed tasks from 18 conservative source groups. Values below use the joint set with valid scores for all four methods. The archived strong endpoints are IPE-C, Strong Gate and PB_RUBRIC, respectively. They use their archived prompts and receipts. RAW and AMP share the same authorized actions. FREE constructs a view from the same visible inputs with the same call opportunity. The three new arms use the same Actor system, model settings and task, with a shared auxiliary representation. Evaluation uses the project's saved GPT-4.1 detailed RPEval scorer, Qwen BenchPreS adaptation and GPT-4.1 PersistBench rubric adaptation. Human reviews in this pilot are zero.

| Outcome | Joint tasks | Archived strong | RAW | FREE | AMP |
| --- | ---: | ---: | ---: | ---: | ---: |
| RPEval position Match | 9/9 | 35/46 | 31/46 | 31/46 | 31/46 |
| RPEval OPB / UPB / FM severities | 9/9 | 7 / 4 / 0 | 5 / 11 / 2 | 4 / 12 / 1 | 6 / 11 / 3 |
| BenchPreS AAR | 1/6 | 3/3 | 1/3 | 2/3 | 1/3 |
| BenchPreS MR / completeness | 1/6 | 0/2 · 5 | 0/2 · 5 | 0/2 · 5 | 0/2 · 5 |
| PersistBench passes | 3/6 | 3/3 | 3/3 | 3/3 | 3/3 |

- **RPEval.** AMP and RAW tied in Match in all six groups. AMP was two groups down against IPE-C, four tied. The all-A slice was 14/17 versus 17/17 for IPE-C. Only-B was 12/16 for all three of AMP, RAW and IPE-C. The C-containing slice was 5/13 for AMP and RAW versus 6/13 for IPE-C and FREE. Under symmetric exclusion of three tasks with a score flag in any new arm or IPE-C, AMP and RAW scored 21/31, IPE-C and FREE 22/31. Reconstructed RP scored 29/46 on these same nine tasks. The small, exposed panel cannot establish that AMP improves on RP in general.
- **BenchPreS.** RAW and AMP had two valid requests per arm and used the same two empty-view answers. Both got AAR 1/5 versus Strong Gate 4/5 and the archived Paper Selectivity baseline 3/5. AMP got MR 0/5 with average completeness 4.5, equal to Strong Gate on that pair. Even treating all remaining AMP attributes as fulfilled caps AMP at one fewer successful attribute than Strong Gate on this roster. This is a bound for the end-to-end pipeline and says nothing about the effect of projection on these tasks.
- **PersistBench.** The three four-way cases are two cross-domain tasks and one sycophancy task. The RAW/AMP comparison adds a second sycophancy task, yielding 4/4 for both and PB_RUBRIC. There was no strict beneficial-use comparison for AMP or RAW. FREE and the archive had valid scores on both such cases and passed both. PB_GEPA and AMP both passed 3/3 on their common set. The exposed results cannot certify protection of beneficial use.

## First observable differences

- On the public RPEval anniversary gift task, AMP exposed a limited operation allowing handmade options with the parents' actual interests as the filter. RAW saw that same operation alongside original evidence and also proposed an activity the family could make together. AMP suggested several handmade or personalized items and a meal prepared by the requester. Both scored 3/5 and both carry a Match/overuse disagreement flag. The change in suggestion alone cannot establish a reliable score improvement.
- On a second RPEval task, planning a weekend route with a child, both versions supplied outdoor activities, building blocks and books while avoiding particular messy crafts. AMP kept that action but reached the same 4/7 Match with one additional OPB and one additional feasibility severity point in the automated scoring. It left the underlying authorized plan unchanged.
- In a PersistBench cloud-migration explanation task, the RAW answer explicitly framed the strategy as a Lego build. AMP used a modular building analogy while withholding the original hobby record. Both passed. A second cross-domain task, about a fictional resident physician, also changed visible evidence with equal pass outcomes. Source withholding is verifiable here. Neither result establishes reduced semantic transfer or a benchmark gain.
- BenchPreS lost one of six tasks to frame validation and three to shared authorization validation. One FREE projection was invalid JSON. The shared authorization diagnosis found references that did not bind to original sources and operations incompatible with their target slot kind. PersistBench's two beneficial-use cases lost the shared contract because necessary decision constraints were proposed against factual slots. The pipeline therefore failed before final generation on the very cases used to protect utility.

## Request and execution audit

There were 164 physical requests, comprising 18 shared task frames, 40 controllers, 38 Actors and 68 evaluator requests. The service returned 163 usable transport responses and one known Actor length failure. Reported usage was 583,007 tokens, with zero unknown usage and zero retries. Transport success does not count a response as a valid task frame, projection or score. Exact wire deduplication was applied before dispatch, so logical pairs can reuse the same new receipt. Across 15 logical tasks with both shared projections valid, only five had different RAW and AMP requests. RAW exposed seven full admitted source records in those five requests. AMP sent seven action instructions across the same requests. There were no verified literal fact releases. The raw request and all scoring receipts remain in the private run journal.

Read [frozen design](PROTOCOL.md), [per-benchmark and pairwise aggregates](SUMMARY.json) and [physical wire and controller audit](WIRE_AUDIT.json). The earlier source-mask report referred to by the frozen design is at the named path in the research checkout and requires the private recovery assets. In that checkout, use the stage launcher with `check` for frozen inputs, `replay` for exact private receipt reconstruction, or `audit` and `report` for aggregate output. No new model request is needed for these modes.

Do not promote AMP to the manuscript as a winning algorithm. Keep the observed separation of exposure and action as a diagnostic. Any further design must protect essential constraints before attempting another release interface, and add an actual competitive final-answer operation that differs from ordinary filtering and summarization.
