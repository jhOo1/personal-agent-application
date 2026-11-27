# Do source-specific boundary cards improve the final answer?

**Close this transfer as a candidate.** The experiment assigned 18 exposed RPEval roots. Sixteen had usable, verified author induction records. All 16 ordinary preparations, 32 answers and 32 grades completed, with 394,778 reported new tokens. The original 16 induction calls cost another 230,898 tokens at cold start. Both generators saw the complete original sources and used the same author Stage-1-only generation template. These results test an author ablation under local generation and grading protocols.

| 16 common roots | Match / 93 | OPB | UPB | FM |
|---|---:|---:|---:|---:|
| Induced boundary cards | 46 | 26 | 14 | 5 |
| Ordinary source records | 52 | 30 | 9 | 6 |
| IPE-C | 60 | 14 | 17 | 2 |
| Reconstructed RP | 56 | 22 | 10 | 3 |
| Strong Gate | 43 | 35 | 13 | 10 |

Induction versus ordinary had zero Match wins, two losses and fourteen ties. Five B-only roots tied 19/32; RP reached 23/32. On six roots containing C the comparison was 23/38 versus 24/38. On five all-A roots it was 4/23 versus 9/23. The five-position loss on implicit/017 has a severity-inconsistency flag. On the eight roots clean across all five methods, induction lost one comparison and tied seven.

On explicit/029 (a team dinner), both actual answers used the same history about avoiding an alcohol-centered restaurant and strongly flavored food. Both suggested gentle cuisines and quiet seating. The ordinary answer supplied more restaurant types and concrete exclusions; the boundary-card answer also asked for location, group size and budget. The judge assigned ordinary five matched positions and induction four. Neither this one-point difference nor the flagged five-point loss identifies an individual source as the cause. The experiment offers no paired evidence to add induction to the common policy.

[Aggregate tables](PAIRED_SUMMARY.json) include all strata, five-way and pairwise intersections, and recorded missing usage. [Frozen protocol](PROTOCOL.md), [generator](trial.py), and [scorer and cold cost](summarize.py) distinguish the 18 assigned from the 16 scored. No sealed sources were evaluated.
