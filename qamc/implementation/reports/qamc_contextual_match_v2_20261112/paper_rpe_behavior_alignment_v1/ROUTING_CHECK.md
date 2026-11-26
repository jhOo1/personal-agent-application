# Existing MLE predictions cannot safely rescue whole-history activation

The behavior audit warrants a direct check of the available predictors. For both of its IPE-C routing misses, the archived IPE ranks the relevant author C as B, while the corresponding MLE rank is C. The frozen 300-task archive now provides a 274-task exact three-arm intersection. We rechecked the original IPE-C branch per task and the fused policy's full-history Actor request hash. The experiment selects only archived drafts, with no regenerated Actor or Judge output.

| Added switch from IPE-C OFF to the saved full-history RP answer | Switches | Match delta | Exact joint delta | OPB / UPB / FM severity delta |
| --- | ---: | ---: | ---: | ---: |
| Any MLE top C | 24 | −4 | −2 | +18 / −21 / −3 |
| MLE top C for the same source where IPE top B | 24 | −4 | −2 | +18 / −21 / −3 |
| Same-source IPE B, MLE C, and fused C | 5 | −4 | −1 | +4 / −1 / −3 |

The first two rules select the same rows in this panel. They recover two Match positions on the three contains-C switches and seven on only-B tasks, while losing 13 on seven all-A switches. The agreement rule selects two contains-C tasks with no Match gain and costs four positions in a single all-A switch. The older 233-assignment grouping and the additional 67-assignment grouping are retained separately in the aggregate. Their valid subsets and exposure histories differ, so these are diagnostic results on previously exposed tasks. [Aggregate replay](ROUTING_CHECK.json)

Decision: keep the original IPE-C switch. The predictor disagreement is evidence of where to look for omitted constraints, but the archived full-history answer can let unrelated evidence affect the same task. Any next rescue should change the evidence presented or the actual action and compare against these zero-new-call controls. Current labels and scores were used only for outcome auditing after the switch rule. No original score was modified, and the sealed set was untouched.
