# Re-solve a task after quarantining rejected decisions in candidate drafts

## Antecedents and actual intervention

Old joint synthesis already tested three drafts plus full original evidence. It treated a selected IPE-C answer as a starting point and its direct arm lost heavily on RPEval all-A. A later routed version could return a saved draft and did not beat the matched IPE-C. PersistBench premise and sentence quarantine removed raw history text. Neither varies the visibility of rejected content *in otherwise identical answer candidates* while using a whole-task generator with no privileged draft or saved-answer fallback. The new study holds that single mechanism contrast separate from the simpler possibility that ordinary synthesis is all that is needed.

- DIRECT_FUSION reads the verified candidate drafts, fixed query, context, Facts and original memory, and synthesizes one complete response.
- REVIEW_FUSION adds a one-call audit that returns only block identifiers and forwards the complete unchanged candidates alongside those identifiers.
- QUARANTINED_FUSION shares that audit and replaces just the rejected raw blocks with a constant placeholder in the candidate field.

The original source evidence remains available and unmodified in every arm. The audit does not emit free-text rationales, replacement plans or draft content. All arms use the identical final Actor prompt, model, settings and candidate order. Candidate blocks use original paragraph boundaries and preserve exact text, including Markdown. No block classification is guaranteed semantically correct. Matching text might remain elsewhere in other candidates or raw inputs. No guarantee against final disclosure follows from candidate-channel masking. If the review rejects nothing, all equal final wires share one physical response. If the audit fails, the three paths do not silently revert to an archived strong answer, and direct fusion still runs.

## Panel and costs

The initial freeze had a pre-dispatch capacity error with line-level blocks and recorded zero model requests. The separately frozen paragraph version checks request capacity; unsupported rows remain in the assigned denominator with no truncation.

Reuse the 18 locked crossover development sources, eight RPEval, six PersistBench and four BenchPreS, with no additions. Each task has a fixed three-path supply: Qwen Scope with no history, Qwen Scope with selected history, and Qwen Direct with selected history. All three have valid saved answers and recorded scores before the experiment. The three strongest archived specialists remain separate comparison outputs. Candidate order uses a fixed hash of source identity and answer text, and byte-identical candidates are deduplicated. Runtime inputs contain neither source identity nor any rubric label, score or known winning method. This available matched panel replaces the proposed 24-root enriched panel; it does not claim every enrolled task has demonstrated complementary behaviors.

Maximum stages are 18 audit, 54 final generation, 24 RPEval grades, 72 BenchPreS subgrades and 18 PersistBench grades. Reuse verified exact answers where applicable. Controller and Actor both use the working project Qwen 3.8 service, temperature zero and the inherited execution settings. The archived generation of the three proposals and its upstream steps are real cold-start costs. The audit adds one online call over direct fusion. The quoted limit is newly dispatched logical opportunity, not full deployment cost. PersistBench risk uses single adapted grades here; prior FR@3 remains separate.

## Decision rule

Compare all three to the archived strong answers and compare quarantined with reviewed fusion using the matched scopes. Count newly generated answers and positions strictly above the best recorded original candidate as an offline diagnostic. Inspect actual behavior for legal-use, feasibility and formal delivery independently of the recorded primary score. Promote candidate quarantine only if it adds a supported actual improvement relative to the shared unmasked control, across more than one source, without losing the intended protections. Retain ordinary full fusion if it yields the best protected native-style gains. Leave earlier answers, scopes, graders, and sealed inputs unchanged.

Earlier whole-draft synthesis is archived in the original repository. [Mixture-of-Agents](https://arxiv.org/abs/2406.04692) informs full-answer aggregation. This is a fixed-candidate adaptation.

[Crossover source study](BACKBONE_INTERFACE_FINAL.md)
