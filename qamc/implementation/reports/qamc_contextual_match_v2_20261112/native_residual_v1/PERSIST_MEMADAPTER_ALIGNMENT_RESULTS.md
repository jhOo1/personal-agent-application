# Full MemAdapter compared on the common PersistBench scorer

This comparison reuses the archived full three-stage MemAdapter final answers from the 60-root exposed author-control cohort. Four historical Actor failures remain missing. All 56 successful finals were graded without generation on the same project GPT-4.1 rubric adapter used for the author controls. This keeps the original Qwen grades intact. Each row below uses the specified opponent's stable valid intersection. The scores do not replicate the external paper's full provider and evaluation protocol.

| Opponent | Common | MemAdapter passes | Opponent passes | MemAdapter wins / losses |
|---|---:|---:|---:|---:|
| Archived PB_RUBRIC | 49 | 38 | 43 | 2 / 7 |
| SELECTED_GEPA, prior enriched panel | 14 | 9 | 14 | 0 / 5 |
| SELECTED_GEPA, expanded panel | 19 | 16 | 18 | 0 / 2 |
| SELECTED_RUBRIC, expanded panel | 17 | 14 | 16 | 0 / 2 |

Against PB_RUBRIC, MemAdapter ties on strict beneficial use (18/18 each) and sycophancy (7/12 each, two wins and two losses). The net loss consists of five cross-domain cases, 13/19 versus 18/19. It improves two useful sycophancy diagnostics (dog selection and project-template generation), but both already pass with SELECTED_GEPA in the enriched panel. These post hoc wins identify cases to inspect, not decisions that can be assigned to the method online.

There were 56 new scoring requests, all successful, with 421,171 reported tokens and no unknown usage. Historical inference costs are separate. No final answers or earlier grades changed, and the sealed data were not used. Retain full MemAdapter as an external control. This archive does not support replacing the stronger PB_RUBRIC or SELECTED paths with it. The result leaves the cost-matched native-protocol confirmation and the search for useful history realization on RPEval open.
