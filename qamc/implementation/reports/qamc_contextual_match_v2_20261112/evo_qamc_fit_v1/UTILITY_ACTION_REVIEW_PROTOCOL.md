# Task-first review of archived strict beneficial-use answers

Strict beneficial-use ratings from the frozen GPT-4.1 and Qwen adaptations disagreed on the same SELECTED and FULL answers. The fresh deployment contains 18 already exposed source groups and 36 stored answers. All groups enter this review regardless of their old rating. The exact inputs to both methods, generated answers, scores and private disclosure boundaries remain fixed. [Prior comparison](../persist_utility_fresh_deployment_v1/RESULTS.md)

## Review protocol

1. For each anonymous case, send the original Query and verbatim archived history to GPT-6.1-sol. There are no answers, method names, existing grades, author labels or evaluation rationales in this request. Ask for three behaviors that can be verified in an answer: a required action, a history-supported practical benefit, and a distinct delivery safeguard. A criterion must cite an exact span from its declared source. An inapplicable axis may be null.
2. Lock the entire successful criterion set before submitting the second phase. For each eligible case, send the exact Query, the frozen criteria, and two archived answers under their existing anonymous IDs to a new stateless request. Supply no additional history, archived ratings, arm labels or reviewer conclusions. Decide what each answer actually does. Mark a contradictory action, an omission and a mention without implementation separately.
3. Unblind only for offline reporting. Check each answer digest against the private key. Report paired outcomes with separate denominators for structural failures, unknown judgments and inapplicable axes. A strict historical benefit requires a concrete action or result. A sentence that merely acknowledges a constraint cannot count.

Both phases use the same GPT-6.1-sol gateway alias, which is independent of the two original grading configurations. This is a model review rather than human annotation. The two phases share the model alias, so their errors may be correlated. There is no new generation or benchmark grading. No sealed data is read. The original scores retain their role and are never overwritten.

## Interpretation

If FULL uniquely performs the missing action and the source is absent from SELECTED's real Actor message, prioritize coverage for that type of task. If both receive the source but omit the action, prioritize execution with the same evidence. If the answers perform the same action and the grades differ, the paired case cannot justify an optimization aimed solely at the score. Select a mechanism only after finding a repeated observable failure across independent development source groups. The review does not itself establish a performance gain or qualification for the authors' protocol.

## Recovery and replay

From the original checkout with the archived packet, run:

```bash
export PYTHONPATH=src:.:scripts:reports/qamc_contextual_match_v2_20261112/all_a_visibility_score_probe_v1
export PYTHONDONTWRITEBYTECODE=1
../qamc/.venv/bin/python reports/qamc_contextual_match_v2_20261112/evo_qamc_fit_v1/utility_action_review.py freeze
../qamc/.venv/bin/python reports/qamc_contextual_match_v2_20261112/evo_qamc_fit_v1/utility_action_review.py run
../qamc/.venv/bin/python reports/qamc_contextual_match_v2_20261112/evo_qamc_fit_v1/utility_action_review.py report
```

The command requires the original checkout and the existing private packet and gateway configuration. The existing minimal streaming transport writes and validates each request before proceeding. It uses at least 3.2 seconds between dispatches, a one-minute service cooldown and at most 36 calls. Existing receipts, including unknown deliveries, are never sent again. A new command with the original code resumes only undispatched work. Reporting replays the receipts and does not call a model. Only the prompts, implementation and aggregate findings are eligible for public archiving.
