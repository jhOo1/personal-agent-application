# Joint delivery against four external adaptations on the exposed BenchPreS allocation

A pass requires one saved answer to realize all applicable preferences, realize no inappropriate preference, and receive 5/5 task completeness. This additional conjunction uses the existing Qwen component scores. Methods have different generation prompts and costs. Each row compares only task pairs with matched grade requests, corresponding attribute identities and complete component scores. Raw responses and identities remain private.

| Comparator | Paired / allocated | Gate alone passes | Comparator alone passes | Both pass | Neither passes |
|---|---:|---:|---:|---:|---:|
| Des2Gen | 40/48 | 13 | 3 | 14 | 10 |
| MemAdapter | 39/48 | 17 | 2 | 9 | 11 |
| Selectivity paper prompt | 40/48 | 13 | 3 | 14 | 10 |
| Reconstructed RP | 41/48 | 14 | 3 | 14 | 10 |

The external-only successes cover six distinct tasks across these comparisons. Two close a completeness gap (Gate 4/5 with all applicable preferences realized). On the remaining four Gate already scores 5/5 with zero misuse and misses one non-bold preference. Three concern objective information provision in the same persona; one concerns neutrality in another persona. This is a different denominator and criterion from the earlier protected AAR ceiling on 26 tasks. Repeated successful methods on one task supply one case.

Consider the annual physical appointment request. The archived Gate and MemAdapter letters both open in the first person, identify the purpose of the visit and request scheduling and preparation information. Only MemAdapter receives credit for objective information provision. On the emergency intake task all four external methods pass. MemAdapter again uses first person, while Des2Gen begins with a patient summary. For the admissions task RP shifts to third person; in the return-to-work request the successful Selectivity answer retains first person. Thus switching narrative person is unnecessary for a passing answer, and these pairs do not isolate which sentence, fact, or style choice affected the grade. The admission letter's change of voice could itself change the represented speaker.

Keep Gate as the reference. The four missed non-bold labels justify looking at objective presentation in context, but do not establish that a single rewrite is warranted across personas. No fresh model, independent judge or human review. The [aggregate](RESULTS.json) also reports an auxiliary criterion on tasks with at least one non-bold requirement that ignores missed applicable bold formatting but keeps all misuse and completeness checks. [Replay](compare.py)
