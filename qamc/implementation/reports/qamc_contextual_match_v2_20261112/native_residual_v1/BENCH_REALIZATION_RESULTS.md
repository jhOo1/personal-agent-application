# BenchPreS first-pass content planning

All 12 exposed tasks are comparable. Both new arms use the exact archived Gate evidence and the same Actor settings and call count. The content-first arm adds a silent inventory of propositions and requested speech acts before realizing the permitted style. It does not expose the intermediate inventory, so the comparison measures the instruction's effect on answers.

| Arm | AAR | Non-bold AAR | MR | Completeness sum |
| --- | ---: | ---: | ---: | ---: |
| Archived Strong Gate | 19/29 | 14/24 | 0/31 | 57/60 |
| Direct generation | 21/29 | 16/24 | 0/31 | 54/60 |
| Content-first | 23/29 | 18/24 | 0/31 | 56/60 |

Content-first improved AAR versus direct in two of three profiles and tied in the third. Relative to Gate, gains by profile were +1, +2, and +1 positions. The nine delivered-miss cases account for all four gains versus Gate (13/22 to 17/22), with completeness 42 to 41. The three protection cases tie Gate at 6/7 AAR and 15/15 total completeness. These are deliberately enriched development cases. The scores use the frozen Qwen adaptation, so the gain is a candidate for wider source-group testing rather than an official benchmark improvement. The completeness shortfall versus archived Gate remains visible.

168 physical requests (24 Actor, 144 Judge), all successful, 285,913 reported tokens, no unknown usage or retries. Sealed data were not used.
