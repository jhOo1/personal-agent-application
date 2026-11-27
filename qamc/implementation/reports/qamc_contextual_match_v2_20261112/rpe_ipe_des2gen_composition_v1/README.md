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

## Can pre-generation agreement protect the switch?

On history-on tasks, switch to Des2Gen only if its Apply set is a strict subset of the RP B/C set and includes every RP-predicted C. These are predicted policies. Both generators see the original source texts. Check the query, facts, current context, ordered sources and decision IDs against both Actor requests. On 137 assigned history-on tasks, 129 have common grades. The rule switches on 44 of those 129. Within these 44 tasks (267 positions), RP versus Des2Gen Match is 157 versus 154, OPB 68 versus 91, UPB 38 versus 25, FM 13 versus 20. Source-group net Match is positive twice, negative four times and tied 20 times. Combined with the unchanged off and keep branches, the policy gives 946/1472 against 949/1472 for IPE-C. The subset rule was devised after the previous composition result, on the same development material.

On explicit/042 the user wants bedtime audio without scrolling. Des2Gen suppressed three more sources, yet led with explicit attribution to the user's meditation and musical tastes. RP led with the immediate goal of choosing audio before bed. Both recommended meditation and gentle instrumental music. Archived Match moves from 4/6 to 3/6, OPB from 1 to 3. These whole-answer scores do not identify the causal effect of the opening. A smaller Apply set does not establish weaker influence in the final answer. Close this switching rule. [Aggregate](AGREEMENT.json) · [Replay](agreement.py).

### Post-selection author-label audit

On the same 44 switched tasks, align M0 through Mn in the identical Actor source lists with the author labels only after freezing the preceding switch. Of 84 additional Suppress instructions, 83 were author A, one was B, and zero were C. The 107 remaining Apply instructions cover 37 A, 22 B and all 48 C positions. The 76 previously ignored positions comprise 75 A and one B. Thus the rule kept every author C on this particular scored subset. Its loss cannot be explained by newly suppressing author C.

In the 43 tasks where every newly suppressed position was author A, total Match fell by five positions (259 allocated); OPB severity rose by 23, UPB fell by 13 and FM rose by seven. The single remaining task gained two positions. These are whole-answer ratings; the divergence between policy and answer scores does not locate causal responsibility in any single source. Both Actor prompts displayed the original source texts and the prompts themselves differed. No labels enter either Actor or routing. Use agreement.py --audit-labels to reproduce the [aggregate](LABEL_AUDIT.json).
