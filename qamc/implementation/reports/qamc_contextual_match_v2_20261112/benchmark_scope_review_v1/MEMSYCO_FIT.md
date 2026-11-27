# What a third primary benchmark would measure

Original QAMC B6 development only. The 16 previously exposed tasks cover all five MemSyco-Bench tracks. The byte digests match the original corpus manifest on each track. The local scorer imports upstream rubric builders and parsers; the original project's automatic Judge was uncalibrated. The three columns are historical ablations of QAMC, not their leaderboard counterparts. In particular E_full is the B6 full evidence-construction configuration, not an always-full-history generator.

| Track | A_task | E_full | F_adaptive |
|---|---:|---:|---:|
| Scope control | 3/3 | 3/3 | 2/3 |
| Memory versus current evidence | 1/3 | 2/3 | 2/3 |
| Objective fact judgment | 2/4 | 2/4 | 2/4 |
| Personalized memory use | 1/3 | 2/3 | 3/3 |
| Valid memory selection | 2/3 | 2/3 | 3/3 |

The two positive-use tracks therefore provide an empirical reason to consider this benchmark beyond testing sycophancy again. F gains one correct joint score relative to E on each, loses one on scope, and has the same aggregate scores on both other tracks. Across 16 paired cases there are three wins, two losses and eleven ties. Track totals cannot identify the individual winning and losing cases. This development slice is too small and already exposed to establish a ranking.

For the specific claim that the agent handles superseded preferences, MemSyco's valid-selection track measures both using the latest preference and avoiding outdated contamination. For a claim about opposing preferences in different contexts, the original QAMC CUPID preflight identifies a more direct contrastive test. Neither substitutes for BenchPreS writing quality. Retain the existing three results and avoid a new full benchmark run until the intended mechanism and fair comparison are fixed.

The script takes the original QAMC root. It reads the existing development aggregate reports and computes file hashes. It submits no requests and consumes no hidden examples for inference. See the [authors' code](https://github.com/XMUDeepLIT/MemSyco-Bench/tree/3c3aa013ac5bee2f0e252fe8748644edc7f9af0a).
