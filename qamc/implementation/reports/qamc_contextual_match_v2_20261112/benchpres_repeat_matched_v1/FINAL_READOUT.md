# BenchPreS frozen three-draw comparison

All six waves settled on the fixed allocation of 48 exposed tasks and 10 profiles. Both methods use the same Qwen3.8 Flash alias, temperature 1.0, three separately identified draws and the fixed Qwen grading adaptation. Strong Gate retains its original selected text, GEPA system policy and use guidance. Selectivity uses the authors' Figure 11 defense. The methods do not share identical Actor prompts. The proceedings evaluation uses DeepSeek-R1 to detect preference occurrence. This result is a comparison under the adaptation. [Frozen protocol](PROTOCOL.md) · [Full replay](FINAL_REPLAY.json)

| Common scored task–draw pairs | Strong Gate | Author Selectivity |
| --- | ---: | ---: |
| MR | 1/346 | 44/346 |
| AAR | 155/184 | 138/184 |
| Bold AAR | 60/62 | 42/62 |
| Non-bold AAR | 95/122 | 96/122 |
| Completeness | 504/106 | 501/106 |

There are 106 common pairs on 38 tasks. Restricting the comparison to 32 tasks with complete scores on all three draws gives MR 1/315 vs 39/315, AAR 139/165 vs 121/165, non-bold AAR 84/108 in both arms, and completeness 458/96 vs 454/96. On the available pairs, MR favors Gate in nine profiles with one tie. The profile-bootstrap range for the paired MR difference is −16.34 to −8.05 points. The AAR range is −0.56 to +22.97 points, and the non-bold AAR range is −6.61 to +9.41 points. These intervals resample the observed exposed profiles. [Profile sensitivity](FINAL_PROFILE_TRACE.json)

## Interpretation and missing outcomes

On the complete 48-task allocation, the fieldwise diagnostic bounds the Gate-minus-Selectivity differences at −101 to +39 MR positions out of 480, −13 to +50 AAR positions out of 240, +8 to +32 bold positions out of 87, and −21 to +18 non-bold positions out of 153. Completeness ranges from −115 to +53 total points across 144 draws. The intervals preserve known individual grades and vary only the missing fields. Of these outcomes only bold AAR retains its sign over the full assignment range. The available-pair MR advantage is large across profiles, but cannot certify lower MR on the full roster given the missing responses. [Fieldwise replay](FINAL_FIELDWISE.json)

Thirty-six of Selectivity's 44 flagged misuses involve an exact inappropriate nickname, confirmed in the saved answer. Three further exact appearances receive no adapted Judge flag. Gate has no exact inappropriate nicknames on the same 106 positions. This makes a large part of the observed MR contrast directly observable and leaves suitability governed by the author labels. Non-bold realization remains unresolved. On 119 of 122 paired non-bold positions the exact normalized preference is visible in both requests and both methods receive credit on 84 of those positions. On the three other draws of one debt-consolidation task, the exact objective-information preference is absent from Gate's selected sources and fixed facts. Selectivity sees it and receives credit twice. Both downstream realization and at least one upstream omission remain in the evidence. [Misuse](FINAL_MISUSE_TRACE.json) · [Delivery](FINAL_DELIVERY_TRACE.json) · [Grounding example](OBJECTIVITY_GROUNDING_TRACE.md)

## Execution

- The final wave contributed only two complete pairs. It dispatched 45 Actor requests and 132 rating requests, with 23 Actor and seven Judge timeouts. All 30 retain unknown delivery and usage. The comparator conclusions above use the frozen intersection and report the missingness explicitly.
- Complete study: 1,767 physical requests, 1,736 successful transports, 31 unknown deliveries and usages, four invalid score contracts, and 2,430,117 reported tokens. Zero automatic retries. Fifteen unavailable Gate draws are from missing historical Actor wires, separate from transport failures. Gate has 113/144 complete scores and Selectivity 126/144. All 273 executable Actor slots are separately registered; the final 1,494 grade positions contain no inherited grades.
- Across 115 successful common Actor pairs, Gate reports 1,063,497 total tokens and Selectivity 533,529. This excludes selection and grading. The measure identifies the cost of the whole frozen Actor contract. It does not isolate evidence-selection cost.
- The artifact verifier reconciles manifests, receipts, score fields and analysis denominators, with no model requests added. Raw cases, requests, answers and service records remain in the private run. No sealed input was used. [Costs](FINAL_COSTS.json) · [Draw identity](FINAL_IDENTITY.json) · [Historical comparison](FINAL_STABILITY.json) · [Acceptance and hashes](FINAL_ACCEPTANCE.json) · [Verifier](settle_repeat.py)
