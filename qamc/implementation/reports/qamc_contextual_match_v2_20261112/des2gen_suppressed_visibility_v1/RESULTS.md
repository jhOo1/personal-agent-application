# Hiding correctly suppressed memory text did not improve Des2Gen's final answer

Sixteen IPE-C history-on development tasks from distinct conservative groups had mixed frozen Des2Gen decisions. Removing text from Suppress slots concealed 47 author-A sources. The visible slots still contained 19 A, 10 B and 17 C sources. These labels were inspected only after assignment. The intervention preserved IDs, decisions, order, all Apply text, the final system prompt and task. Both arms were freshly generated. Thirty-two Qwen generations and 32 GPT-4.1 adapted grades completed (228,940 reported tokens, zero unknown usage). Neither strict Match parsed for implicit/022, leaving 15 paired fresh tasks; one additional archived strong comparator lacked a usable joint score.

| Common set | Full-text fresh | Masked fresh | IPE-C |
|---|---|---|---|
| 15 fresh pairs: Match / 89 | 49 | 48 | — |
| 15 fresh pairs: OPB / UPB / FM | 37 / 5 / 9 | 40 / 2 / 8 | — |
| 14 with strong reference: Match / 85 | 47 | 46 | 48 |
| 14 with strong reference: OPB / UPB / FM | 36 / 3 / 9 | 38 / 2 / 7 | 27 / 8 / 5 |
| 9 unflagged three-way pairs: Match / 59 | 30 | 30 | 31 |

The archived full Des2Gen answer also scored 47/85 on the fourteen common tasks. Zero masked answers beat both comparators on the same task. This does not establish equivalence; each new wire had a single answer and automatic grade.

In explicit/074 (a three-day family visit to Qingdao), both answers kept the sea-ingredient exclusion and walking activities. Full text suggested flexible distances with family-fitness adjustments; the masked answer proposed a long first-day chain of landmarks and allowed reductions based on stamina. Match was 5 versus 4. The change in a particular grade cannot be assigned solely to that itinerary detail. No B or C source was lost. Do not promote the masking change as an improvement on Des2Gen or IPE-C.

[Frozen instructions](PROTOCOL.md) · [Actor and Judge execution](trial.py) · [Paired scores](RESULTS.json) · [Aggregation](settle.py)
