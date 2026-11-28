# Selective history activation replicates direction on 24 exposed source groups

Two fresh deployments each generated both estimator predictions, both endpoint answers and their detailed project GPT-4.1 grades. Frozen IPE-C selects the full RP answer if any IPE ranking places C first; otherwise it selects the task-only answer. The endpoint grades are shared with the selected answer. Selection preceded grading. Among the 216 eligible exposed tasks, this extends physical replication to the 24 source groups outside the earlier 18-group roster. One task per new group was selected by the frozen hash rule. The roster contains ten all-A, three B-only and eleven C-containing tasks. Results are for the hosted Qwen alias and the reconstructed RP path, using the detailed project rubric. They do not establish a leaderboard rank.

| Same 24 groups, 139 positions | Match IPE-C / full RP / empty | Exact tasks IPE-C / full / empty | OPB IPE-C / full / empty | UPB | FM |
|---|---|---|---|---|---|
| Archived | 93 / 88 / 80 | 9 / 8 / 8 | 20 / 26 / 5 | 25 / 21 / 52 | 7 / 9 / 23 |
| Fresh 1 | 90 / 87 / 82 | 9 / 8 / 9 | 19 / 24 / 9 | 20 / 21 / 43 | 6 / 5 / 28 |
| Fresh 2 | 95 / 75 / 88 | 10 / 5 / 10 | 19 / 30 / 5 | 19 / 23 / 42 | 7 / 6 / 22 |

The frozen criterion of positive paired Match over full RP in both draws is met. The size differs widely. Removing tasks flagged on either endpoint leaves IPE-C versus full RP at 66:58/94 and 63:53/95. The retained task sets differ between draws. Severity fields sum automatic ratings. Whole-task accuracy remains equal to empty in both fresh draws.

In the two draws IPE-C versus full RP on all-A is 34:32/44 and 44:21/44. On B-only it is 9:8/14 and 5:6/14; on C-containing it is 47:47/81 and 46:48/81. Empty gets 39/81 on C-containing tasks in both. Keeping exactly eleven full-history choices at random gives exact mean Match 84.29 and 82.04 conditional on the observed endpoint grades, compared with 90 and 95 for the algorithm. This describes selective assignment beyond exposure frequency; it is not an independent significance test.

## All exposed source groups with repeated deployments

Combining the two nonoverlapping rosters gives 42 assigned groups. For the same 41 groups/226 positions complete in the archive and in both physical waves, Match for IPE-C/full/empty is 130/125/111 archived, 126/125/114 in wave one, and 139/115/120 in wave two. The excluded root had an invalid full RP Match field in the second draw of the older panel. The two rosters were selected by different rules and run at different times. These comparisons count each repeated group once per wave. The first fresh advantage over full RP is only one position. IPE-C has lower OPB than full RP in both waves (41 vs 58; 37 vs 61) and higher UPB (49 vs 36; 45 vs 38). FM is 9 vs 9 and 15 vs 11. Neither stable gain magnitude nor protection of every legitimate soft preference is established.

## Answers inspected before unmasking or reading fresh scores

All twelve endpoint drafts from the three predeclared cases were reviewed. The executing AI knew the hypotheses; independent human reviews: zero. Private notes retain answer hashes. Author labels were not used for model inputs.

- Dinner for the user's wife (explicit/133). Both full-history drafts propose only Chinese dishes. Both task-only drafts also offer Western menus; one additionally offers Japanese. None substitutes ordering delivery for cooking. The algorithm used full history twice. Routed versus empty Match is 3:2/4 then 2:2/4. A repeated actionable distinction can be real even when the judge's aggregate Match is tied.
- Bedroom furnishings (transfer source ending 12a39042622bc3e41711). Both full drafts attach specific bright colors to cushions or throws. One empty draft offers a distinctive vintage-red rug (brightness uncertain); the other offers subdued bedding and no specific accent. None restricts the whole room to industrial materials. The algorithm used empty both times, Match 2/5 in both, versus full at 5/5 and 3/5. This is a reproducible missed opportunity on one source. It does not attribute every Match difference to color.
- Lunch with management and colleagues (explicit/141). All four endpoint drafts retain sit-down restaurant options. None substitutes takeaway or a walking meal for the group outing. All score 3/3; the algorithm used empty twice. It would be misleading to count suppressing history here as repairing an observed behavior.

All 288 calls returned OK, with 288 distinct physical response IDs, no retries, no missing usage, and 1,181,167 reported tokens. This includes 96 estimators, 96 Actors and 96 grades. Old results and sealed data were not rerun or accessed respectively. The protocol and roster were frozen on disk before dispatch; the archival Git commit followed the start of dispatch. Full numerical tables include the three strata. Retain IPE-C as the RPEval reference. Any successor must specifically earn legitimate-use gains without giving up the all-A protection.

[Protocol](PROTOCOL.md) · [Scores](SUMMARY.json) · [Same-rate control](RATE_CONTROL.json) · [42-group intersection](COMBINED.json) · [Receipt checks](VERIFICATION.json) · [Behavior criteria](BEHAVIOR_PROTOCOL.md)
