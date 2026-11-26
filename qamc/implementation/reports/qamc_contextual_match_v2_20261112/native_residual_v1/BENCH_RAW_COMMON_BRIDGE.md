# BenchPreS Raw, Strong Gate and Selectivity on one common panel

The original QAMC Raw full-memory arm has 48 assigned responses in the earlier development archive. All 48 match the later Figure 11 Selectivity panel by stable UID, author record index and hash, public task hash, and evaluation reference hash. Generation and scoring stage settings match the later frozen Qwen single-draw configuration. Raw uses the older project's full-history Actor interface. It is a reference for unconditional history exposure in this project and does not reproduce the exact author default prompt.

| Method | Valid among 48 | AAR on common 38 | MR on common 38 | Non-bold AAR | Completeness |
|---|---:|---:|---:|---:|---:|
| Raw | 45 | 49/64 | 78/126 | 28/43 | 154/38 |
| Strong Gate | 41 | 56/64 | 1/126 | 35/43 | 187/38 |
| Figure 11 Selectivity adaptation | 47 | 53/64 | 12/126 | 36/43 | 185/38 |

All ten frozen profile groups are represented. Metrics are compared on exact same task and ordered attribute references. The large misuse reduction from unconditional history is present for both selective methods. Strong Gate reduces observed MR relative to Selectivity and realizes three more total appropriate attributes, while realizing one fewer non-bold attribute. Completeness differs by two rubric points in total across 38 tasks. These observations reinforce the need to report non-bold realization separately.

Raw has two unavailable Actor rows and one returned answer without complete scoring; Strong Gate has five unissued actors and two incomplete scores; one Selectivity score is incomplete. For the 38 common rows we reused the old stored scores. This audit checks case identity, recorded stage configuration and exact ordered score references. The earlier matched-paper proof of identical reconstituted Judge wires for Gate remains separate. This audit did not reconstruct all Raw request and response hashes across inherited caches or establish the author's official DeepSeek-R1 grading. No new actors, scores or sealed data were used.

Reproduction: run `audit_bench_raw_common.py` after restoring the original project's `qamc_contextual_match_20261111/development_v1` and `benchpres_matched_paper_v1` report inputs. Do not present these as temperature-1, three-draw paper results. The new three-way table does not replace the original 40-task Gate–Selectivity pair.
