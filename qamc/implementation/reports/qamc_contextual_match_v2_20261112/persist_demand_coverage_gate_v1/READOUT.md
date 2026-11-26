# Demand-conditioned MemGate stops at evidence qualification

The frozen experiment failed the entrance rule for end-to-end generation. On 13 valid need proposals, both maximum-score ranking U and set coverage C returned exactly the same ordered history as original MemGate on all 13 tasks. No required source set was recovered on the two observable failure probes. The remaining failure probe (special dinner) had a stream error with unknown delivery. Its behavior remains unknown. No Actor or Judge was dispatched.

| Development probe | Required sources exposed by original / U / C | Finding |
|---|---:|---|
| Pet food | 0 / 0 / 0 of 1 | The generated questions ask about both identity and diet. With the original task attached, the best new score for the missing source is 0.0165, below 0.07. |
| Book club | 0 / 0 / 0 of 2 | Neither required source cleared the threshold, despite explicit open questions about diet and hosting. |
| Special dinner | Missing | No demand matrix due to a stream error. The earlier hand-authored diagnostic does not supply its frozen output. |
| Project template and kickoff email | No re-exposure on either | Both preserve exactly the originally selected sets. |

The locally calculated scores did change on every valid task, so this is not a stale-matrix error. Fixed-cardinality selection did not turn those changes into a different evidence set. Under the frozen request construction the coverage solver had no end-to-end exposure contrast to test.

A post-hoc zero-cloud diagnostic reused the actual 13 saved need strings as standalone scoring queries, without rewriting them. It holds K and the original-query matrix row fixed. Four C sets changed. Both C and U recover the pet source (standalone peak 0.2931); neither completely recovers the book-club sources nor reintroduces either tracked project risk. The book-club diet source crosses the threshold but still loses fixed-budget competition, and the allergy source remains below threshold. This isolates a plausible score-composition effect but yields only one complete recovery and no C-vs-U advantage. It does not reverse the stop decision.

14 new Qwen need requests, 13 valid, one delivery and usage unknown, 7,353 reported tokens, no resends. All proposals with usable JSON had four needs. No changes to native scores, past controls or sealed inputs. Deterministic selection passed synthetic checks for complementarity, empty gating, stable ties, retaining all when K equals input size, and rejecting nonfinite scores. Code, prompt and evaluation-layer criteria were frozen before dispatch. Exact generated needs, matrices, original request and callbacks remain in the private `runs/qamc_contextual_match_v2_20261112/persist_demand_coverage_gate_v1` namespace. [Protocol](PROTOCOL.md) · [Aggregate](SUMMARY.json) · [Predecessor signal diagnostic](../persist_memgate_matched_actor_v1/NEED_SCORE_SCREEN.md)
