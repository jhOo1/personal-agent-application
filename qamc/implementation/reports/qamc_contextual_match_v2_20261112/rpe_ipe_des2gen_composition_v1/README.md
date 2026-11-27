# Substituting full Des2Gen on IPE-C history-on requests

Development replay. The frozen IPE-C gate decides before generation. On history-off, reuse its unchanged task-only answer. On history-on, use the complete archived Des2Gen pipeline (including its own per-memory decisions) instead of the RP answer. No author label, score, or UID enters the routing decision. The comparison uses the adapted detailed RPEval judge already saved with these answers. No new generation, training, or evaluation calls. The history-on pipeline would pay for both the IPE estimate and the Des2Gen path in a cold deployment; archived replay does not test that latency.

| Same 274 tasks, 1472 positions | IPE-C | Always Des2Gen | Composed |
|---|---:|---:|---:|
| Position Match |949|704|942|
| Exact tasks |92|32|91|
| OPB severity |255|578|304|
| UPB severity |254|149|216|
| FM severity |52|121|75|

26/300 allocated tasks outside the shared scored comparison. This intersection differs from the 274-task, 1462-position IPE-C versus full/empty endpoints table. Among 129 history-on tasks the replacement trades less underuse for more overuse. It adds two matches on the C-containing stratum but loses five on B-without-C and four on all-A. Composed vs IPE-C had positive net Match in four source groups, negative in 12, zero in 29. Task counts and source groups refer to previously exposed development data. Stratum scores are whole-answer position totals, not direct measures of whether individual C constraints were obeyed.

Retain the original IPE-C endpoint. The gain against standalone Des2Gen primarily comes from the off branch; substituting Des2Gen does not improve the incumbent on the common panel. This rejects this specific combination and leaves the independent confirmation question open.
