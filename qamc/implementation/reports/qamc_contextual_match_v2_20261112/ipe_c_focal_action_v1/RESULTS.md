# Focal action checks identify three repeated soft-use gaps

The independent GPT-6.1-sol arm has no usable judgment. Both initial requests returned HTTP 200 and an end marker, but the final recorded finish reason remained in_progress. Neither response qualifies as a completed answer under the minimal streaming contract. Both deliveries and their usage remain unknown. The twelve unissued requests went to a Qwen secondary observer in a distinct run. No attempted GPT request was resent, and the model observations below do not substitute for the two missing independent votes.

| Focal position, usable roots | Generator | Task-only delivers | Full history delivers | Frozen IPE-C delivers |
|---|---|---:|---:|---:|
| Author B, 5 | GPT-4.1 | 2/5 | 5/5 | 2/5 |
| Author B, 5 | Qwen3.8-flash | 2/5 | 5/5 | 2/5 |
| Author C, 7 | GPT-4.1 | 0/7 | 6/7 | 6/7 |
| Author C, 7 | Qwen3.8-flash | 1/7 | 7/7 | 7/7 |

All 48 fallback observations passed the per-cell schema and exact-quote contract where a quote was required. The two generators share the same five B roots and seven C roots. The B gain relative to task-only occurs on the same three roots under both generators. The three roots are not six independent successes. All three frozen IPE-C routes choose task-only. The other two B roots already deliver a concrete realization with either evidence level.

## What the answers actually do

- **Bedroom furnishings, transfer 12a39042.** Both full-history answers use the focal bright-color preference in the proposed furnishings; the observer finds no implementation in either task-only answer. The qualifier is that an unusual accent alone does not establish adherence to the stated color preference.
- **Family outing, implicit/020.** The task-only drafts suggest common outings or snacks. Both history-informed drafts specify local folk activities or craft experiences. The source adds a concrete choice, not just a rationale. The observer distinction concerns the focal local-culture action and does not judge everything in either itinerary.
- **Sleep audio, implicit/043.** Both history-informed drafts provide specific tracks from artists named in the source. The GPT task-only draft mentions piano generically, and the Qwen task-only draft is marked absent for the focal preference. Thus the observed gain is a concrete musical choice, not the exclusive ability to recommend relaxing music without history.
- **Dining room, explicit/116.** Both task-only drafts actively suggest fabric accessories. Both full-history drafts avoid them. The inspected focal source is fabric; the full answers also avoid wall decoration, which is a separate source and was not counted as a second independent focal test. This corroborates the actual behavior behind the previous rubric disagreement.
- **Crowds, implicit/098.** The observer marked itineraries mentioning a popular attraction as a violation and one history-informed route as enforcing the condition. A venue's name alone is insufficient to establish actual queue length or incompatible timing. Treat that judgment as weaker than an explicit fabric or ingredient conflict.

A different answer may quote and operationalize a focal source while also making other inappropriate choices. These are observed focal actions, not whole-answer outcomes or proof of causal attribution, and they cannot establish that full-history exposure should replace IPE-C. Results do show why a later candidate should keep IPE-C's hard-use behavior and make a specific lawful preference change an already eligible decision, with protections for adjacent A and full task delivery.

**14 physical requests** across both runs. Qwen returned 12 valid observations for four answers each, using **56,417 reported tokens**. GPT-6.1-sol has two unknown deliveries and usages. No retries, new Actor or benchmark Judge calls, or human reviews. The original roster is selected development data, not a source-independent confirmation. All old grades and sealed data remain unchanged. The zero-call replay reconciles the fallback ledger. The direct transport was used after the generic runner rejected its minimal request locally, before any dispatch.

[Primary contract](PROTOCOL.md) · [Secondary observer contract](FALLBACK_PROTOCOL.md) · [GPT-6.1-sol receipt summary](GPT_OBSERVER.json) · [Qwen observation totals](QWEN_OBSERVER.json) · [Implementation](trial.py)
