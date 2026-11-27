# Does the RPEval result depend on position Match?

The archived detailed multi-preference prompt (prompts_715.py, lines 867–885, local author source) requests a whole-answer Judge score from 0 to 5, higher meaning more severe overall error. Keep that field and position Match from the same GPT-4.1 grading response. The Judge score is not an independent assessor or a sum of the five error categories. The author short prompt uses a different contract.

| Panel | Common / assigned tasks | IPE-C | Empty | Full RP |
|---|---:|---:|---:|---:|
| Exposed archived, severity sum |274/300|451|537|532|
| Fresh deployment 1, severity sum |18/18|46|49|45|
| Fresh deployment 2, severity sum |17/18|38|48|41|

On the archive the mean severity is 1.65, 1.96 and 1.94 respectively. Against full RP, 38 tasks improved on both Match and severity, 12 worsened on both, and two moved in opposite directions, one each way. The other 222 tied on at least one metric. A shared selected answer can tie by construction. The original archive advantage is visible on both metrics. On the same 18 development groups redeployed twice, both metrics favor IPE-C over empty history in each comparison, while the full-RP ranking reverses between deployments. One invalid Match in deployment 2 is excluded for all arms. These paired complete-case results do not establish independent replication or a published-protocol ranking.
