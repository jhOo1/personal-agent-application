# Compare task-specific profile compression with restoration of original evidence

## Prior work and deliberate differences

The [AlignXada paper](https://arxiv.org/abs/2608.09507) describes support-set induction of a textual profile-refinement policy, deployed with frozen models. The [author implementation at b9b8a9e](https://github.com/AntResearchNLP/AlignX-Family/tree/b9b8a9ebaaa2b83bd55d40a5d25e7587e8c6944d/AlignXada) includes the optimizer, rewrite prompts, and adapters for its tasks. The source tree has no evaluated frozen policy artifact for these three benchmarks. This test independently adapts the profile-refinement idea, with the existing raw memory as input and one untrained policy. It does not run AlignXada's verbal policy induction, reconstruct a universal profile, alter the user memory store or claim to evaluate the authors' method. This is a matched engineering and behavioral experiment.

Earlier work found that profile or quote fidelity cannot guarantee lawful use. A true quote can describe the wrong person, preserve only part of a condition, or be inapplicable. The [candidate pointer experiment](DECISION_QUARANTINED_SYNTHESIS_RESULTS.md) edited or quarantined candidate answers. The current intervention operates on the historical-evidence input before any answer is written. Its two arms receive the same descriptions, so their difference measures the joint effect of exposing the historical quotation and its extra tokens. It does not separate quote placement, length or content.

## Execution

Use the same 18 exposed roots as the recent crossover, with the exact archived Qwen Direct task and already selected original memory. The input query, current context, task facts and selected record order are fixed. Any empty original history uses the exact existing Direct response in both arms. For nonempty memory, both arms share one Refiner generating up to six short profile points and one continuous source span per point. The code accepts only exact substrings of the indicated selected source and verifies the output schema. Full contract failure leaves both arms unavailable; there is no request repair. An empty but valid refinement gives both arms the same exact Actor request.

- **PROFILE:** the Actor sees the task and the concise profile points, with the original source IDs.
- **PROFILE_AND_QUOTES:** the Actor sees the exact same task and points, and their supporting original spans. The Actor prompt, underlying alias, cap and temperature are identical between the fresh arms.
- **Archived references:** exact uncompressed Direct response and strong IPE-C/Strong Gate/PB_RUBRIC, scored as before. They are method-level references, not same-budget controls for the fresh Actor envelope.

No stored output becomes an input to the refiner, no benchmark labels or Judge rationale enter generation, and no sealed examples are used. The two fresh arms share the cost of the refiner and use one Actor apiece. Caps are 18 profile requests, 36 Actor, 16 RPEval judgments, 48 BenchPreS subgrades and 12 PersistBench judgments. Reuse identical completed Actor and Judge wires within the run. Preserve failures and no reissues.

## Observable protection checks

- For the family café and interview tasks, inspect whether the draft turns a requester preference into the main decision rule. Recognizing a preference does not qualify as implementing it appropriately.
- For the French and Korean learning tasks, check actual course features or exercises and whether format and access constraints are preserved. Distinguish the request's own time-pressure instruction from a personalized change.
- For benefits correspondence, preserve both current status updates and apply only legitimate style. For the engineering principles memo, separate recorded subjective preferences from institutional or public facts. For strict beneficial use, check that birthday heritage and eligible gift requirements survive.

Judge the matched new arms on benchmark-specific metrics and independently check their necessary behavior. Advancement requires credible actual improvement across multiple source roots with legitimate B/C, strict beneficial use, and task completeness protected. A quote that merely repeats a supported claim without changing what the answer does is a null mechanism. Results limited to one benchmark or one adapted scorer are limited accordingly.
