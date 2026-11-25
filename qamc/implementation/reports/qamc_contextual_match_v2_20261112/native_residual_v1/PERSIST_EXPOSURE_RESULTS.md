# Round 1: PersistBench shared-preparation evidence exposure

Both new arms reuse the same query route and source selection. SELECTED_RUBRIC renders only selected original sources in the archived Rubric-informed template. FULL_RUBRIC_WITH_SELECTION renders the complete history with the same selection appended as advisory context. Both use a single new Actor call and the same project GPT-4.1 rubric adaptation. The treatment changes exposure and its presentation together, so this experiment does not isolate the effect of the advisory block or compare with two generic preparation calls.

| Comparison | Common | Archived PB_RUBRIC | Fresh PB_RUBRIC | SELECTED_GEPA | SELECTED_RUBRIC | Full + selection |
|---|---:|---:|---:|---:|---:|---:|
| Five arms, total | 13 | 10 | 9 | 13 | 12 | 10 |
| Five arms, sycophancy | 5 | 2 | 1 | 5 | 4 | 2 |
| Matched new arms, sycophancy | 6 | — | — | — | 5 | 3 |
| Matched new arms, cross-domain | 4 | — | — | — | 4 | 4 |
| Matched new arms, strict beneficial use | 4 | — | — | — | 4 | 4 |

The new exposure comparison used 56 physical requests, all successful, with 531,447 reported tokens. All 28 new answers have scores. The five-arm panel omits one fresh PB_RUBRIC length failure. No sealed data was used. This is an exposed development panel enriched for failures of the archived baseline, evaluated with an adapted rather than author-native Judge route.

Retain SELECTED_GEPA as the strongest tested path on this panel. The Rubric-informed exposure comparison supports carrying forward explicit control over visible evidence, while the three original SELECTED_GEPA wins arose from empty selections. The evidence does not yet establish simultaneous fine-grained retention and exclusion on mixed tasks, or SOTA. The next and final authorized design round should test that gap on real source-separated development cases and compare against a simple whole-history gate as well as the strongest available task-specific reference.
