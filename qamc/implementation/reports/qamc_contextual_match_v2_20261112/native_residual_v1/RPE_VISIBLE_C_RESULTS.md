# RPEval single-source B-to-C instruction diagnostic

Eight exposed source groups were selected by deterministic hash among nonperfect baseline answers without recorded rubric flags that had a visible B instruction for an author-C source. The actor request changes one such instruction and retains all original evidence, other instructions, and task fields. Historical RP-route answers were reused. Selection did not establish that the corrected instruction addressed the exact misgraded position.

| Metric | Archived RP route | C promotion |
|---|---:|---:|
| Match | 34/56 | 36/56 |
| OPB severity | 15 | 15 |
| UPB severity | 7 | 4 |
| FM severity | 2 | 0 |

Three roots improved by one Match each, one lost one Match, and four tied. OPB was unchanged in aggregate but increased on two roots and decreased on two. All 16 physical requests succeeded (eight Actor, eight Judge), with 42,124 reported tokens. No retries or sealed data.

This is an author-label-conditioned development diagnostic with a historical single-draw baseline. It establishes score movement under the policy edit on this panel, with sampling variation and scorer inconsistencies still possible. It does not measure deployable selection. Inspect individual changes, verify the promoted constraint in each answer, and compare against a matched B-control rerun if needed before training an intervention chooser.
