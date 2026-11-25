# Selective activation beats both fixed endpoints on exposed RPEval tasks

Three methods have strict common Match on 274 of the fixed 300 exposed RPEval multi-preference tasks. All compare the same original Actor and generation caps. IPE-C chooses the RP completion if IPE's best rank is C for at least one source. Always-Memory is the unchanged RP reconstruction, and Always-Task uses the same Actor template with an empty history and use-policy array.

| Matched score stratum | Tasks / positions | IPE-C | Always-Task | Always-Memory |
| --- | ---: | ---: | ---: | ---: |
| All paired | 274 / 1462 | **953** | 874 | 824 |
| All A | 116 / 512 | 400 | **426** | 267 |
| Only B present | 48 / 278 | 145 | 142 | **147** |
| Contains C | 110 / 672 | 408 | 306 | **410** |
| Exclude any known grading flag | 184 / 1022 | **701** | 655 | 592 |
| Additional 67-task archive only | 58 / 320 | **188** | 178 | 179 |

IPE-C's +79 Match over Always-Task comes from +102 on contains-C and +3 on only-B, offset by −26 on all-A. Conversely, +129 over Always-Memory comes from +133 on all-A, offset by −2 in each applicable-preference slice. The two baseline comparisons establish a measurable conditional activation benefit with trade-offs, under this common project protocol. They do not demonstrate reliable soft-preference recovery.

Across all 274 tasks, IPE-C, Always-Task and Always-Memory respectively have OPB 247, 80, 371; UPB 248, 515, 227; FM 51, 250, 55. These are severity totals from an automatic adapted rubric. Original scores are preserved. Twenty-six assigned tasks do not have all three strict positions. No added generated answers were needed. Of the 29 prior-history tasks requiring an Always-Task endpoint, 28 reused exact saved answers and one saved failed generation was preserved. Seven previously unissued GPT-4.1 author-rubric scores ran, all succeeded, with 15,903 tokens and zero unknown usage. Zero new Actor or estimator; no sealed data.

Results and raw scoring receipts（原仓库 `reports/qamc_contextual_match_v2_20261112/ipe_c_two_endpoint_completion_v1/RESULTS.json`，见[恢复索引](../../../../EVIDENCE_INDEX.md)） · [Protocol](PROTOCOL.md) · Same-rate 216-task controls（原仓库 `reports/qamc_contextual_match_v2_20261112/ipe_c_rate_matched_controls_v1/READOUT.md`，见[恢复索引](../../../../EVIDENCE_INDEX.md)）
