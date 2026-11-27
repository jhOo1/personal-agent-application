# Close disagreement-based OFF-branch re-entry

The frozen comparison completed all 24 exposed tasks, with 48 valid arm scores on 122 positions. Exact wire sharing reduced the deployment to 33 Actor and 33 Judge calls, all successful, 118,229 reported tokens and zero unknown usage. No new estimators or fixed endpoint regenerations. All scores below use the project detailed GPT-4.1 rubric and a single response per unique new Actor request.

| Same 24 tasks | Match | Whole exact | OPB | UPB | FM |
|---|---:|---:|---:|---:|---:|
| Original IPE-C OFF (task only) |63|5|12|50|8|
| Archived full RP |59|3|30|29|5|
| Equal-size RP |57|2|42|22|8|
| Disagreement only |53|2|38|28|7|

On the 11 tasks with different subset requests, disagreement scores 27/62 versus 31/62, OPB 18 versus 22, UPB 12 versus 6. Across all 16 source groups it wins one, loses one and ties 14 on Match. Seven all-A cases fall from 17/29 with no history to 4/29 with either restricted method. On the 14 B-without-C cases disagreement scores 41/80 versus equal-size RP 45/80. All three C-containing tasks together score 8/13 under both subset arms.

The two preregistered action opportunities produced different consequences. For bedtime audio the disagreement answer supplies three personally relevant playable tracks; equal-size RP offers a generic instrumental category. Match is 3/6 vs 2/6. For the friend's birthday the disagreement answer reproduces the host's lemon-basil pasta and purple sweet potato cheesecake, placing both in the proposed party menu. A personal cooking capability influenced a shared menu. Equal-size RP offers other party food. Match is 1/8 vs 6/8. A difference in a particular dish cannot by itself explain five graded positions. The pair shows why adding an author-B item need not improve overall scoring.

Keep the original OFF rule. Lower OPB than RP at equal count accompanies higher UPB and lower Match, and the prespecified two-root improvement rule fails. These are development estimates without independent confirmation. Behavioral examples are execution-side readings. The candidate has no new BenchPreS or PersistBench evidence. Private requests, answers, ledger and original grades remain in the independent run directory. Recompute FINAL.json with bash report.sh.
