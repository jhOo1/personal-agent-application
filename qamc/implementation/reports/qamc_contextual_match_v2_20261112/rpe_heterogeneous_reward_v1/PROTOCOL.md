# RPEval single source blind selection

Freeze the prior 24 exposed single-source development tasks and the exact RP-Reasoner, Des2Gen and MemAdapter answers. The primary historical overlap has 22 tasks. All 24 enter blind selection, with full-roster and strict-success sensitivity reported. Source, current task, context and facts are fixed. Candidate order is deterministic per task and anonymized. Candidate methods are local reconstructions or adaptations as recorded in the parent experiment.

Compare the pinned InternLM2-7B-Reward release using its author chat template and reward head, and one direct Qwen3.8-flash comparison. Both read the same raw task information and same candidate texts. Reward inference sees one candidate at a time, while Qwen compares all three. No new Actor or Judge. Generation and review compute are not matched across mechanisms. Three independently generated candidates are necessary at cold start and the original method costs must be disclosed separately. Current replay uses exact saved answers.

A missing choice, invalid envelope or tied reward panel explicitly falls back to RP. Keep the original failure and report new strict success as well. Choice files are locked before importing old score payloads into the settlement. The scoring protocol is the historical detailed Qwen single-preference rubric, not a new judge or a verified author leaderboard replication.

Advance only if the primary overlap reaches at least 19/22, improves on the best fixed external method, and has genuine behavior gains across at least two sources without new all-A misuse or material lost constraints. Report OPB, UPB and FM separately. If the direct comparator is at least as good or recovers the same gains, an independent reward-model advantage is unproven. Case inspection cannot change the selected answer or grade.

- [Author reward model and implementation](https://huggingface.co/internlm/internlm2-7b-reward/tree/853c9e6e0f71862785dd0b8eefca9609f8e720cb)
- [Personalized RewardBench](https://arxiv.org/abs/2604.07343)
