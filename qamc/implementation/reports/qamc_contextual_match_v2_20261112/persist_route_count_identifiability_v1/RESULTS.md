# Do identical router/count decisions require different exposures?

## First deployment per source (49)

|Branch|Count|N|GPT group/narrow/tie/missing|Qwen group/narrow/tie/missing|
|---|---:|---:|---|---|
|grounding|0|22|0/0/22/0|0/0/22/0|
|grounding|1|3|1/0/2/0|0/0/3/0|
|grounding|2|7|0/0/6/1|1/0/5/1|
|grounding|4|3|0/0/3/0|0/0/3/0|
|grounding|5|1|0/0/1/0|0/0/1/0|
|style|10|1|0/0/1/0|0/0/0/1|
|style|2|2|0/0/2/0|1/0/1/0|
|style|3|2|0/0/2/0|1/0/1/0|
|style|4|2|0/0/2/0|0/0/2/0|
|style|5|5|0/0/5/0|0/0/5/0|
|style|6|1|0/0/1/0|0/0/1/0|

## All available deployments (111; repeated risk sources)

|Branch|Count|N|GPT group/narrow/tie/missing|Qwen group/narrow/tie/missing|
|---|---:|---:|---|---|
|grounding|0|62|0/0/59/3|0/0/59/3|
|grounding|1|16|1/1/13/1|0/1/13/2|
|grounding|2|16|0/1/13/2|1/1/12/2|
|grounding|4|3|0/0/3/0|0/0/3/0|
|grounding|5|1|0/0/1/0|0/0/1/0|
|style|10|1|0/0/1/0|0/0/0/1|
|style|2|2|0/0/2/0|1/0/1/0|
|style|3|2|0/0/2/0|1/0/1/0|
|style|4|2|0/0/2/0|0/0/2/0|
|style|5|5|0/0/5/0|0/0/5/0|
|style|6|1|0/0/1/0|0/0/1/0|

## Scored differences

|Source prefix|Draw|Branch|Count|GPT|Qwen|
|---|---:|---|---:|---|---|
|0029f020|3|grounding|2|narrow|narrow|
|36bd0c4f|1|grounding|1|group|tie|
|3776469a|1|style|2|tie|group|
|7b03625e|1|grounding|2|tie|group|
|a47fceb8|3|grounding|1|narrow|narrow|
|ef273934|1|style|3|tie|group|
