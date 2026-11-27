# Which tasks account for the RPEval Exact trade-off?

Paired offline replay of 274/300 exposed tasks (1,462 scored positions) from ipe_c_two_endpoint_completion_v1/RESULTS.json. Compare the same task-only draft to the deployed IPE-C choice under the archived detailed Judge. Exact here means all positions match. The JSON separately tallies the saved full_match field. Partial includes zero matches. No new generation, grading or sealed data.

| Author stratum | Tasks | Newly exact | Lost exact | Net position Match | Net positions among tasks partial under both |
|---|---:|---:|---:|---:|---:|
| All A |116|2|7|−26|0|
| B present, C absent |48|0|0|+3|+3|
| C present |110|0|3|+102|+107|

Overall, activating historical memory selectively adds 79 matched positions but loses eight exact answers net relative to always withholding history. Within the 110 C-containing tasks, IPE-C and the full RP endpoint each achieve 0/110 exact, compared with task-only 3/110. After excluding tasks with a known flag on any endpoint, the corresponding counts are 0/67, 0/67 and 2/67. Exact counting from Match and the separate saved full_match field agree on the 110 tasks for each method.

Only 11/110 IPE-C tasks in this stratum are one position short; two of those remain in the unflagged subset. This bounds how many currently imperfect C-containing tasks a hypothetical one-position correction per task could make exact, assuming all other positions retain their scores. It does not bound multi-position changes from a single answer edit. The aggregate cannot identify which memory was mishandled or establish failure to implement the C constraint itself. Author strata are used only for retrospective analysis.

The public files contain the replay script and aggregate. Reproduction requires the original private project score archive. The source panel, endpoints, and exposure history are unchanged.
