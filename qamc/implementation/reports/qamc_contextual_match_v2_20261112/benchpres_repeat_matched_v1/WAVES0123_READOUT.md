# BenchPreS three-draw comparison after four waves

Four of six frozen waves are settled. There are 32 allocated exposed tasks and 84 common scoring pairs on 29 tasks across ten profiles. Both methods use temperature 1.0, three allocated draws, and the fixed Qwen grading adaptation. Strong Gate retains its original selected evidence and prompt. The Selectivity arm uses the author's Figure 11 policy in the project runner. This is an exposed development comparison under the adaptation. [Protocol](PROTOCOL.md) · [Exact replay](WAVES0123_REPLAY.json)

| Common scoring pairs | Strong Gate | Author Selectivity |
| --- | ---: | ---: |
| MR | 1/274 | 34/274 |
| AAR | 124/146 | 107/146 |
| Bold AAR | 48/50 | 33/50 |
| Non-bold AAR | 76/96 | 74/96 |
| Completeness | 399/84 | 397/84 |

The 26 tasks with all draws valid yield MR 1/258 and 31/258, AAR 113/132 and 95/132, non-bold AAR 67/84 and 64/84, and completeness 371/78 and 369/78. On available pairs Gate has lower MR in nine profiles with one tie. Non-bold AAR favors one profile in each direction, with five ties. Of Selectivity's 34 misuse labels, 26 are literal inappropriate nicknames, compared with zero for Gate. The original non-bold preference is visible in both Actor wires on all 96 appropriate positions. [Profiles](WAVES0123_PROFILE_TRACE.json) · [Misuse trace](WAVES0123_MISUSE_TRACE.json) · [Delivery trace](WAVES0123_DELIVERY_TRACE.json)

## Robustness and missing outcomes

The diagnostic fieldwise replay keeps all valid original fields and still excludes missing aggregate grades from the primary table. The full allocation for these 32 tasks contains 315 inappropriate positions. There are 36 missing Gate fields and one missing Selectivity field. The unrestricted Gate-minus-Selectivity MR difference ranges from −36 to +1 positions. With the unknown Selectivity slot assigned no misuse, a tie would require 35 of 36 missing Gate slots to be misused; a reversal would require all 36. This tipping point describes the effect of missingness and gives no estimate for the missing cases. AAR retains a +10 to +24 position advantage under all assignments, driven by bold AAR (+13 to +19). Non-bold AAR ranges from −3 to +5 and completeness from −41 to +3 in their original sum units. [Fieldwise bounds](WAVES0123_FIELDWISE.json)

On the 25 tasks with both historical single draws and all six current draws scored, the historical MR was 1/82 and 6/82. The current MR is 1/246 and 31/246. This preserves the direction on a common cohort. The historical and current service fingerprints differ, so the size difference does not identify a temperature effect. [Matched historical trace](WAVES0123_STABILITY.json)

The four waves record 1,275 physical requests, 1,274 successful transports, one unknown Actor delivery and usage, and two invalid scoring contracts. Reported usage is 1,781,381 tokens. There are no automatic retries. The 86 successful paired Actor calls per method use 806,970 and 400,608 total tokens, respectively, excluding the frozen selection step and grading. Two more wave-four tasks lack historical Gate Actor wires. Wave five continues with the original allocation and grading. No sealed inputs were used. [Costs](WAVES0123_COSTS.json)
