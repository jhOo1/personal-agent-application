# Released MemGate language adaptation over the full development roster

All 300 original tasks remain allocated. The frozen RP contract is usable on 295. Eleven successful pilot outputs and one failed pilot output were reused, and the other 283 contracts each ran once locally. Both languages produce usable continuous scores for 286 tasks. Nine have invalid translation or scoring output. The original Chinese selections reproduce exactly in all 286 valid pairs. Successful rows account for 1,806 text items, 1,855 local translator input segments and 258,820 translator input tokens, including reused rows. Failed translation usage is not included. There are no new cloud, Actor or Judge calls.

| Selection comparison | ZH / EN retained | Changed tasks / 286 | A visible /1,216 | B visible /149 | C visible /155 |
|---|---:|---:|---:|---:|---:|
| Released 0.07 threshold | 1,205 / 512 | 284 | 964 → 370 | 117 → 58 | 124 → 84 |
| Equal to each task's ZH count | 1,205 / 1,205 | 145 | 964 → 943 | 117 → 122 | 124 → 140 |
| Equal to each task's EN count | 512 / 512 | 180 | 410 → 370 | 50 → 58 | 52 → 84 |

At matched English counts, the 40 net replacements of A by B/C are spread across a mixed set of groups. Over the original 45 conservative source groups, 25 gain and seven lose applicable sources, with 13 unchanged. There are 51 tasks adding at least one B/C without losing any B/C and 18 with losses and no gains. The equal-ZH controls retain more B/C overall (+21) but also deliver 943 author-A positions. Count matching holds the number of complete original records fixed. Their lengths can differ.

The same English representation without the learned mask already improves within-task ordering. Over 168 mixed tasks, task-macro AUC for B/C versus A is 0.5675 in Chinese and 0.6941 in English with plain cosine. With the released gate, it is 0.5198 and 0.6668, respectively. Both English C-vs-A and B-vs-A AUC are higher using cosine than with the released mask. In the closed dataset there are 14/1,520 truncated English memory views and 731/1,520 truncated Chinese views under the actual fixed embedding limit. The English views contain zero unknown tokens. This measures encoder representation and ordering. The pilot demonstrates that passages can become shorter because information is absent from the translation. It is therefore unsupported to equate decreased truncation with preservation. [Case audit](READOUT.md) · [Coverage and unmasked cosine](WIDE_REPRESENTATION.json)

**Implication for the next comparison.** Published threshold transfer sharply reduces A exposure and also sacrifices B/C. The same-count rankings preserve more B/C than Chinese ranking, but some groups still lose applicable sources. Ranking changes justify an exact, limited Actor test that compares translated gate and the simpler translated cosine under the same task-level count and checks genuine realization. Any score difference would still be conditional on the task and two-level representation. Neither the translation nor the scores are sent to the Actor. This study does not select a replacement for IPE-C or a new official baseline score.

[Protocol](WIDE_PROTOCOL.md) · [Source, exposure and grouping counts](WIDE_SUMMARY.json) · [Direct-transfer end-to-end results](../rpe_memgate_matched_actor_v1/READOUT.md)
