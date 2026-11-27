# How much does a source-disjoint task prior explain?

The original IPE-C remains the incumbent. These offline controls reuse two scored endpoints per exposed task. Each training pool has 201–215 other records. Excluding the held-out conservative source group and exact shared memory text eliminates all identical task-request neighbors; each of 216 predictions uses a different request as its closest lexical neighbor. Holding out the row alone would leave exact request matches on 214/216 tasks. The two splits answer different questions.

|Policy|History ON / 216|Match / 1142|OPB|UPB|FM|All A|B without C|Contains C|Unflagged|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|empty|0|696|65|396|206|369/432|97/181|230/529|547/834|
|full|216|645|314|156|45|222/432|101/181|322/529|490/834|
|IPE-C|100|765|206|168|42|343/432|100/181|322/529|586/834|
|global|0|696|65|396|206|369/432|97/181|230/529|547/834|
|task|91|666|201|285|138|295/432|103/181|268/529|517/834|
|conditional|72|729|166|254|106|342/432|99/181|288/529|567/834|
|row_only|93|718|159|282|118|334/432|101/181|283/529|570/834|

Compared with the task prior, conditioning the training pool on the IPE-C activation bit improves Match on 29 tasks, loses on seven, ties on 180. OPB, UPB and FM severity sums also fall. Keeping the original IPE-C decision directly wins 21 tasks against this conditional prior, loses one and ties 194. Absence of an exact-match neighbor in the strict split means that this result compares transfer across different task requests. It cannot establish discrimination between different histories under the same exact request. Structural gates and conditional priors use the archived history-dependent estimator, which has a different inference cost from a lexical lookup. The row-only comparison can reuse related tasks and is reported separately.

No additional model calls or scoring. This source-held-out development replay supports retaining IPE-C over this specific task prior. It does not establish superiority over learned semantic task priors or independent benchmark SOTA.
