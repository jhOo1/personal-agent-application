# Expansion behavior traces before scoring

Read saved first-batch answers for the first task in each RPEval stratum with successful receipts in all three arms at review time, following frozen batch order. The abbreviated descriptions preserve the behavioral differences. This was an unblinded read with no new model requests; the examples are not estimates of error frequency. See [the request audit and frozen protocol](EXPANSION_PROTOCOL.md).

| Task and author labels | Shared history | Parent and Scope behavior | Direct behavior |
|---|---|---|---|
| Father's birthday restaurant, explicit/019, AAAAA | Three A entries about dining alone in quiet, having control over choices and eating efficiently | Both prioritize a private room and group seating. Parent explicitly rejects the requester's solo quick-meal pattern as an organizing principle. Scope explicitly invokes the requester's quiet, autonomous and low-effort style as a reason to set the group's restaurant requirements. A private room could be justified independently, so the observable change is the use of historical preferences to justify a group decision. | Also explicitly draws on the requester's efficient, low-complexity dining preferences in the recommendation. |
| Student dietary advice for stomach discomfort, implicit/045, AAAACA | All six sources reach every arm, including a C source saying the user avoids drinks and desserts containing coffee or tea, even small additions | Both provide substantial task advice. Parent warns against strong coffee and tea especially on an empty stomach. Scope lists coffee and strong tea among foods and drinks to limit. Neither states the full no-coffee-or-tea ingredient exclusion expressed by the source. | Adds specific advice to avoid coffee and tea ingredients, including common tea categories, while suggesting alternatives. The text frames this as conditional on sensitivity, so the source strength is still not fully carried through. |
| Family Spring Festival trip to Hainan, implicit/086, BAAAAAA | Selected sources include the B interest in local folk culture and A histories about nightlife and occasional challenging sports | Both give a usable family itinerary. Scope incorporates a museum and local cultural sites in the main itinerary. It offers surfing and paddleboarding conditionally if family members want those activities. The example does not establish that Scope cleanly rejects all A influences. | Includes the same broad family itinerary needs and also features folk culture, nightlife and light sports prominently. |

The birthday case falsifies a hard guarantee that Scope keeps a requester's preferences out of shared decisions. The student case distinguishes C exposure from C execution and confirms that replacing selection alone cannot repair this example. Check the frozen grader once available and preserve any disagreement between the described behavior and the adapted native score. The rest of the comparison continues unchanged.

## Returned grades for the three inspected cases

Read the saved GPT-4.1 evaluator receipts with the runner's unchanged parser. These are individual adapted native grades, separate from the final panel comparison.

| Task | Direct Match / OPB / UPB | Parent Match / OPB / UPB | Scope Match / OPB / UPB | Interpretation |
|---|---|---|---|---|
| Father's birthday | 0/5 · 4 · 0 | 0/5 · 0 · 3 | 0/5 · 2 · 0 | With all five author labels A, the parent's reported positive UPB has no feasible transition under the archived rubric. Preserve its 0/5 and the incompatibility flag. The answers give different reasons for a group decision despite tied Match. |
| Student dietary advice | 4/6 · 2 · 0 | 4/6 · 0 · 2 | 4/6 · 0 · 2 | Direct's ingredient-level advice improves one aspect of execution, while the adapted score records higher overuse and the same Match. The aggregate alone leaves the exact C verdict unresolved. |
| Hainan family trip | 6/7 · 1 · 0 | 0/7 · 0 · 5 | 0/7 · 0 · 4 | Direct has a Match–bias conflict. Parent and Scope identify the wrong preference ordinal in the rationale, and Parent also has a Match–bias conflict. The saved numerical gap cannot establish a six-position behavioral improvement. |

The cases support keeping source exposure, answer behavior and judge results separate when comparing the three paths. All nine raw grades above are retained.
