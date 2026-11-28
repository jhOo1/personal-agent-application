# Separate current task from historical evidence in the native message array

## Intervention

Test whether the Actor gives the current task more weight when its input has a separate message boundary. The fixed panel and Qwen Direct with selected history come from the earlier backbone crossover. Every new arm keeps the same selected evidence, original query, current context, facts, ordered source records, generator alias, sampling settings and cap. All receive the same system clarification that the current task has authority and the historical evidence is background, regardless of order or boundary.

| Arm | Native user messages |
| --- | --- |
| TASK_FIRST | One message containing the current task record, then the history record |
| TASK_LAST | One message containing the history record, then the current task record |
| TASK_SEPARATE | Two adjacent user messages: the same history record, then the same current task record |

Record bytes match across the three arms. TASK_LAST and TASK_SEPARATE differ in the API message boundary and its implied serialization, with the same record order. TASK_FIRST versus TASK_LAST examines order under the single-message form. There is only one generation call per arm and no artificial assistant turn. A gateway may coalesce adjacent user messages. Success shows an effect of the submitted interface on this route; neither a tie nor a win identifies its private chat template. The archived Direct and the three strong specialists are method references, because the fresh arms share a changed system clarification and envelope. The earlier [RPEval evidence-position intervention](../evidence_position_rpeval_v1/PROTOCOL.md) reordered source and policy rows while keeping the task in place. No source or policy row moves relative to another here. [Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/) and [Lost in Conversation](https://arxiv.org/abs/2505.06120) motivate controlling order and turns; their tasks and treatments differ from this proposal.

## Frozen comparison

Use the 18 previously exposed crossover roots: eight RPEval, four BenchPreS and six PersistBench. Rebuild the saved selected Direct request and verify its digest before constructing any arm. Use established visible information only. Old scores and any author labels stay in evaluation. If one new arm exceeds the request capacity, assign that root missing in all new arms. No context truncation or sealed data.

Hypotheses inspectable on existing cases:

- A current family or companion task can regain practical priority over a requester's prior habits, while an applicable restriction still changes the actual choice. RPEval all-A and contains-C cases bound the two sides.
- A formal letter should preserve the current request and facts, including the intended audience, without applying an unsuitable style just because it appears near the current task.
- A team strategy or public exhibit should remain grounded in its present purpose. A strict beneficial-use request that explicitly calls for personalized details should still implement those details.

Use paired valid results under frozen adapters. Report RPEval Match and OPB, UPB and FM by stratum, BenchPreS AAR, MR and completion, and PersistBench failures per track including strict BU. Inspect actual case behavior before advancing a candidate. A separation improvement needs gains on multiple roots relative to TASK_LAST, with no repeated loss of legitimate constraints, strict utility or formal delivery. If TASK_LAST gains but TASK_SEPARATE adds nothing, report the result as order sensitivity. A gain limited to the shared clarifying prompt cannot be separated from the different old envelope. Retain original specialists where the new variant fails to reach them. No new selector and no full-draft synthesis.

Stage ceilings are 54 Actor, 24 RPEval grades, 72 BenchPreS subgrades and 18 PersistBench grades. The existing runner handles pacing, exact on-run deduplication and retained attempts. The new arms have independent wire hashes. Use the exact archived grade for an identical returned answer when available. Record any rejected multi-message inputs as transport outcomes. Resume only the same frozen ledger with failed deliveries preserved.
