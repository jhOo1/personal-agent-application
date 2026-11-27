# Additional RPEval single-preference development records

The fixed V1 experiment used 24 single-preference cases from the 156-task plan. After excluding that entire plan's source groups, formal multi groups, reservations and the frozen near-match exclusion list, 62 official single rows belonged to previously allocated, exposed groups. Only 29 rows (29 audit groups) had an allocation file of their own. The legacy RP plan explicitly marks 21 of these as development; the other eight match a custom allocation without the same explicit development designation and are excluded from the score table.

| Historical method adaptation | Answers present among 21 | Strict same-task Match among 18 |
|---|---:|---:|
| RPR_PAPER_XBENCH | 21 | 15/18 |
| D2G_PAPER_ADAPT | 20 | 16/18 |

The join uses release-relative file, track and original row, checks the source file digest, and verifies case UID, public input hash and evaluation hash across the development plan and nine-method archive. The strict slice requires two nonempty answers, both strict flags and exactly one evaluated position each. These are archived adapted rubric scores. A one-position aggregate lead does not establish superiority. These groups are outside the original V1 roster but have prior development exposure.

The inspected nine-method archive contains no MEMADAPTER_FULL answer on this roster. This is not a repository-wide absence claim. The legacy RP and Des2Gen adaptations cannot silently substitute for the FULL implementations used with V1. Before a frozen selector comparison, verify the original wire/actor and scoring configurations and identify the third candidate on exactly these inputs or generate a version-matched missing candidate. Do not fill a missing candidate with the best available method. This audit does not evaluate V1 on any additional task.

Reproduce with Python 3 from the original research workspace via the adjacent audit.py. Inputs are the original census, reservation and near-match metadata, frozen development plans and the legacy nine-method archive. The public copy provides the code and aggregate output only. No new model, scoring or retry requests were made.

## Can the original outputs serve as FULL candidates?

Yes for 41 answers. On the 21 eligible rows, the FULL RP builders reproduce both original successful estimator requests per task and all 21 Actor requests, down to the serialized messages and settings. The responses match all 21 archived candidate strings exactly. The FULL Des2Gen builders reproduce all 21 Decision calls and 20 successful Actor requests with exactly matching answers. This admits 20 complete RP/Des2Gen candidate pairs before looking at scores. It does not supply the missing third candidate.

The V1 bridge's detailed Qwen Judge request (8,192 output cap) for these answers had **zero exact successful matches in the respective original method ledgers**. Thus the old 15/18 and 16/18 are historical adapted scores, not prospectively matched V1 scores. Search other exact caches before dispatching any new grade. Candidate generation and Judge reuse have different eligibility. The same model alias does not authenticate the backend weights across runs.

From the original workspace run the adjacent wires.py with the research Python environment. It imports the actual FULL request builders, opens the two original databases in read-only mode, and emits aggregate checks. Evaluation material is read solely to construct the hypothetical Judge messages; no request is sent. WIRE_COUNTS.json contains the observed counts.
