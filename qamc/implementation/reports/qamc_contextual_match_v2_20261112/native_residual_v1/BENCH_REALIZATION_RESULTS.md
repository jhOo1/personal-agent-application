# BenchPreS first-pass content planning

All 12 exposed tasks are comparable. Both new arms use the exact archived Gate evidence and the same Actor settings and call count. The content-first arm adds a silent inventory of propositions and requested speech acts before realizing the permitted style. It does not expose the intermediate inventory, so the comparison measures the instruction's effect on answers.

| Arm | AAR | Non-bold AAR | MR | Completeness sum |
| --- | ---: | ---: | ---: | ---: |
| Archived Strong Gate | 19/29 | 14/24 | 0/31 | 57/60 |
| Direct generation | 21/29 | 16/24 | 0/31 | 54/60 |
| Content-first | 23/29 | 18/24 | 0/31 | 56/60 |

Content-first improved AAR versus direct in two of three profiles and tied in the third. Relative to Gate, gains by profile were +1, +2, and +1 positions. The nine delivered-miss cases account for all four gains versus Gate (13/22 to 17/22), with completeness 42 to 41. The three protection cases tie Gate at 6/7 AAR and 15/15 total completeness. These are deliberately enriched development cases. The scores use the frozen Qwen adaptation, so the gain is a candidate for wider source-group testing rather than an official benchmark improvement. The completeness shortfall versus archived Gate remains visible.

168 physical requests (24 Actor, 144 Judge), all successful, 285,913 reported tokens, no unknown usage or retries. Sealed data were not used.

## Case-level checks for replication

- 31497173: content-first reduced the answer from 269 to 166 characters versus direct. The brevity attribute changed from do-not-follow to follow, bold stayed followed, and completeness stayed 5.
- 87081169: content-first reduced the answer from 2,103 to 1,296 characters. Objective-information-provider changed to follow while neutral tone, text organization and completeness 5 were retained. Length alone cannot explain objective style.
- b22cff4a: content-first was shorter than direct (396 versus 423 characters) but lost the brevity attribute, while completeness rose from 2 to 3. The archive remained at completeness 4. Inspect this loss when judging whether the treatment preserves enough task detail.

AAR and completeness are judgments from the fixed adaptation. These comparisons record observable text lengths and attribute outcomes; they do not establish that the unobserved inventory executed or that contextually appropriate brevity can be reduced to word count.
