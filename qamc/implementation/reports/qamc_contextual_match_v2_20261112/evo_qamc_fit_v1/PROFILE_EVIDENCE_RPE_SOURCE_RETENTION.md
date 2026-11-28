# Which RPEval sources survive profile refinement?

Evaluation-only join of the seven returned RPEval refinements with original ordered source records and the archived author labels. The eighth assigned RPEval case starts with empty selected history and does not dispatch a refiner. The script requires identical source IDs and raw text on the subset that enters the shared refiner. A quoted source is counted once even if it supports multiple points. These labels never enter the Refiner or either Actor request.

| Author label | Original pool | Selected and seen by the refiner | Still represented by an exact quote |
| --- | ---: | ---: | ---: |
| A, ignore | 26 | 12 | 10 |
| B, support | 4 | 4 | 4 |
| C, dominate within scope | 3 | 3 | 3 |

The refiner removes two A sources, both on C-containing tasks. Across the three all-A tasks with history, it retains every one of the seven selected A sources. Neither legitimate B nor C disappears at the source-ID level in this small panel. That does not certify claim meaning, the scope of the extracted substring, or actual implementation in the answer. The 17 represented sources yield 29 profile points; repeated extraction can increase the salience of a source even when the number of source IDs does not grow.

The Actor-level question is therefore whether returning provenance limits the effect of inapplicable evidence or better realizes the B/C sources already represented. The profile-only arm already has the rewritten points. Expected outcomes are constrained by the [recorded example where a work qualifier is lost](PROFILE_EVIDENCE_REFINER_TRACE.md) and by the all-A retention above. No finished answer or grade was used for these counts. Do not generalize from seven deliberately exposed cases.

Run `bash run.sh profile-evidence-label-audit` within the original experiment archive. No model requests, no grade modification, and no sealed inputs.
