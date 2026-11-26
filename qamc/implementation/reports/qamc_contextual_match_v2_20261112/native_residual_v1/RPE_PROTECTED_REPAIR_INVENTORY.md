# RPEval saved-answer repair inventory

This retrospective audit searches for positive behaviors to explain and test. It does not select a new answer online or change any archived grade. All records come from the existing exposed development panel. The reference is the exact IPE-C endpoint. The six comparison methods are the contemporary formal-coverage archive's RP reconstruction, Des2Gen reconstruction, MemAdapter adaptation, and three internal GEPA pipelines. Their histories, prompts and inference costs can differ. All use the recorded project rating protocol.

## Reproducible screen

Join by exact UID. Restrict to inputs with an author B or C and require both strict Match denominators to equal the label count. Mark a potential repair if Match increases and none of OPB, UPB or FM increases. The last screen also requires a distinct answer hash, no recorded diagnostic flag on IPE-C, and no recorded invalid native field on the alternative. The latter two checks have different coverage. A row that passes can still contain a Judge error. Author labels and scores are used only here, after generation.

| Slice | Allocated method-task cells | Paired Match | Increased Match | Also severity protected | Final screen | Distinct tasks / groups |
|---|---:|---:|---:|---:|---:|---:|
| B without C | 324 | 255 | 40 | 5 | 5 | 3 / 3 |
| Contains C | 732 | 630 | 47 | 32 | 30 | 17 / 12 |
| Total | 1,056 | 885 | 87 | 37 | 35 | 20 / 15 |

Run `python3 audit_rpe_protected_repairs.py` from this directory after restoring `../ipe_c_two_endpoint_completion_v1/RESULTS.json` and `../rpeval_formal_multi_coverage_v1/RESULT_ROWS.json`. Baseline answers for the inspected cases were joined by matching their archived IPE-C answer digests to `../ipe_c_full_exposed_panel_v1/RESULTS.json`. This is a candidate inventory. Scores across methods for the same source group are dependent and cannot multiply the number of independent repairs.

## Behavior inspection

| Exposed task | Candidate | Match change | What changed relative to IPE-C |
|---|---|---:|---|
| explicit/073, Xi'an family outing | Des2Gen | +1 | IPE-C prioritizes open, low-queue options. Des2Gen adds an explicit if-crowded switch to a named alternative park with the same trip objective. This is a concrete addition tied to the explicit no-queue preference. A prior matched B-to-C prompt experiment on this same root also produced a substitution, so the two results do not provide two independent roots. |
| implicit/067, Spanish apps for travel | RP | +2 | The no-history draft already has Duolingo and travel resources. The RP draft adds game mechanics such as points and streaks as a reason to choose it and introduces SpanishDict for reference. History includes enjoyment of game-like quizzes; the actual app remains the same. This is a grounded added way to choose or use an existing option, without proving that both added Match positions arise from it. |
| implicit/149, screen-free children's bedtime audio | Des2Gen | +5 | The draft expands generic story categories into named stories and adds playback controls. Both drafts already honor the core ad-avoidance preference with ad-free or offline audio. Content specificity improves visibly, but this is not recovery of a previously missing no-ad constraint. |
| implicit/148, Qingdao family itinerary | GEPA selected bounds | +2 | The new draft makes shopping optional with a regrouping point and retains the seaside itinerary. The old draft already lacks a shopping stop. The remembered objection concerned a company outing. Without resolving its scope here, presenting a voluntary detour does not demonstrate correction of an IPE-C shopping requirement. |
| implicit/004, healthy takeout without seafood | MemAdapter | +1 | The original IPE-C answer already says to exclude all seafood and relevant seasonings in its ordering note. Its summary speaks of reducing hidden seafood ingredients. MemAdapter is more consistent and retains concrete orderable options. The much more severe positive fish and shrimp recommendations previously seen in the RP endpoint should not be attributed to this IPE-C reference. |
| explicit/097, cold-weather dinner | Des2Gen | +1 | The original already excludes chili and pepper. Des2Gen makes the prohibition global across the recipe and expands the list of seasonings to avoid. This does not establish a previously violated pepper constraint or prove that every added restriction was needed. |
| implicit/146, weekend child outing | Des2Gen | +2 | The baseline already avoids craft activities, provides interactive alternatives and includes a venue switch if crowded. The new itinerary adds specific games and observational activities but introduces remembered style as a route theme. OPB remains 4 in both; this is not a second demonstration that the contingency was missing. |

The first two cases provide observable gains of different kinds. The first adds a replacement action if a constraint is violated; the second improves the rationale for an already available option. No repeated repair operator across independent sources has been established by these checks. The remaining candidate pairs need text-level verification before choosing a test. In particular, search for a second missing constraint-preserving substitution outside the Xi'an group, require an actual change in a requested decision, and use already-compliant cases as controls. A broader sufficiency hypothesis still needs to distinguish the effect of memory from better generic task completion. No model requests or sealed data access occurred.
