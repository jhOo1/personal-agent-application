# One reserved memory slot improves feasibility and increases overuse

The frozen rule did not meet the advancement criteria. It recovers real hard constraints more reliably than adding the next ranked memory, but increases overuse severity and does not beat IPE-C or the RP reconstruction on the affected tasks. Retain it as an equal-count development control. The scores below are from the project's frozen GPT-4.1 RPEval adaptation on exposed development cases.

The policy keeps the translated MemGate set and proposes one omitted original record if the IPE top prediction and the original RP fusion both mark it C. The comparator adds the next translated MemGate record on the same triggers. The shared Actor receives original Chinese text and the same RP policy for each retained ID. No new Selector is called. The 34 triggered tasks span 21 conservatively identified source groups. The other usable tasks did not change. [Frozen protocol](ANSWER_PROTOCOL.md) · [Selection qualification](QUALIFICATION.md)

| Pair, first vs second | Common tasks | Match | OPB | UPB | FM | Task wins/losses/ties |
| --- | ---: | --- | --- | --- | --- | --- |
| Reserved vs next ranked | 32 | 116/199 vs 106/199 | 57 vs 40 | 31 vs 54 | 8 vs 30 | 8/1/23 |
| Reserved vs original English gate | 31 | 113/194 vs 107/194 | 55 vs 41 | 31 vs 54 | 8 vs 39 | 9/2/20 |
| Next ranked vs original English gate | 31 | 103/194 vs 107/194 | 39 vs 41 | 53 vs 54 | 30 vs 39 | 3/6/22 |
| Reserved vs IPE-C | 32 | 116/199 vs 120/199 | 57 vs 55 | 31 vs 19 | 8 vs 7 | 2/3/27 |
| Reserved vs RP reconstruction | 32 | 116/199 vs 120/199 | 57 vs 55 | 31 vs 19 | 8 vs 7 | 2/3/27 |

All triggered tasks have a separate missing-outcome bound in the [machine-generated summary](SUMMARY.json). Match differences against next ranked and against the unchanged gate span [−6, +26] and [−12, +25] positions respectively. Among the 20 valid pairs with genuinely different expanded requests, Match was 77/128 vs 67/128. Aggregating observed differences by source group gives 6 positive, 0 negative, 14 tied for reserved vs next ranked, with one group lacking a valid pair. On the 27 common pairs outside the earlier trial, reserved vs next ranked was 98/172 vs 89/172 and OPB 48 vs 35. Excluding known flags, the same comparison was 81/143 vs 72/143. The two all-A triggers tied on Match at 0/9; they provide no evidence of improved all-A safety. Total source count was 97 for each expansion, and their original source text occupied 24,097 and 23,495 characters.

On audio and dinner, the added refusal removed actual white-noise and chili recommendations even though Match did not change from the original gate. On the Qingdao itinerary, the new draft avoided seafood restaurants but still centered the family itinerary around the requester's long walks. In the living-room false trigger, both expanded arms increased the role of cool colors, although the answer still used warm lighting. These are observed decisions in the deliverable, with no independent human review. [Behavior checks](BEHAVIOR_READOUT.md)

The ledger has 84 new Actor and 84 new Judge attempts, 167 successful transport receipts and one Judge disconnection of unknown delivery and usage. There were zero resends. The reported 360,749 tokens include 184,976 Actor tokens. Two rating contracts per arm did not yield valid Match, and one original-gate rating is missing due to that disconnection. Shared missing slots are counted per arm without claiming separate failures. Six exact cached Actor and scoring records were reused for the 90 distinct logical Actor requests. Full private recovery records are under the research run directory of this name. No sealed data was read.

The next scientific question is whether task-side authority adds value beyond this rule and an ordinary equally informed reviewer. The result establishes a reason to test it and a concrete overuse regression that it must address. It does not show that rank agreement alone protects applicability or that an extra review call will help.
