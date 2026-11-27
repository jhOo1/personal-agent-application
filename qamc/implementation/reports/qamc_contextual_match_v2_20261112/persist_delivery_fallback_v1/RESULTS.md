# Existing-answer fallback on infrastructure failure

One common policy across tracks: take the selected-evidence Actor response if delivered, otherwise serve the archived parallel RUBRIC response when available. Never switch on the judge, numeric rating, track, UID, or perceived answer quality. This offline policy assumes both responses are available at serving time. An unknown original delivery remains recorded.

|Track|Judge|Roots|Selected pass/fail/unknown|Fallback pass/fail/unknown|Rubric pass/fail/unknown|Rubric-first backup pass/fail/unknown|Selected-first vs rubric-first wins/losses/ties/unknown|
|---|---|---:|---|---|---|---|---|
|beneficial_memory_usage|old|18|12/0/6|18/0/0|18/0/0|18/0/0|0/0/18/0|
|cross_domain|old|19|15/1/3|16/1/2|12/1/6|16/1/2|0/0/17/2|
|sycophancy|old|12|11/1/0|11/1/0|4/8/0|4/8/0|7/0/5/0|
|beneficial_memory_usage|qwen|18|11/1/6|15/3/0|14/4/0|14/4/0|2/1/15/0|
|cross_domain|qwen|19|15/0/4|16/0/3|13/0/6|17/0/2|0/0/16/3|
|sycophancy|qwen|12|12/0/0|12/0/0|8/4/0|8/4/0|4/0/8/0|

Fallback activations (track, failed stage, archived backup delivered, deployments):

- beneficial_memory_usage, actor, True: 1
- beneficial_memory_usage, route, True: 5
- cross_domain, actor, False: 2
- cross_domain, actor, True: 1

No new calls. This simulation uses a second previously generated response, whose inference cost remains part of the system. It does not measure sequential retry success, latency, intrinsic beneficial-use performance of SELECTED on missing responses, or official Kimi grades.
