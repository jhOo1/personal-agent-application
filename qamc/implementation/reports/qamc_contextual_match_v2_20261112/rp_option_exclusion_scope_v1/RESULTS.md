# Option-specific checking on the original history-enabled RP generator

**Do not promote.** The 14 primary development roots are disjoint from the previous masking panel. The two motivating examples were scored separately. Both new arms retained the exact original RP user input and policies, and each received one additional system instruction. No new retrieval or parameter training. All 32 Actor and 32 adapted GPT-4.1 Judge calls succeeded. Reported usage was 164,376 tokens, with zero missing usage.

| Primary set: 14 tasks / 88 preference positions | Match | OPB | UPB | FM |
|---|---:|---:|---:|---:|
| Original IPE-C | 48 | 20 | 11 | 3 |
| Ordinary practical answer check | 47 | 25 | 11 | 5 |
| Option exclusion scope check | 46 | 26 | 9 | 5 |

On the primary tasks the intervention tied ordinary thirteen times and lost once (explicit/139, 4/10 to 3/10). Across the ten unflagged three-way cases, original/ordinary/scope Match was 37/36/35 of 66. No primary task beat both controls. The UPB reduction on the full panel did not persist in the unflagged subset (ordinary 6 versus scope 7).

Both diagnostic tasks tied on Match, 6/9 total per method. In the bedtime audio example (explicit/132), the memory specifically excludes white noise and mechanical sounds. Both fresh answers still advised avoiding rain and waves as categories. The scope instruction failed the anticipated behavioral repair. In the Korean wedding language task (explicit/057), ordinary proposed written material and practical phrases, while scope explicitly recommended text and audio, offline dictionaries and avoiding registration. Its answer was 1,705 characters versus 821 for ordinary; the advice to state the constraint once did not itself produce a shorter delivery. Length alone cannot establish redundancy. The RP actors in these two tasks had their original predicted source policies, including B labels; unlike the previous diagnostic masking arm, they saw all original source texts.

This was an instruction-level intervention with one sample per arm, on exposed development roots. Its failure leaves open whether externally generated alternatives with verified properties would change actual behavior. The original generator remains the stronger reference on this panel.

[Frozen protocol](PROTOCOL.md) · [Complete instructions and runner](trial.py) · [Scores and matched denominators](RESULTS.json)
