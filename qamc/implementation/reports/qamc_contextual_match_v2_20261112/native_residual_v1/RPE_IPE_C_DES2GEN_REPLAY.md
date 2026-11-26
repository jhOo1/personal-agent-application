# RPEval fixed IPE-C route with Des2Gen FULL on the history branch

The original IPE-C task-only output and route are fixed. The proposed combination substitutes the archived full Des2Gen adaptation only where the original decision was REUSE_RP. The rule was committed before the paired readout. No task chooses among answers using a score. Des2Gen Actor request hashes and the original RP answer binding are checked. Old scoring and candidate scoring use the existing project's automatic rubric adaptation. Skipped cells are reported independently. This is an exposed development replay with zero new inference, not an independent or official result.

| Common slice | Tasks | Positions | Original IPE-C | Combined | Task wins / losses / ties |
|---|---:|---:|---:|---:|---:|
| Overall | 280 | 1502 | 964 | 957 | 10 / 17 / 253 |
| Replaced history branch | 129 | 777 | 443 | 436 | 10 / 17 / 102 |
| All-A | 117 | 515 | 397 | 393 | 0 / 1 / 116 |
| Only B | 49 | 286 | 150 | 145 | 0 / 4 / 45 |
| Contains C | 114 | 701 | 417 | 419 | 10 / 12 / 92 |

Overall OPB severity rises from 255 to 304, UPB falls from 266 to 228, and FM rises from 53 to 76. These aggregates do not identify individual recovered positions. There are eight missing history-branch cells, seven missing task-only cells and five unknown archived route states among the 300 allocated cases. The 151 valid task-only results are identical by construction. In two preidentified development examples, both routes use history: the cold-weather dinner (implicit/099) moves 3/6 to 4/6, and children's audio (explicit/139) stays 3/10.

Keep the original IPE-C route and its RP history endpoint. The Des2Gen substitution trades increased overuse and severe omissions for lower underuse severity, while losing primary Match and scoring worse on only-B tasks. Do not expand this fixed combination. Evaluation of a stronger backbone should preserve the route, compare matched backbones and continue to report legal-use strata separately. No sealed data were used.
