# Additional RPEval single-preference development records

The fixed V1 experiment used 24 single-preference cases from the 156-task plan. After excluding that entire plan's source groups, formal multi groups, reservations and the frozen near-match exclusion list, 62 official single rows belonged to previously allocated, exposed groups. Only 29 rows (29 audit groups) had an allocation file of their own. The legacy RP plan explicitly marks 21 of these as development; the other eight match a custom allocation without the same explicit development designation and are excluded from the score table.

| Historical method adaptation | Answers present among 21 | Strict same-task Match among 18 |
|---|---:|---:|
| RPR_PAPER_XBENCH | 21 | 15/18 |
| D2G_PAPER_ADAPT | 20 | 16/18 |

The join uses release-relative file, track and original row, checks the source file digest, and verifies case UID, public input hash and evaluation hash across the development plan and nine-method archive. The strict slice requires two nonempty answers, both strict flags and exactly one evaluated position each. These are archived adapted rubric scores. A one-position aggregate lead does not establish superiority. These groups are outside the original V1 roster but have prior development exposure.

The inspected nine-method archive contains no MEMADAPTER_FULL answer on this roster. This is not a repository-wide absence claim. The legacy RP and Des2Gen adaptations cannot silently substitute for the FULL implementations used with V1. Before a frozen selector comparison, verify the original wire/actor and scoring configurations and identify the third candidate on exactly these inputs or generate a version-matched missing candidate. Do not fill a missing candidate with the best available method. This audit does not evaluate V1 on any additional task.

Reproduce with Python 3 from the original research workspace via the adjacent audit.py. Inputs are the original census, reservation and near-match metadata, frozen development plans and the legacy nine-method archive. The public copy provides the code and aggregate output only. No new model, scoring or retry requests were made.
