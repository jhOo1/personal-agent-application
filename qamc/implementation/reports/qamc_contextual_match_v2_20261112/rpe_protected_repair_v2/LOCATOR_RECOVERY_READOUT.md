# Locator contract sensitivity results

The original trial and its scores are preserved. Removing one unsolicited locator field restored four validated diagnoses. The same eight secondary requests produced eight new answers, all scored with the frozen detailed Qwen RPEval adapter. The separate extension made 16 physical requests, all successful, with 82,381 reported tokens and no retries. It did not reissue a locator or recover any delivery-unknown sample.

| Same 13 common items | Match ↑ | OPB ↓ | UPB ↓ | FM ↓ |
| --- | ---: | ---: | ---: | ---: |
| RP reconstruction | 9/13 | 0 | 2 | 8 |
| V1 witnessed whole-answer choice | 10/13 | 0 | 2 | 7 |
| Main FREE | 10/13 | 0 | 2 | 6 |
| Main PATCH | 10/13 | 0 | 2 | 6 |
| Composite FREE with projected diagnoses | 11/13 | 0 | 0 | 4 |
| Composite PATCH with projected diagnoses | 10/13 | 0 | 3 | 6 |

One B task explains the additional Match difference. In the brunch task, both arms received the same diagnosis of a missed opportunity to honor the requester's preference for creative experiences. PATCH changed the opening selection criterion, but the concrete brunch choices still lacked distinctive options. FREE incorporated specific compatible choices into its recommendations, such as a distinctive offering alongside familiar dishes and options the parents could select comfortably. The project scorer changed Match from 0 to 1 only for FREE. On the other three restored tasks both arms retained the original Match. The Japan revisions still mention seafood in conditional form, and neither establishes ingredients or a medical restriction. The Xi'an and Italy travel tasks demonstrate retained passing scores with different amounts of rewriting.

On all 15 same-item valid tasks, the composite is 13/15 FREE and 12/15 PATCH. The B slice on the historical intersection is 5/5 FREE and 4/5 PATCH. The full 22-task missing-data bounds are [−9, 8] for PATCH minus FREE, [−8, 0] for PATCH minus V1 and [−8, 1] for FREE minus V1. The parent and extension together made 59 physical requests and used 283,925 reported tokens with nine delivery-unknown records. Their scores stay missing.

This extension makes the difference between identifying a defect and realizing a preference visible. A genuine deletion can fix a valid hard restriction with little disturbance, as in plant-protein muscle gain. A legitimate soft preference may need concrete options in the body rather than a change to an introductory criterion alone. The next mechanism comparison should retain the bounded deletion path and test whether adding the needed decision dependencies while keeping unrelated text fixed can match the positive behavior of FREE. The present executor remains a diagnostic and is not promoted on this evidence.

[Extension cost](LOCATOR_RECOVERY_COST.json) · [Composite aggregates](LOCATOR_RECOVERY_SUMMARY.json) · [Main results](READOUT.md)
