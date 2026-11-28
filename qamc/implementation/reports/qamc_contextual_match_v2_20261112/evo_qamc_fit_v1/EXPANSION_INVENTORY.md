# Which larger-panel tasks can be verified without opening sealed data?

The source is the existing 296-task jointly scored development matrix. For each row the inventory verifies the IPE-C, Strong Gate or PB_RUBRIC terminal card through the original archive loader. The loader checks answer identity and score provenance. We then exclude the 40-task fit panel and any task sharing one of its conservative source groups. No model calls were made.

| Benchmark | Scored matrix | Same tasks as fit | Other task from fit group | Source-disjoint with verified reference | Qualified source groups |
|---|---:|---:|---:|---:|---:|
| RPEval | 228 | 12 | 90 | 126 | 28 |
| BenchPreS | 26 | 8 | 14 | 4 | 1 |
| PersistBench | 42 | 10 | 0 | 32 | 32 |
| Total | 296 | 30 | 104 | 162 | — |

Ten fit tasks are outside the exact jointly scored matrix and are accounted for when excluding fit groups. The inventory shares no raw prompts, answers or source group identities. The result is an available larger evaluation population within the existing development pool. “Source-disjoint” here means relative to this 40-task fit panel, not independent or previously unexposed. No samples were dispatched or selected.

The BenchPreS limitation is a single additional profile. Findings across its four new tasks can check behavior, but cannot estimate variation across new profiles. Once a joint candidate is ready, report that limitation separately from the much broader RPEval and PersistBench source diversity. An eventual official comparison should use a newly qualified source set and still include the three existing tasks' native metrics and protected outcomes. [Reproducible inventory](EXPANSION_INVENTORY.json)
