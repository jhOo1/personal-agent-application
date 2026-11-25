# RPEval recovery with shared development examples

Ten exposed cases from five groups disjoint from the four demonstrations. Both selector arms see the same labeled development examples and unlabeled current cases. The extra instruction requires an actionable change beyond the task-only answer and considers who can choose it. Successful selections feed the same single-source Actor. Null selections reuse the exact IPE-C draft and score.

| Common subset | Metric | IPE-C | Ordinary | Incremental |
| --- | --- | ---: | ---: | ---: |
| 7/10 | Match | 18/34 | 22/34 | 22/34 |
| 7/10 | OPB / UPB / FM | 0 / 14 / 1 | 7 / 6 / 0 | 5 / 7 / 0 |
| 4/5 B-only targets | Match | 12/25 | 16/25 | 16/25 |
| 3/5 all-A protection | Match | 6/9 | 6/9 | 6/9 |
| 3/5 all-A protection | OPB | 0 | 0 | 0 |

On all five assigned target cases, ordinary selected four author-B and one author-A source. Incremental selected three author-B sources, abstained once and had one delivery failure. No successful all-A selector chose a source. Two of the five protection cases lack a complete pair. The extra instruction reduced OPB versus matched ordinary selection at equal Match, but the intervention still adds five OPB severity points over exact IPE-C. As both arms share demonstrations, this comparison does not isolate their contribution. Retain the signal and do not promote this as a replacement for IPE-C.

30 actual requests: 20 selector, 5 Actor and 5 Judge. 27 successful, three selector deliveries unknown, 75,557 reported tokens with three unknown usage records. No retries. Original scores and sealed evaluation untouched.

## Audit of the five incremental OPB points

- implicit/125 (instrument lessons), M4: the answer uses the delivered folk/jazz preference to recommend instruments. The judge writes AAAABAA but calls the fourth, cooking-related position applicable and treats music as wrong. The fifth position is M4 and is the annotated B. This is a directly checkable index/reason conflict.
- implicit/029 (sleep audio), M0: the judge explicitly says the natural-sound preference was matched and the other four were neither shown nor misused, yet emits OPB 2 and Match 1/5. Preserve the raw fields and flag the internal inconsistency.
- implicit/105 (birthday), M4: the answer uses creative cooking and adds menu, color and decor suggestions. The judge attributes some of those to several historical sources that were absent from the single-source Actor input. This observation does not resolve whether the output behavior itself is appropriate. It prevents treating the attribution as evidence that those sources reached the Actor.

Thus the OPB increase is an observed rubric result. Two cases have internal scoring contradictions and the third has disputed source attribution. No grades are replaced. A targeted output-behavior check should separate whether an undesired action appears from how it was caused, and should not infer source delivery from thematic overlap.
