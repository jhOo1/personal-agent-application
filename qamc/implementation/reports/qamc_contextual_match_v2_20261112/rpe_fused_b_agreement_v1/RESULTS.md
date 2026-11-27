# Can two agreeing estimates identify safe supporting preferences?

Frozen rank audit: 296 of 300 allocated tasks. Source SHA256: 0a6b01cc2c3f38ba081c9517c7e4ce95a1fb9440f8900508a288a0001a61b2d7. Counts are memory positions among fused B only. Order of the two votes: MLE, IPE. Both derive from the same model.

|Slice|Tasks|Estimator agreement|Author A|Author B|Author C|
|---|---:|---|---:|---:|---:|
|all|296|Both B|398|94|7|
|all|296|Other|162|44|46|
|soft|54|Both B|51|49|0|
|soft|54|Other|30|22|0|
|IPE_off|158|Both B|205|46|0|
|IPE_off|158|Other|94|20|1|
|all_A|120|Both B|168|0|0|
|all_A|120|Other|80|0|0|
|has_C|122|Both B|179|45|7|
|has_C|122|Other|52|22|46|
|IPE_on|138|Both B|193|48|7|
|IPE_on|138|Other|68|24|45|

## Individual vote pairs over the full audit

|Pair|Author A|Author B|Author C|
|---|---:|---:|---:|
|AB|82|0|0|
|BA|61|0|0|
|BB|398|94|7|
|BC|9|5|42|
|CB|10|39|4|

No answer generated or rescored. Demoting an author-C item already labeled B would further reduce its allowed strength. Counts cannot establish the effect on final answers.

## Existing final-answer intervention

Among 118 previously assigned tasks, narrowing only fused B with exactly one A vote changes 34. The previous context-first experiment produces precisely this policy change on 13 of those tasks. There are 12 common valid score pairs from 10 conservative groups. All remaining affected tasks are outside this exact-pair comparison.

ORIGINAL_FUSION: Match 17/67, OPB 27, UPB 12, FM 5.

CONTEXT_FIRST_FUSION: Match 22/67, OPB 23, UPB 7, FM 5.

Paired Match outcomes: {'tie': 10, 'win': 2}

This is a post-hoc exact-policy intersection of archived contemporaneous Actor draws. Reusing the archived score on an unchanged request does not imply scores are deterministic. No causal attribution for individual behaviors or independent confirmation.

## Check against frozen IPE-C and the previous RP draw

IPE_C, 12 tasks: candidate 22, contemporary original 17, archived comparator 44 of 67.
RPR_PAPER_FULL, 12 tasks: candidate 22, contemporary original 17, archived comparator 23 of 67.

The observed wins occurred on implicit/000, implicit/075 .

## Apply the change only when IPE-C actually opens history

Exact-pair subset only: 6 of 12 open. Archived IPE-C 44, same-route contemporary original 43, same-route narrow veto 44 of 67. Closed branches reuse their exact old answer.
