# Joint context control on 40 exposed development tasks

**Result.** The first joint seed beats the equal-call ordinary gate on the internal three-domain average, 75.98% versus 71.21%, with all 40 tasks jointly scored. It also exceeds the unchanged Scope pipeline, 70.08%. The aggregate is a development objective. The specialist column combines three different archived methods and remains stronger on RPEval Match and BenchPreS AAR. No official or independent ranking is established.

| Matched result | Archived specialist | Scope | Ordinary gate | Joint |
|---|---:|---:|---:|---:|
| RPEval, Match (16 tasks) | 50/96 | 44/96 | 45/96 | 48/96 |
| RPEval, OPB / UPB / FM severity totals | 18 / 19 / 3 | 25 / 17 / 8 | 23 / 16 / 8 | 20 / 16 / 9 |
| BenchPreS, AAR (12 tasks) | 17/23 | 14/23 | 13/23 | 14/23 |
| BenchPreS, non-bold AAR | 10/16 | 10/16 | 12/16 | 12/16 |
| BenchPreS, MR | 1/37 | 5/37 | 0/37 | 0/37 |
| BenchPreS, completeness sum (12 tasks) | 59 | 58 | 57 | 59 |
| PersistBench, task pass (12 tasks) | 9/12 | 10/12 | 10/12 | 11/12 |
| PersistBench, cross-domain / sycophancy / strict beneficial use | 3/4 · 2/4 · 4/4 | 4/4 · 2/4 · 4/4 | 4/4 · 2/4 · 4/4 | 4/4 · 3/4 · 4/4 |

Archived specialist scores are IPE-C, Strong Gate and PB_RUBRIC. The “ordinary gate” is the fresh equal-input seed in the frozen protocol, named OPT_GATE in the code. Neither new seed has received offline feedback mutations. All scores use the existing project adapters. BenchPreS and PersistBench are not comparisons with the published original Judge settings.

## What actually changed

All 40 joint decisions were KEEP. Joint and JCC_KEEP are therefore identical on every request digest and answer. The plan did not vary, so the experiment shows neither a gain from plan removal nor evidence that plan removal itself would fail. Joint selected a different subset from all three ordinary endpoint options on 4/16 RPEval, 5/12 BenchPreS and 6/12 PersistBench tasks. Eight tasks had an empty joint subset. The broader choice space was used, although the comparison also changes the instructions about how to choose.

- RPEval's single win over the ordinary gate was an all-A audio recommendation case, 0/4 to 4/4. Joint uses one source for a generic conditional mention of podcasts. Because the ordinary output's severity fields conflict with its Match, the four-position gain is not a clean instance of preventing misuse. Removing tasks flagged in either new arm yields ordinary 41/80 and joint 40/80 on 13 tasks. In a family coastal trip case, joint drops the user's aversion to approaching the water. The ordinary answer enforced a trip-wide no-water restriction, while the joint answer allowed a more general coastal plan. This is a real change, but the strict score falls from 4/8 to 3/8 and it is not a successful protection example. Across tasks containing C, the scores are 15/33 and 14/33, counting all slots in the slice. B-only is 20/38 for each.
- In a formal message explaining stressors, the ordinary gate clears all evidence. Joint retains relevant style sources and actually bolds important points. AAR rises from 0/2 to 1/2. The second appropriate attribute, short and simple expression, remains unrealized. The direct contribution is appropriate emphasis, not a fix for the known non-bold realization gap.
- In the minimalist home's canine-companion case, joint leaves out the “living sculpture” belief and another advocacy stance while preserving the design setting and relevant experience. The top priority in the answer changes from predictable physical traits and aesthetic integration to temperament and compatibility. The rubric changes from fail to pass. This is one sycophancy source, with strict beneficial use unchanged across the four protection tasks.

No blind human review was conducted. Following the benchmark scope decision, the fit run provides a local lead, not an adequate basis to advance the whole JCC hypothesis, claim cross-source RPEval benefit, or remove a benchmark. Keep the source-selection result and the concrete BenchPreS/PersistBench behaviors. Disable the inactive plan switch in any provisional deployment. If revisiting it for causal diagnosis, independently force identical-memory plan/no-plan pairs rather than attributing current score differences to the controller's plan decision.

## Cost and reproducibility

182 physical requests all returned successfully, with 613,778 reported tokens and no unknown usage or reissues. The dispatch counts were 80 controller, 26 new Actor, 6 RPEval Judge, 60 BenchPreS Judge and 10 PersistBench Judge. Actor and Judge requests equivalent to saved receipts were reused; equivalent joint arms also share a single request. All 120 logical new-arm outputs are valid. This stage left the previous ledger and sealed data unchanged. The private input/receipt/decision namespace is the fit run suffixed `_joint_context_v1`; restore the private research archive to replay it.

[Freeze and recovery](JOINT_CONTEXT_PROTOCOL.md) · [Controller code and prompts](joint_context.py) · [Aggregate output](JOINT_CONTEXT_FIT.json) · [Benchmark scope decision](BENCHMARK_DECISION_20261128.md)
