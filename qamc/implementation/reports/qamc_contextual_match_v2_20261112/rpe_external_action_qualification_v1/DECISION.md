# Do external answers supply a missing useful action?

The external-score frontier suggested two Des2Gen answers, each one Match position above the frozen incumbent. We recovered both full answers, matched the original task, and checked the author's preference positions against the original grader explanation. This is an unblinded development diagnostic by the research assistant, with zero human reviews and zero new calls. Original scores remain intact.

| Task | What the complete answers actually do | Implication |
|---|---|---|
| Jiangnan trip with retired parents, implicit/008, 4/7 to 5/7 | Both offer cultural visits, easy outdoor activities and a slower itinerary: the incumbent already suggests a Pingtan performance, gardens, a boat ride, and choosing one garden to avoid rushing. Des2Gen organizes towns as alternative stops; a changed itinerary is observable. Its judge calls position 5 support and position 7 ignore, the reverse of those author labels in AABBAAB. | A different route is available, but the +1 does not isolate a previously missing beneficial action. |
| Warm dinner for a girlfriend, implicit/099, 3/6 to 4/6 | Both offer steamed bass, tomato-tofu soup, broccoli with shrimp and rice, with mild seasoning. Des2Gen adds recipe detail, a cooking sequence and instructions for light soy sauce. Its judge says 3 and 6 should dominate. Both are ignore in CAACAA. The only dominant positions are 1 and 4. | More detailed cooking instructions have practical value. Neither the actual menu nor the labels establish a newly implemented soft preference. This task has no supporting B. |

## Wider development census

Use every row with known labels containing B and no C in the completed endpoint archive, including mixed A/B. For each comparator separately, require valid Match on both answers. Record all strict Match wins, then count those without a rise in recorded OPB, UPB or FM. This latter screen is intentionally selective and unsuitable for estimating the prevalence of useful actions. Other tradeoffs may be worth pursuing. A lack of pre-existing grader flags does not certify a clean rationale.

| Project comparator | Eligible | Paired | Missing | Strict Match wins | Wins with all three protections |
|---|---:|---:|---:|---:|---:|
| Full RP reconstruction | 54 | 49 | 5 | 9 | 2 |
| MemAdapter adaptation | 54 | 46 | 8 | 6 | 0 |
| Des2Gen adaptation | 54 | 47 | 7 | 8 | 2 |

Four protected method-task wins collapse to three task groups. Jiangnan appears above. On Hainan holiday lodging (explicit/125), both external answers score 6/7 against 5/7 and have recorded score-consistency flags. The incumbent already includes an old town, coffee culture and a cultural tourism area. Des2Gen adds specific local-cultural visits, alongside nightlife and surf-related material. The single position increase cannot identify which action earned it.

The strongest lead is Spanish-learning apps for travel (implicit/067). Full RP scores 4/4 against 2/4. The incumbent already offers audio shadowing with Pimsleur and pronunciation lookup with SpanishDict and lists Duolingo. Full RP adds Memrise's native-speaker imitation option and promotes Duolingo plus SpanishDict into the final shortlist. This is a change to the usable shortlist and practice method, not discovery of a previously absent pronunciation tool. The score does not isolate the benefit of introducing one app, reordering the others, or omitting irrelevant material. The corpus records the app claims in the answers; their current product capabilities were not independently evaluated.

**Decision.** The two original Des2Gen examples do not qualify a common new operation. The Spanish case remains an actionable development example, with only one source for that particular shortlist change. Keep it available to test future hypotheses. Close this cross-source qualification attempt and do not allocate another online generation trial to the same examples. Future external comparisons can pursue a different unresolved gap such as a full method's selection and generation at matched inference permissions. These results do not establish the absence of useful B preferences.

[Aggregate and answer fingerprints](SUMMARY.json) · [Reproduction](audit.py) · [Original 92-root analysis](../external_pool_frontier_v1/READOUT.md)
