# RPEval author multi-roster identity and matched input formats

The 300 assigned IPE-C rows are precisely the 300 author multi-preference tasks at [release commit 0f8bce80](https://github.com/XueyangFeng/RPEval/tree/0f8bce80a03e6b86426485264b14ae7de49cc8f9). The 24 non-`formal_multi_v1` UIDs are legacy identities retained for those same author rows. This resolves the namespace caveat in the preceding audit. The verified claim is full **allocated author multi-roster coverage** and partial paired score coverage in the project development protocol.

Both original files match the pinned commit byte-for-byte. Each row matched its frozen native hash, stored evaluation copy, original-input adapter output and manifest UID. IPE-C and the RP reconstruction still use the project's Qwen generation and GPT-4.1 detailed scoring adaptation. The release identity check does not validate the code-release short Judge, model weights, or independent confirmation.

| Author track | Allocated tasks / positions | Strict common tasks / positions | IPE-C Match | RP reconstruction Match | IPE-C absent / RP absent / both absent |
|---|---:|---:|---:|---:|---:|
| Explicit multi | 150 / 803 | 140 / 754 | 510 | 431 | 9 / 7 / 6 |
| Implicit multi | 150 / 803 | 140 / 750 | 460 | 410 | 9 / 6 / 5 |
| Total | 300 / 1,606 | 280 / 1,504 | 970 | 841 | 18 / 13 / 11 |

The 102 positions outside the common set belong to 20 author tasks. The method-specific missing counts overlap, with 11 tasks missing both strict scores. The combined totals do not treat missing grades as wrong. Four archived route rows lack a saved label but their frozen author labels are present and independently verified. Their scores were not filled. The archived results and failure states remain intact.

## Counterpart verification

A counterpart key is the exact tuple of the author's Query, ordered explicit persona descriptions and author A/B/C string. The descriptions in the implicit release are evaluation-side here. They do not feed the implicit Actor, which receives the original dialogue history only if the method permits it. Two keys occur twice in each track and three single keys on each side lack an exact counterpart. Thus 143 unambiguous pairs are available. All share their conservative source-group identifier. Only 16 of the 150 same-numbered rows share the complete key. Pairing by index would mix nonmatching questions, preferences or labels.

The four-way valid intersection requires strict Match from both methods in both input formats. Each track has the same position denominator on this intersection.

| Author label stratum | Valid pairs / positions per format | Explicit IPE-C / RP | Implicit IPE-C / RP | Same IPE-C history on/off decision |
|---|---:|---:|---:|---:|
| All A | 52 / 232 | 201 / 130 | 179 / 125 | 45/52 |
| Only B | 24 / 139 | 72 / 76 | 73 / 71 | 18/24 |
| Contains C | 52 / 322 | 196 / 196 | 186 / 188 | 49/52 |
| All | 128 / 693 | 469 / 402 | 438 / 384 | 112/128 |

The IPE-C advantage over RP is concentrated in all-A tasks under both formats. The explicit only-B slice loses four positions to RP while the implicit only-B slice gains two. The explicit contains-C slice ties RP and the implicit contains-C slice loses two. More explicit input does not by itself create a consistent IPE-C advantage on legitimate-use tasks. These are archived scored pairs, with each format using its intended source text and the complete strategy pipeline, so the difference cannot be attributed to the Selector or Actor alone. They are counterpart comparisons, not 256 independent source observations.

Two concrete checks make the distinction important. In the same after-work sleep-audio task with `BABAAA`, IPE-C takes the history route in explicit row 42 (4/6) and the task-only route in implicit row 43 (3/6). In the same Korean wedding study task with `CAA`, explicit row 118 uses history and implicit row 115 takes task-only, but both score 1/3. A changed route is visible in both examples and is not a sufficient explanation for an observed score difference.

Reproduce with `PYTHONPATH=src python3 audit_rpe_release_identity.py` from the research repo root (provide the script path). The script reads the two already-exposed multi files, their frozen project manifests and scored endpoints only. The author single-preference files, sealed cases and new labels were outside scope. No model requests, data migration, or score changes occurred.
