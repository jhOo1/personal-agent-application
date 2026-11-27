# Same-packet default-aware selection control

The same 24 cases and their original RP default, identical answer ordering, tasks, history and service configuration were used. Both arms made one Qwen selection with temperature 0 and an 8,192-token output cap. The control could choose any answer if clearly better and had no witness requirement. It changes the procedure relative to the older blind control and the witness arm. The existing witness program is unchanged.

| 22 historical common tasks | Match ↑ | OPB ↓ | UPB ↓ | FM ↓ |
| --- | ---: | ---: | ---: | ---: |
| RP reconstruction | 17/22 | 0 | 7 | 17 |
| Ordinary blind Qwen | 17/22 | 2 | 2 | 15 |
| Default-aware Qwen | 18/22 | 4 | 5 | 13 |
| Conflict and compatible-option witnesses | **19/22** | 1 | 2 | 12 |

Default-aware selection changes the answer on **21/24** cases, against **5/24** in the witness arm. Both recover the plant-protein and winter formalwear targets. The only strict Match difference between them on the 22-task panel is a Japan cuisine task. Original RP and the witness-selected Des2Gen answer receive a match. Default-aware selects the archived MemAdapter answer and receives a miss with UPB 3. The old ordinary selector had unknown delivery on that task and falls back to RP under the original rule. Restricting all three selectors to jointly available decisions leaves 21 tasks. Both new arms score **18/21**, with OPB **1 versus 4** in favor of witnesses. On the full 24-task cohort, the witness arm leads 21 to 19. The extra full-cohort difference is an author A pet-packing case, excluded from the primary overlap.

The new control helps separate the default indicator from the combined effect of the conflict-focused instruction and restricted switch policy. The Match difference is concentrated in one archived judgment, and Judge interpretation of seafood scope matters. The same-proposal replay shows that all five proposed switches already met the literal checks. Current gains support continued study of when to intervene and how to protect task decisions. They provide no observed score contribution from the exact-span validator. The validator provides provenance only. A later comparison can test local decision repairs using common evidence and protected untouched portions, with no need to repeat global free selection.

The default-aware arm made 24 successful requests with 107,381 reported tokens, no unknown use or retries. Both new arms total **48 requests, 232,866 reported tokens**. Actor and official Judge requests were zero. All archived grades stay in place. These exposed single-source results use the project Qwen detailed single-preference scoring adaptation.

[Control aggregates](DEFAULT_CONTROL_SUMMARY.json) · [Witness aggregates](SUMMARY.json) · [Same-proposal replay](UNCHECKED_SUMMARY.json)
