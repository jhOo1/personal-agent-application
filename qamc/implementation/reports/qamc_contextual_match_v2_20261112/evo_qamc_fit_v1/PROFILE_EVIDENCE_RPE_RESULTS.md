# RPEval: original-quote restoration does not improve profile-only answers

Receipt-only replay on the fixed eight exposed RPEval tasks. The common scorer is the project's frozen GPT-4.1 rubric. Seven tasks have valid paired Match on the two new paths. They include the empty-history archive case by assignment and exclude one case with an invalid Match response. The original records and flags are preserved.

| Common slice | Profile with quotes | Profile only | IPE-C |
| --- | ---: | ---: | ---: |
| Overall Match, seven tasks | 16/36 | 18/36 | 26/36 |
| OPB / UPB / FM on those tasks | 14 / 6 / 5 | 14 / 5 / 4 | 0 / 7 / 2 |
| All-A Match, three tasks | 6/13 | 6/13 | 13/13 |
| B-only Match, two tasks | 5/13 | 6/13 | 8/13 |
| C-containing Match, two tasks | 5/10 | 6/10 | 5/10 |

Quote restoration records zero wins, two losses and five ties against profile-only. Allowing all possible scores for the unmatched task, its assignment-wide Match difference is [−5, +1]. Excluding tasks flagged in either new arm gives 11/26 versus 12/26. Against IPE-C the assignment-wide Match difference is [−10, −7] and the flag-free paired comparison is 14/32 versus 24/32. OPB remains higher than IPE-C on the common tasks.

The profile retained all seven already-selected B/C sources on the nonempty history allocation. In the café task, adding the original work-specific wording did not prevent a quiet environment from driving venue choice. Both language-learning drafts already implement multiple legitimate preferences. These observations separate richer visibility from final task behavior. [Source positions](PROFILE_EVIDENCE_RPE_SOURCE_RETENTION.md) · [Actual Actor cases](PROFILE_EVIDENCE_ACTOR_TRACE.md)

Rebuild the substage from saved requests and receipts using `bash run.sh profile-evidence-replay --domain RPEval` within the original repository experiment directory. The replay issues no requests. BenchPreS and PersistBench will appear in the separately settled result.
