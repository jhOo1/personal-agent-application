# BenchPreS profile-level external comparison

Common complete panel: 37/48 tasks, 10 profiles. Existing adapted Qwen scores.

|Method|AAR|MR|Completeness sum / tasks|Joint passes / tasks|
|---|---:|---:|---:|---:|
|GEPA_SELECTED_BOUNDS|53/63|1/122|180/37|24/37|
|DES2GEN_FULL|46/63|1/122|169/37|15/37|
|MEMADAPTER_FULL|40/63|1/122|168/37|10/37|
|PAPER_SELECTIVITY|49/63|12/122|180/37|15/37|
|RPR_PAPER_FULL|45/63|3/122|172/37|16/37|

## Pairwise eligible

|Gate minus comparator|Tasks|Profiles|Positive|Zero|Negative|Profile-equal gap (pp)|Omit-one-profile range (pp)|
|---|---:|---:|---:|---:|---:|---:|---:|
|DES2GEN_FULL|40|10|7|2|1|+32.2|+24.6 to +39.4|
|MEMADAPTER_FULL|39|10|7|1|2|+33.5|+26.1 to +42.8|
|PAPER_SELECTIVITY|40|10|6|2|2|+21.0|+12.2 to +28.9|
|RPR_PAPER_FULL|41|10|7|2|1|+31.8|+24.3 to +37.6|

## Common five-method panel

|Gate minus comparator|Tasks|Profiles|Positive|Zero|Negative|Profile-equal gap (pp)|Omit-one-profile range (pp)|
|---|---:|---:|---:|---:|---:|---:|---:|
|DES2GEN_FULL|37|10|7|2|1|+24.0|+15.6 to +37.8|
|MEMADAPTER_FULL|37|10|7|1|2|+28.0|+20.0 to +42.2|
|PAPER_SELECTIVITY|37|10|6|2|2|+15.5|+6.1 to +28.3|
|RPR_PAPER_FULL|37|10|7|1|2|+19.8|+10.9 to +33.1|

## All 48 assigned tasks, worst-case missing outcomes

|Comparator|Net joint passes, min to max|Profile-equal gap, min to max (pp)|
|---|---:|---:|
|DES2GEN_FULL|+5 to +14|+10.5 to +30.0|
|MEMADAPTER_FULL|+11 to +20|+22.5 to +42.0|
|PAPER_SELECTIVITY|+6 to +14|+12.5 to +30.0|
|RPR_PAPER_FULL|+6 to +15|+12.0 to +31.0|
