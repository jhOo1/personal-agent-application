# Speaker turns did not improve RPEval on the fixed history route

Keep the original IPE-C Actor interface. Across all nine exposed roots, the structured turn format had zero Match wins, one loss and eight ties against the contemporaneous flattened control. It also lost two tasks against the archived exact IPE-C output. The offline input audit verified identical source text after joining turns and identical final task, policy, system boundary and decoding settings for all nine roots. The structured arm supplied 29–59 historical messages per task. The flat arm supplied one historical message. Neither arm permits attributing a difference to role markers alone.

| Common stratum | Original IPE-C | Flat archive | Speaker turns |
|---|---:|---:|---:|
| Overall Match, 9 roots | **24/48** | 22/48 | 21/48 |
| B only, 3 roots | **9/16** | 7/16 | 6/16 |
| With C, 4 roots | 15/24 | 15/24 | 15/24 |
| All A on the history route, 2 roots | 0/8 | 0/8 | 0/8 |
| OPB / UPB / FM severity | 16 / 10 / 2 | 17 / 11 / 4 | 18 / 11 / 4 |

In the anniversary-gift task (`implicit/110`), the flat answer already offers crafts as a conditional addition to a broader gift list. The turn-structured answer moves handmade items into standalone options and adds doing a craft together. This changes how strongly the suggestions shape the gift. Adapted Match drops 3/5 to 2/5 and OPB 1 to 3, while UPB 1 to 0. These scores alone cannot establish which source positions changed. In the friends' picnic task (`implicit/094`), both live arms favor quiet, low-traffic spots and recommend two to four people. Historical role boundaries did not prevent the individual's quiet setting preference from shaping the group plan. Both score 0/4. In the family meal and clothing cases, aggregate ties cannot certify identical handling of each legitimate preference.

There were 36 physical requests (18 Actor, 18 GPT-4.1 project-adapted Judge), all 36 usable, 86,016 reported tokens and no retries or unknown usage. Historical results were reused. No sealed data were opened. This is a focused development experiment on implicit history-enabled roots. These results do not estimate behavior on all 300 tasks or certify safe rendering of arbitrary untrusted chat history. Kimi eligibility was a separate stopped experiment, so its failed requests are not included here.

[Protocol](PROTOCOL.md) · [Reproducible runner](run.py) · [Aggregate audit](SUMMARY.json)

Exact paired requests, historical data, paired answers and ledgers remain in the original worktree's private run directory `runs/qamc_contextual_match_v2_20261112/rpe_history_turn_encoding_v1`.
