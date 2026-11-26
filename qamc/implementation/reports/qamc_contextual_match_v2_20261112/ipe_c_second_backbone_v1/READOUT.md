# IPE-C backbone replication on GPT-4.1

The same frozen choice rule beats both fixed Actor endpoints on the jointly evaluable development sample under both generation backbones. The new run replaced the generator and both RP estimators. It keeps the original estimator prompts, fusion, source text, task and decoding settings. The only planned backbone change is the requested model alias. The fixed adapted GPT-4.1 rubric judged both backbones. Using the same alias for the GPT-4.1 Actor and Judge leaves possible judge self-preference and deployment identity unknown.

| 22 common UIDs, 115 preference positions | IPE-C | Always-Task | Always-Memory |
| --- | ---: | ---: | ---: |
| GPT-4.1 Match | **80** | 71 | 61 |
| Exact archived Qwen Match on the same UIDs | **70** | 61 | 59 |
| GPT-4.1 OPB | 17 | 0 | 32 |
| GPT-4.1 UPB | 19 | 49 | 23 |
| GPT-4.1 FM | 4 | 29 | 5 |

The GPT-4.1 route selects full history on 9/22. After excluding any known flag in either underlying endpoint, 13 tasks and 67 positions remain. GPT-4.1 scores 50/67 versus 44/67 for Always-Task and 38/67 for Always-Memory. On these same UIDs Qwen scores 44/67, 40/67 and 37/67. The two backbones show the same direction on this selected development panel. This does not establish transfer to new source groups or a formal cross-provider leaderboard comparison.

| GPT-4.1 subgroup | Tasks / positions | IPE-C | Always-Task | Always-Memory |
| --- | ---: | ---: | ---: | ---: |
| All A | 8 / 33 | 33 | 33 | 12 |
| B only | 7 / 40 | 22 | 22 | 24 |
| Contains C | 7 / 42 | 25 | 16 | 25 |

The route avoids much of the harm of Always-Memory on all-A and retains the benefit of memory when hard restrictions are present. It does not exceed Always-Task in the B-only layer. Equal Match in that layer does not prove equal task quality or preference use. On the full common denominator IPE-C preserves 10/22 whole-task matches, tied with Always-Task; Always-Memory has 4/22.

## Observed behaviors

- On all-A implicit/047 the user plans a birthday for a friend. The full-history answer promotes the requester's low-fat and low-sugar profile into the party menu. The task-only answer gives several treat options and leaves the decorations open to the birthday recipient's own taste. The route chooses task-only. The original rubric scores 7/7 versus 0/7. This illustrates a named decision and beneficiary, beyond shifting a total score.
- On contains-C explicit/116 the user and partner want to furnish their new dining area. The supplied history rules out wall decor and fabric. The routed answer explicitly avoids both and offers glass or metal. The task-only answer recommends both fabric table settings and a photo wall. The preserved scores are 4/6 versus 2/6.
- On B-only implicit/043, playing audio at bedtime, task-only already suggests natural sounds and piano. Full history adds specific piano pieces and guitar and scores 3/6 rather than 2/6. The frozen rule still chooses task-only and misses this local score gain. It remains a soft-preference boundary.

## Recovery and bookkeeping

The frozen strict run produces 17 common valid tasks, with scores 60/88, 53/88 and 45/88 respectively. Five GPT-4.1 IPE responses contain exactly the three target labels with spaces between some of them. The separate recovery removes whitespace and revalidates original IDs and rank order, then dispatches only their previously unissued full-history Actor and score. The strict version remains independently replayable. One historical full Actor on explicit/114 yielded a stream error with unknown delivery and usage and was not retried. A strict Match field remains missing on a task-only grade for explicit/036. Together they account for the two exclusions in the 24-task roster.

Strict study 133 physical requests, 132 successful, 217,582 known tokens, one unknown. Recovery 10 requests, all successful, 18,344 tokens. Combined **143 physical requests, 235,926 reported tokens, one unknown, no replays of previous dispatches**. The study uses no new or sealed source. No new BenchPreS or PersistBench scores. [Matching author model family in the paper](https://arxiv.org/html/2601.16621)

The strict scores and complete recovery traces remain in the original worktree under the corresponding experiment directory. [Recovery access and evidence](../../../../EVIDENCE_INDEX.md) · [Frozen rules](PROTOCOL.md)
