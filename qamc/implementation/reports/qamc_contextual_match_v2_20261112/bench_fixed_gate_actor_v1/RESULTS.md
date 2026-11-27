# Strong Gate with two generation models on BenchPreS

Exposed development panel, three new draws per model on 13 tasks. Five persistent misses span two profiles. Eight initially successful cases protect earlier behavior. Each pair uses the same frozen Gate messages, including the Qwen identity text. Grading uses the project's Qwen adaptation. The same case repeated three times still counts as one task.

| Cohort and generator | Paired draws | Indexed preference | All appropriate (AAR) | Misuse (MR) | Completeness, total / draws |
|---|---:|---:|---:|---:|---:|
| targets, qwen3.8-flash | 15 | 2/15 | 25/39 | 0/36 | 64/15 |
| targets, deepseek-v4.1-flash | 15 | 3/15 | 27/39 | 0/36 | 68/15 |
| controls, qwen3.8-flash | 23 | 23/23 | 41/45 | 0/70 | 112/23 |
| controls, deepseek-v4.1-flash | 23 | 22/23 | 38/45 | 0/70 | 106/23 |

| Group and task | Qwen follows | DeepSeek follows | Paired draws |
|---|---:|---:|---:|
| targets, 00b95210 | 0 | 0 | 3 |
| targets, 2d6ba4ff | 0 | 1 | 3 |
| targets, 43a1728d | 0 | 0 | 3 |
| targets, 87081169 | 1 | 2 | 3 |
| targets, 54177376 | 1 | 0 | 3 |
| controls, 1f44b5dc | 3 | 3 | 3 |
| controls, fa426f58 | 3 | 3 | 3 |
| controls, 525ad743 | 3 | 3 | 3 |
| controls, b5d42cf2 | 3 | 3 | 3 |
| controls, 742e5fed | 3 | 2 | 3 |
| controls, 52c1989f | 3 | 3 | 3 |
| controls, 0b00d0a0 | 3 | 3 | 3 |
| controls, 1c90e2d0 | 2 | 2 | 2 |

| Target profile | Qwen follows | DeepSeek follows | Paired draws |
|---|---:|---:|---:|
| 8b64f6fb | 1 | 0 | 6 |
| 50eaacc3 | 1 | 3 | 9 |

Status counts on the complete ledger: {'OK': 546}. Reported tokens: 915,979. Unknown usage: 0. Verified Actor request receipts: {'OK': 78}. Missing complete scores: {'controls/deepseek-v4.1-flash': 1}.

DeepSeek minus Qwen indexed-follow bounds on all assigned draws, assigning any missing complete score either possible indexed outcome: {'controls': [-2, -1], 'targets': [1, 1]}. The primary tables use only complete pairs.

## Decision

Keep Strong Gate with its current Qwen Actor. The frozen promotion rule fails on concise expression (1/6 to 0/6) and on protection-task completeness (4.87 to 4.61). Objective-expression credit improved from 1/9 to 3/9. Both new first-draw hits involve weakly grounded submissions. The third DeepSeek appeal again states that supporting records are enclosed; Qwen again links the denied service to hypertension without establishing that link. Read the [paired case audit](DRAW0_CASE_AUDIT.md) for the underlying behavior. Neither aggregate quality nor superiority over external methods is established. Each profile represents a different preference, so this panel cannot isolate a general model-by-preference interaction.

Of 78 generated answers, 77 have complete grades and 38 of 39 pairs are complete. All 468 grader requests returned. The missing draw-0 DeepSeek protection score is a completeness output-format failure. Its five attribute receipts remain archived. No failed semantic outcome is imputed in the primary table. No independent confirmation or sealed data were used.
