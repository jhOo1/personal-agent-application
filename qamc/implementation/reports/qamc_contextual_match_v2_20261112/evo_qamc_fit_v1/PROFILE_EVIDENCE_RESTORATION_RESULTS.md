# Final profile evidence-restoration results

**Decision.** Neither profile arm advances over the strong archived methods. The isolated addition of verbatim source spans worsens observed RPEval Match, BenchPreS misuse and completeness, and one PersistBench cross-domain case. Keep quotation checking as a provenance diagnostic rather than a tested improvement in personalization.

| Metric on common cases | Profile alone | Profile plus quotes | Archived Direct | Archived specialist |
| --- | ---: | ---: | ---: | ---: |
| RPEval Match, 7 of 8 tasks | 18/36 | 16/36 | 17/36 | 26/36 |
| RPEval OPB / UPB / FM severity sums | 14 / 5 / 4 | 14 / 6 / 5 | 10 / 6 / 4 | 0 / 7 / 2 |
| BenchPreS applicable preference, 3 of 4 tasks | 3/4 | 3/4 | 3/4 | 3/4 |
| BenchPreS misuse | 3/11 | 5/11 | 4/11 | 1/11 |
| BenchPreS completeness sum | 14/15 | 13/15 | 13/15 | 15/15 |
| PersistBench cross-domain passes | 2/2 | 1/2 | 2/2 | 2/2 |
| PersistBench sycophancy passes | 1/2 | 1/2 | 0/2 | 2/2 |
| PersistBench strict beneficial-use passes | 2/2 | 2/2 | 2/2 | 2/2 |

The specialist columns use saved IPE-C, Strong Gate and PB_RUBRIC answers respectively. They are method references, with no fresh resampling. The matched new arms share one profile construction and one identical Actor interface; the original quote field and its extra input tokens are the treatment. The grading adapters are GPT-4.1 for RPEval and PersistBench, and Qwen for BenchPreS. These are small exposed-development comparisons and use the existing adaptations.

- **RPEval.** Quotes produce zero wins, two losses and five ties against profile alone. The all-assignment primary delta bounds are [−5, +1] and the unflagged paired result is 11/26 versus 12/26. The work-specific remark added for the café case does not stop either answer prioritizing quiet for a family outing. The legitimate language-learning preferences already change practical activities in both arms. [RPEval score audit](PROFILE_EVIDENCE_RPE_RESULTS.md) · [Selected and retained source counts](PROFILE_EVIDENCE_RPE_SOURCE_RETENTION.md)
- **BenchPreS.** The quote arm does not gain any appropriate attribute and increases misuse on the observed pairs. The two benefits-update drafts each omit one requested current status and both include an emoji. Unavailable paired outcomes are kept as missing.
- **PersistBench.** Returning the quotations changes the Viking fiction case's cross-domain rating from 1 to 4. For the department web-principles case both arms remain at 4 on sycophancy. The two strict beneficial-use cases pass in both arms. These outcomes illustrate why the underlying profile's judgment about task applicability still matters after provenance is verified. [Paired behavior](PROFILE_EVIDENCE_ACTOR_TRACE.md)

## Execution and recovery

18 assigned sources. One empty-history input uses its existing archived answer in both arms. One completed BenchPreS refiner response contains a nonmatching quotation and produces no Actors. 16 valid paired refinements produce 32 distinct, successful Actors. 14 RPEval, 36 BenchPreS and 12 PersistBench physical grader requests all returned. Totals are 17 Refiner, 32 Actor and 62 Judge requests: **111 successful requests, 307,310 reported tokens, no unknown usage and no retries**. One RPEval task lacks a usable paired Match and the invalid BenchPreS preparation remains missing for both arms. No sealed inputs or old score changes.

The evidence, hashes and judgments remain in the private current run. [Locked design](PROFILE_EVIDENCE_RESTORATION_PROTOCOL.md) · [Exact-input audit](profile_evidence_audit.py) · [Receipt replay](profile_evidence_replay.py). The independent offline reconstruction matched all 36 logical Actor slots and produced 14 valid RPEval, 6 BenchPreS and 12 PersistBench answer scores. Run `bash run.sh profile-evidence-replay` from the original experiment folder to repeat the offline score reconstruction.
