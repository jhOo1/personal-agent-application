# RPEval IPE-C and external method adaptations

This zero-call audit joins the 300-case IPE-C endpoint archive to the formal multi-preference method archive by UID. Match uses the strict in-project parser and requires both valid scores and a denominator equal to the recorded author label count. Twenty to sixty-six allocated cases per comparison lack a common valid score. Panels and inference costs differ across rows. These are exposed development results using a GPT-4.1 rubric adaptation. RP-Reasoner and Des2Gen are project reconstructions, MemAdapter is the project's full-method adaptation, and Strong Gate is an in-house reference.

| Reference | Common tasks | IPE-C Match | Reference Match | IPE-C / reference UPB severity |
|---|---:|---:|---:|---:|
| RP-Reasoner reconstruction | 280 | 970/1504 | 841/1504 | 258 / 237 |
| MemAdapter adaptation | 263 | 903/1406 | 614/1406 | 248 / 240 |
| Des2Gen reconstruction | 274 | 949/1472 | 704/1472 | 254 / 149 |
| Strong Gate | 234 | 827/1253 | 561/1253 | 199 / 149 |

The IPE-C comparison with RP is a policy comparison against one of its own endpoints. The observed +129 Match decomposes into +133 on all-A, −2 on only-B and −2 on contains-C. On 46 common only-B items, IPE-C and MemAdapter have 140 and 139 Match out of 268, but UPB is 96 and 55. On 47 common only-B items, IPE-C and Des2Gen have 148 and 140 Match out of 273, but UPB is 96 and 44. These are severity sums from automatic grading, so the lower missing-use scores alone cannot establish better realization. Check actual decisions and protect all-A gains before replacing the deployed route. Existing scores and sealed data remain unchanged.
