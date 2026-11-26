# Generation-side cost of the first BenchPreS repeat wave

On 21 same-task, same-draw pairs with successful generation, both methods use Qwen 3.8 Flash, temperature 1, and the 4,096-token output cap. The frozen Gate and Selectivity messages use materially different input sizes.

| Paired Actors only | Strong Gate | Selectivity |
| --- | ---: | ---: |
| Physical requests | 21 | 21 |
| Reported prompt tokens | 160,161 | 48,027 |
| Reported completion tokens | 34,006 | 41,699 |
| Reported total tokens | 194,167 | 89,726 |
| Median prompt tokens per request | 7,579 | 2,239 |
| Median recorded response time, seconds | 18.91 | 21.91 |

Gate uses 3.33 times the prompt tokens and 2.16 times the total tokens on this observed paired slice. This measures the conditional frozen Actor comparison. Gate's upstream selector ran in the historical pipeline, so its selection cost is not included. Grading costs are reported separately by method and make no contribution to the Actor token ratios. Recorded response time includes service behavior and is descriptive. This latency result does not establish that a larger input causes faster generation.

Each physical receipt was checked against its manifest unit, request hash, and the current execution fingerprint. Wave totals match the original settlement, with 45 Actor and 270 Judge requests, 426,974 reported tokens, no unknown usage, and zero retries. The cost-matched dimension is the output ceiling and number of draws. The outcome comparison does not control input compute or token cost. Preserve these distinctions when interpreting the full repeat allocation. [Aggregate replay](WAVE0_COSTS.json) · [Original wave scoring](WAVE0_READOUT.md)
