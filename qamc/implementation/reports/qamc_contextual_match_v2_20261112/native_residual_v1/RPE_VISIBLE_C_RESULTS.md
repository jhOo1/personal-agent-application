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

## Behavior audit of the four Match changes

The saved request comparison confirms exactly one B-to-C policy change on all eight roots, with identical source evidence. In the four non-ties:

- Dining-room layout (implicit/139): neither draft recommends plants, the promoted target. The new grade improves by one while still citing other preferences. No target repair was established.
- Office-worker meals (explicit/006): both drafts avoid seafood and seafood-derived seasonings. Promotion changes avoidance into an explicit hard rule, but the new grade loses one Match. The grader acknowledges the target restriction.
- Family outing (explicit/073): the old draft already recommends walk-in stops and avoiding queues. The new draft adds a specific instruction to switch destinations instead of waiting if crowded. This is a verified operational strengthening of the target; the new Judge explanation assigns inconsistent descriptions to position two, so the Match increase cannot be attributed cleanly to that strengthening.
- Dinner recipe (explicit/097): the old draft explicitly excludes chili and pepper. The new Judge rationale contradicts the recorded CAACAA labels and treats cooked fish and shrimp as raw-food use. The one-point increase cannot establish repair of the promoted spice restriction.

Only the family outing shows an unambiguous new contingency tied to the target among the three improved grades. Do not treat the observed +2 as a verified behavioral improvement or use these four outcomes as clean supervision without additional checks.

## Additional B-control sample

A separately logged draw reused the exact original B-policy requests on the same eight roots and the same grading implementation. This draw was collected after the promotion result, without randomized temporal interleaving. Match was 36/56 for both the new B draw and C promotion, versus 34/56 for the archived B draw. C won one root and lost one against the new B draw. OPB was 12 for new B versus 15 for C, UPB 7 versus 4, and FM 1 versus 0. The original two-point Match gain is reproduced by unchanged inputs, so the pilot provides no demonstrated Match advantage for promotion over resampling. The positive family-outing behavior remains a case-level observation. Sixteen new requests succeeded, with 33,021 reported tokens. All old results and the sealed boundary were preserved.
