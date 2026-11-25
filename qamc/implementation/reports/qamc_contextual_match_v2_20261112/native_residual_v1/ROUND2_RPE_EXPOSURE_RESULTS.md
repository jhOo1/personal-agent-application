# Round 2: RPEval per-source exposure versus a whole-history switch

Twelve exposed development roots, six with A and B but no C and six with A and C, were selected from distinct source groups by frozen hashes without ranking on scores. Both arms reuse the archived RP policy and identical Actor configuration, task, and policy annotations. The per-source arm exposes only original entries predicted B/C. The switch exposes the complete history if any entry is predicted B/C and otherwise exposes none. In all twelve cases the switch exposed the complete history. The arms exposed 47 and 71 original entries respectively. This is a comparison of execution granularity conditional on the same predictions.

| Common slice | Per-source Match | Switch Match | Per-source OPB / UPB / FM | Switch OPB / UPB / FM |
|---|---:|---:|---:|---:|
| All 12 | 41/71 | 41/71 | 16 / 17 / 1 | 12 / 17 / 0 |
| B without C | 19/35 | 19/35 | 8 / 10 / 0 | 4 / 12 / 0 |
| Contains C | 22/36 | 22/36 | 8 / 7 / 1 | 8 / 5 / 0 |

Match wins/losses/ties were 2/2/8 for per-source execution. The bias fields are severity sums, not counts of rejected or applied sources. All 24 final answers and 24 grader calls returned successfully and all were scored. Reported use was 112,208 tokens. The project uses automatic GPT-4.1 grading, with no human calibration in this run. No selector was rerun and no sealed data was used.

Do not promote the current per-source execution rule. It did not improve Match, increased overuse severity, and had higher underuse severity on roots containing C. The earlier PersistBench development result remains separate and supports selective exposure, particularly abstention on some sycophancy tasks. It does not establish that this finer execution scheme improves mixed-evidence tasks. No SOTA claim follows. This closes the second authorized design round. The research remains incomplete and is paused pending user direction.
