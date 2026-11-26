# Equal-count RPEval final-answer comparison

The English gate has the highest adapted Match on this disagreement-selected development panel. It is a credible comparison to the released English cosine and Chinese ranking, but it is not ready to replace IPE-C. A small Match advantage over the frozen IPE-C answers coexists with worse feasibility and concrete violations of originally available hard preferences.

| 24 sources, 125 matched positions | Match ↑ | OPB ↓ | UPB ↓ | FM ↓ |
| --- | ---: | ---: | ---: | ---: |
| Chinese gate at the English count | 63 | 25 | 36 | 23 |
| English gate at the published threshold | 78 | 26 | 21 | 16 |
| English cosine at the English count | 68 | 32 | 27 | 19 |

English gate vs English cosine is 4 wins, 1 loss and 19 ties. Fourteen ties are exactly identical Actor requests and scores. Across the ten different wires, Match is 32/56 vs 22/56. In the predeclared 10%-character support slice of six different wires, it is 20/34 vs 11/34. English gate beats the Chinese gate on seven tasks, ties 17 and loses none by Match. In 12 character-balanced cases it has 38/65 vs 31/65; 14 of 15 gained positions across the full comparison come from cases where the English gate has longer selected original text. This is evidence against a benefit attributable solely to shorter Actor context. A natural length balance slice is not an equal-token intervention.

English cosine vs Chinese gate is 4 wins, zero losses and 20 ties by Match, with higher OPB despite lower UPB and FM. In the primary gate-vs-cosine comparison, English gate retains 4/9 B and 7/13 C against 3/9 B and 6/13 C; the Chinese counterpart retains 1/9 B and 2/13 C. A exposure is 35/103, 37/103 and 43/103 respectively. Correct exposure does not establish implementation. In the flagged-score sensitivity subset specific to the English pair, gate is 48/81 vs cosine 43/81.

## Against the strongest saved controls

Compared with IPE-C on 22 valid paired tasks, the English gate gets 73/114 vs 67/114 (2 wins, 0 losses, 20 ties by Match). But feasibility severity rises from 4 to 14, and the most conservative all-allocated Match difference given two missing IPE-C outcomes can be zero. Compared with archived full-history RP on 23 valid tasks, Match is 75/119 vs 70/119 and FM rises from 4 to 15. The IPE-C +6 Match comes from the solo exhibit and children's room. Both are development observations.

In the sleep-audio case (explicit 132), the English gate delivers an unrelated source within a budget of one and suggests white noise and train sounds despite the applicable aversion. In the dinner-for-wife case (explicit 005), it omits the no-spicy-food source and proposes chili powder. These are behavioral failures even though the Match scores tie IPE-C. The dinner judge also describes the wrong slot as C in its own rationale. In the family Qingdao case, cosine avoids seafood restaurants while the English gate recommends them, yet the English gate gains one Match position relative to cosine. In the shared dining-room case, the English gate replaces a living plant with no-upkeep alternatives and has lower FM than the other two rankers. [Predeclared behavior and actual drafts summarized](BEHAVIOR_READOUT.md)

## Cost, decision and coverage

The original selected evidence totals are 13,475 Chinese-gate characters, 13,915 English-gate characters and 13,737 cosine characters. All three have the same 46 original records in aggregate and the same per-task counts. The concrete record membership and length vary. Cosine and matched Chinese use the count supplied by the English gate; their costs are not standalone and would include that computation without cached inputs. Actual current input tokens are separately reported for logical positions with a new physical Actor receipt, and measurements on shared receipts count once per reported arm. Conditions are single sampled answers under the same Qwen Actor contract, with some historical exact reuses.

We ran 51 new Actor and 51 new detailed GPT-4.1 Judge requests. All 102 returned successfully, with 188,770 reported tokens, no unknown usage or retries, and valid Match for all 72 logical trial outcomes. Two prior IPE-C Match values remain invalid or absent. Four exact prior scoring receipts associated with non-fixed actors were reused. The 24 tasks were selected before inference by source group and real selection difference; no reserve data or tuning. These scores cannot estimate the full cohort effect or certify an official leaderboard rank.

**Decision.** The English gate provides a real end-to-end selection benefit over both same-count alternatives on this sample. Do not promote over IPE-C while hard feasible use degrades. The observed feasibility problems warrant a targeted comparison of a deployable protection mechanism against the same gate and a strong ordinary control. The next change should address relevant excluded constraints, with the recognition that simply enlarging the evidence budget can bring back theme and beneficiary misuse. [Exact paired results and cost](SUMMARY.json) · [Frozen protocol](PROTOCOL.md)
