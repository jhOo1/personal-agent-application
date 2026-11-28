# Removing bold and nickname attributes from the archived joint endpoint

Each cell counts passes on the same 37 exposed tasks. Completeness must still be 5/5.

|Omitted requirements|GEPA_SELECTED_BOUNDS|DES2GEN_FULL|MEMADAPTER_FULL|PAPER_SELECTIVITY|RPR_PAPER_FULL|
|---|---:|---:|---:|---:|---:|
|none|24|15|10|15|16|
|bold|24|20|17|17|21|
|nickname|24|15|10|20|17|
|bold, nickname|24|20|17|23|24|

|Method|Other appropriate realized|Other inappropriate realized|Full completeness|Joint on tasks with other appropriate preferences|
|---|---:|---:|---:|---:|
|GEPA_SELECTED_BOUNDS|32/42|1/85|33/37|16/28|
|DES2GEN_FULL|35/42|1/85|26/37|13/28|
|MEMADAPTER_FULL|32/42|0/85|24/37|10/28|
|PAPER_SELECTIVITY|33/42|3/85|32/37|15/28|
|RPR_PAPER_FULL|35/42|0/85|28/37|15/28|

## Matched outcomes after excluding bold and nickname

Cells partition the 37 tasks. Loss reasons can overlap.

|Comparator|Both pass|Gate only|Comparator only|Neither|Reasons comparator failed on Gate-only tasks|Reasons Gate failed on comparator-only tasks|
|---|---:|---:|---:|---:|---|---|
|DES2GEN_FULL|14|10|6|7|completeness 9, misuse 1|completeness 2, misuse 1, omission 3|
|MEMADAPTER_FULL|13|11|4|9|completeness 9, omission 2|completeness 1, misuse 1, omission 2|
|PAPER_SELECTIVITY|19|5|4|9|completeness 4, misuse 1, omission 1|completeness 1, misuse 1, omission 2|
|RPR_PAPER_FULL|19|5|5|8|completeness 5|completeness 2, misuse 1, omission 2|
