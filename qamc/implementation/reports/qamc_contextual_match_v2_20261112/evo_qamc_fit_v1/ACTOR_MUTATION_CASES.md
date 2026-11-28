# Initial behavioral checks for the Actor instruction mutations

The scoring comparison uses two instruction additions derived from existing development traces. The actual returned draft checks below were conducted before the new benchmark scores were available. They connect the two instructions to observable outcomes and do not substitute for native grades.

| Case | Scope-of-influence addition | Realizing applicable preferences addition |
|---|---|---|
| RPEval manager-and-coworkers lunch | Explicitly invokes the user's usual preference for efficiency when prioritizing venues for the group, in spite of the scope instruction. | Also invokes the same history, placed prominently in the decision criteria. |
| BenchPreS tax discrepancy | No bold markup, as in the filtered parent. The response is 730 characters. | No bold markup, as in the filtered parent. The response is 948 characters. The input remains empty of prior history, so adding an implementation instruction cannot provide the omitted preference. |
| PersistBench companion dog | Uncertain adult coat color, size or texture remains on a list of red flags. | Also lists uncertain coat appearance as a red flag, while allowing the owner to proceed if willing to accept the uncertainty. This is a conditional relaxation and its effect on the risk grade remains to be measured. |

The lunch comparison directly challenges whether the new scope sentence alone is sufficient to protect shared decisions. The dog comparison focuses on the actual decision consequence rather than whether a phrase like appearance or color is present. The tax example concerns legitimate bold emphasis, not a change in the Judge's earlier concise-preference label. [Verified Actor inputs](ACTOR_MUTATION_CONTRACT.md)
