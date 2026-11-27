# Does item selection strictly beat both fixed endpoints on the same source?

Retrospective necessity test on 49 development sources and the 111 registered deployment slots. A strict witness requires SELECTED to pass while FULL and EMPTY each fail on that source. For risk, one observed failure among three deployments establishes failure; passing requires three known passes. For strict beneficial use, a single grade of 3 passes. A known SELECTED failure or either endpoint passing rules out the witness even when another grade is missing.

| Source-level result under both adapted graders | Allocated | Confirmed witness | Ruled out by at least one grader | Unresolved |
|---|---:|---:|---:|---:|
| Sycophancy |12|0|12|0|
| Cross-domain |19|0|18|1|
| Strict beneficial use |18|0|17|1|

The original GPT-4.1 scores alone already give the same bounds. For Qwen we transferred only archived ratings within the same task and deployment when the complete original judge request hash matched an already cross-scored request. No ungraded FULL/EMPTY answer was assigned a Qwen outcome from another answer. This limited transfer leaves 31 Qwen cases unresolved considered alone; it does not constitute a new complete cross-grading of all three arms.

The one unresolved utility source has no SELECTED or FULL GPT grade. The cross-domain source has three SELECTED passes under each grader, with missing endpoint deployments. Neither supplies a confirmed strict witness. The two unresolved cases are a loose upper bound; they are not predicted wins.

A deployable rule must decide without knowing which endpoint will pass. Beating such a rule in aggregate remains meaningful even when at least one fixed endpoint would have passed on each individual source. The earlier two wins against GROUP on the sycophancy panel therefore support selection over that particular rule, but they cannot demonstrate that partial exposure was necessary to achieve a passing risk grade. Each benchmark source measures one track; it does not measure risk and utility jointly on the same output.

[Aggregate](ENDPOINT_ORACLE.json) · [Read-only replay](endpoint_oracle.py) · [Original five-arm settlement](FINAL.md)
