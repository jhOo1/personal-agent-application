# Fixed RPEval endpoints: blind-evaluation preflight and retained gateway failures

Neither evaluator yielded a valid assessment. There is no new behavioral ranking and the original RPEval grades remain the primary evidence. The 22 prepared pairs came from 22 conservative source groups within the existing 274-task common development set. They cover four ON and four OFF all-A tasks, four ON and four OFF B-only tasks, four ON and two OFF C-bearing tasks. Both endpoint hashes and the selected IPE-C answer hash matched the archived grades. The anonymous requests expose only the task, fixed facts, original memories and two randomly ordered answers. Code verified the request shape and rejection of unsupported answer citations. No new answers were generated.

| Frozen evaluator alias | Allocated | Dispatched | Valid | Delivery unknown | Undispatched | Unknown usage |
|---|---:|---:|---:|---:|---:|---:|
| GPT-6.1-sol | 22 | 2 | 0 | 2 | 20 | 2 |
| DeepSeek V4.1 Flash | 22 | 2 | 0 | 2 | 20 | 2 |

Both GPT-6.1-sol receipts had HTTP 200, a stream terminator and the expected alias, but the final reason was still `in_progress`. After the prior one-minute cooldown and a second occurrence, the stop marker prevented further dispatch. Both DeepSeek receipts had HTTP 200 and a stream terminator, but contained an `api_error` and no verified model alias or final answer. This independent transport batch also stopped after the second occurrence. The alternate manifest and code hashes were frozen on disk before dispatch. A transient Git index lock delayed committing the alternate code until after its first request. The request payload remained the frozen one. Neither route's unknown deliveries were resent. Reported token usage was unavailable in all four receipts. Human reviews, new native scores and new Actor requests all remain zero.

The balanced diagnostic subset has 118 author positions. Its old project-adapted Match is IPE-C 60, Always-Task 64 and RP reconstruction 72. It deliberately assigns coverage to uncommon route/label combinations without selecting on score value. The subset reverses the ranking from the 274-task panel and cannot substitute for it. Future behavioral judgments on this subset should be interpreted as stress cases within the route strata. No sealed data were opened.

[Protocol](PROTOCOL.md) · [Blind runner](blind_endpoints.py) · [Alternate evaluator](deepseek_sensitivity.py) · [Existing common-panel results](../native_residual_v1/COMMON_COMPARISON_CLOSURE.md)

The source task archives and shared runner are available in the original research worktree. Frozen anonymous requests, model receipts and execution state stay under the private `runs/qamc_contextual_match_v2_20261112/ipe_endpoint_behavior_{blind,deepseek}_v1` directories. A verified working evaluator can resume undispatched jobs with their exact manifests. The two stop markers and all four failure records are retained.
