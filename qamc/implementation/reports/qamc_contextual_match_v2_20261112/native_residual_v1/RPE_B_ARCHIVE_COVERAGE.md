# RPEval hidden B archive coverage

A zero-call join used the exact Actor census and four scored intervention archives: source-local re-entry format recovery, supervised recovery, incremental pair, and fixed-source strength. Keys were task UID and selected source ID. A hit required an existing grade and an author-B source marked HIDDEN for the baseline Actor.

The census has 44 hidden-B positions across 14 conservative source groups. The four archives cover 14 distinct task/source pairs across 13 groups, leaving 30 positions without a hit across 11 groups. Only one group has no scored hit anywhere in this join. This is a reuse inventory, not a proof of equivalent Actor requests, a semantic success rate, or an inventory of confirmed position-level mistakes. The majority of unused positions share a group with an earlier intervention. Treat any additional same-group comparison as development and reuse exact matching actor/scorer receipts before dispatch.

Before running a development-only oracle, recover the raw per-position Judge artifacts for the baseline. The aggregate Match payload stores counts, not the emitted label sequence. Do not classify a hidden B as missed simply because it was absent from input. Check that its position was actually marked wrong, preserve conflicts between Judge notes and label sequences, and keep author labels out of the deployed method.

## Uniquely locatable misses and scored reuse

The companion [aggregate-grade bounds audit](audit_hidden_b_misses.py) identifies eight development tasks across six conservative source groups where there is exactly one hidden B and every compatible interpretation of Match, OPB, UPB and RII marks it wrong. Five have a scored intervention exposing that same source, and three do not have a hit in the four audited archives. This is conditional on consistency of the archived rubric fields.

Across the five reused tasks, total Match increased in three cases (explicit/067, explicit/071, implicit/105) and tied in two (explicit/080, implicit/029). Every observed increase also came with higher reported OPB. The archived interventions have different Actor instructions and some share answers, so the result is descriptive and scores cannot be attributed solely to the B exposure. Missing instances must not be read as failures. The two previously flagged Judge issues for implicit/029 and implicit/105 still apply. Three unmatched development tasks are available for an exact single-source diagnostic after checking the wider request archive. No new request was made for this join.
