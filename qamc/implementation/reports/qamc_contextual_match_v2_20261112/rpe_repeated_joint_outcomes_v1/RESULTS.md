# Joint outcomes across two fresh RPEval deployments

Better means at least one improvement with no deterioration over Match count, OPB, UPB and FM. Severity decreases are favorable. Mixed directions are tradeoffs. Missing fields remain unknown.

|Comparator|First draw|Second draw|Roots|
|---|---|---|---:|
|RP_FULL|better|better|2|
|RP_FULL|better|tie|1|
|RP_FULL|tie|tie|9|
|RP_FULL|tradeoff|better|1|
|RP_FULL|tradeoff|tie|1|
|RP_FULL|tradeoff|tradeoff|2|
|RP_FULL|worse|tradeoff|1|
|RP_FULL|worse|unknown|1|
|TASK_ONLY|tie|tie|10|
|TASK_ONLY|tradeoff|better|3|
|TASK_ONLY|tradeoff|tradeoff|3|
|TASK_ONLY|tradeoff|worse|1|
|TASK_ONLY|worse|tradeoff|1|

## Repeated non-tie directions

|Comparator|Exposed task|Stratum|Direction|First delta|Second delta|
|---|---|---|---|---|---|
|RP_FULL|rpeval/formal_multi_v1/implicit/005|B_only|tradeoff|(0, 2, -1, 0)|(0, 1, -1, 0)|
|RP_FULL|rpeval/formal_multi_v1/implicit/024|B_only|better|(0, 1, 0, 0)|(0, 1, 0, 0)|
|RP_FULL|rpeval/formal_multi_v1/implicit/047|all_A|tradeoff|(0, 4, -5, 1)|(0, 5, -5, -2)|
|RP_FULL|rpeval/formal_multi_v1/explicit/061|all_A|better|(0, 2, 0, 0)|(4, 3, 0, 0)|
|TASK_ONLY|rpeval/formal_multi_v1/implicit/030|contains_C|tradeoff|(2, -2, 3, 2)|(3, -3, 4, 1)|
|TASK_ONLY|rpeval/formal_multi_v1/explicit/006|contains_C|tradeoff|(2, -1, 3, 3)|(2, -1, 3, 3)|
|TASK_ONLY|rpeval/formal_multi_v1/explicit/052|contains_C|tradeoff|(2, -1, 4, 4)|(1, -1, 3, 3)|

## Symmetric scoring-flag sensitivity

Keep a root only when both routes have complete four-field comparisons and neither endpoint has an archived scoring flag in either deployment. Same population for both comparisons.

|Comparator|Eligible roots|Better twice|Worse twice|Mixed fields twice|
|---|---:|---:|---:|---:|
|RP_FULL|7|0|0|0|
|TASK_ONLY|7|0|0|2|
