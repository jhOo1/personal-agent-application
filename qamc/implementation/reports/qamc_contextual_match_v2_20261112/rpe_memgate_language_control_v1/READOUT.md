# MemGate language control on 12 exposure-screened development roots

Eleven of 12 fixed development contracts yielded selection scores on both inputs. One local translation result failed the output contract and was not retried. The successful rows cover 63 original sources. They required 74 local translation items, 77 input segments and 10,409 translator input tokens. No new cloud requests, Actor answers or Judge scores.

| Selection comparison | ZH / EN retained sources | Changed roots | Author A exposure | Author B exposure | Author C exposure |
|---|---:|---:|---:|---:|---:|
| Both at released threshold | 53 / 13 | 11/11 | 46/54 → 8/54 | 5/5 → 1/5 | 2/4 → 4/4 |
| Match ZH amount in each task | 53 / 53 | 4/11 | 46/54 → 44/54 | 5/5 → 5/5 | 2/4 → 4/4 |
| Match EN amount in each task | 13 / 13 | 4/11 | 11/54 → 8/54 | 1/5 → 1/5 | 1/4 → 4/4 |

Task-macro within-task AUC for distinguishing C from A moves 0.175 → 0.900 (four mixed roots), while B from A moves 0.867 → 0.528 (three). No threshold or translation was chosen using author labels. The original Chinese results reproduce the frozen decisions on every valid task. The observed C gain at equal item count cannot be explained by fewer records, although ordering may also be affected by translations or token coverage. QAMC has no new end-to-end result from this diagnostic.

## Inspecting unchanged source IDs with changed scores

- **Decorating a child's bedroom.** At the English cut size, English ranking retains the source prohibiting all cartoon patterns in the child's room and replaces an author-A source. The translated source preserves both the no-cartoon condition and its intended room. The cardinality-matched Chinese ranking omits it.
- **Anniversary dinner.** At the original Chinese cut size, the translated ranking restores the source that records avoiding all dairy, including in romantic dining, and replaces a source classified A. The translation keeps discussion of cheese and dairy-free dishes, but loses the unconditional refusal and muddles some dialogue. The selected ID would map back to the complete original. This is insufficient to attribute the rank gain to recognition of the strict condition.
- **Family trip to Qingdao.** At the English cut size, English ranking restores the family's no-seafood restaurant preference, but the translated dialogue loses references to seafood and contains obvious mistranslations. The original describes a food preference for a group and provides no medical allergy claim.
- **Movie visit with a partner.** At the Chinese cut size, one C rises above an A. The translated history retains positive cues about warmth and low tension but omits some explicit descriptions of avoiding suspense, plus some film titles are mistranslated.

These are previously exposed development cases described without publishing private raw logs. The observed threshold drop from 53 to 13 admits very little history and loses four of five B exposures. At matched counts, evidence is positive for identifying certain C constraints and weak or negative for soft preferences. Extend the local fair-baseline audit to the complete eligible roster before deciding any cloud comparison. [Protocol](PROTOCOL.md) · [Exact aggregate](SUMMARY.json)
