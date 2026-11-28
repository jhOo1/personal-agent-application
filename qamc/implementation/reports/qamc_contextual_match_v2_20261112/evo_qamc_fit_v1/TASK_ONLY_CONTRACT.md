# Task-first planning input and behavior audit

All 40 planning prompts matched the frozen request hashes. Their payloads contain just the current task, context and facts. They have no original history candidates. All 40 plans returned successfully. The final 40 Actor request bodies match the original task, the entire original ordered history and the exact returned task plan. The final system prompt matches the other planned arms. The first-pass audit confirms the contrast despite the order in which Judge results later become available. [Audit output](TASK_ONLY_CONTRACT.json)

The raw plans also give concrete predictions for the final answers:

- The manager-and-coworkers lunch plan includes service speed as one possible restaurant detail without access to the requester's past lunch habits. A final answer choosing timely service does not by itself demonstrate personalization. Treating it as a group rule explicitly based on the past habit is a clearer behavioral indicator.
- The companion-dog plan puts coat color and appearance in a lower-priority tier after behavioral fit. The two previously scored full-history plans produced final answers with uncertain coat appearance as a disqualifying condition. Check whether the task-first answer preserves the original ordering after the Actor sees history.
- The tax discrepancy plan restricts the output to a complete message for the official recipient. Check whether the answer actually realizes concise expression while maintaining the required resolution request and other document facts. A statement in the plan is not a scored behavior.

Final generation and grading determine whether these differences persist. The paired crossover will then reuse the very same task plans and final prompt with Self-ReCheck's narrower source set.
