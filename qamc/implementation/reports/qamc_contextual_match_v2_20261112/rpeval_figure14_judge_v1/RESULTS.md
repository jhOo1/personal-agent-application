# The RPEval scoring contract changes the ordering on identical answers

RPEval Figure 14 was recovered from the author's arXiv v1 source and verified against the versioned download. The author's public code still points to `0f8bce80`, whose short repository scorer does not request Match. The paper appendix differs: it asks for whole-task Macro, position-level Micro, and includes FB and LF. This test imports its prompt text and adds only a declared convention for representing the original placeholders; it does not authenticate an original provider or unpublished payload.

All 24 responses to the Figure 14 reconstruction used an unquoted fraction, mirroring the printed example. No strict JSON score parsed. A zero-call syntax diagnostic quotes just that fraction without changing a numerator, denominator, severity or boolean. It leaves **15/24 valid, 7 wrong denominators and 2 inconsistent Macro values**. Only six tasks/34 positions have both endpoints valid. IPE-C, full history, and task-only score 15, 15, and 8 on that six-case intersection, while the detailed project adaptation scores 23, 23, and 17. The loss of six paired cases is substantial, including three of the four all-ignore cases.

An alternate request appends an explicit JSON and original-denominator contract without changing the severity definitions. All 24 responses satisfy the contract. That makes the following comparison well-formed but does not establish semantic agreement. Each condition reuses the same answers and exact archived IPE-C routing. The two Judge prompts use the same GPT-4.1 alias and endpoint settings.

| Same 12 tasks, 65 preference positions | Original detailed project Match | Figure 14 with explicit format Match | Original exact tasks | Figure 14 exact tasks |
|---|---:|---:|---:|---:|
| IPE-C | 39/65 | 22/65 | 3/12 | 0/12 |
| RP full history | 35/65 | 24/65 | 2/12 | 0/12 |
| Always task-only | 33/65 | 14/65 | 3/12 | 0/12 |

IPE-C's comparison to RP changes from +4 to -2. On the all-ignore stratum, the two new endpoint routes and IPE-C all receive **0/21** in the Figure 14 format control. The recorded no-history responses get UPB severity 5 on all four all-ignore tasks, even though the author labels require none of the histories. The detailed adaptation also exhibits judge anomalies, so this comparison cannot establish either judge as ground truth. The stable comparison is the observed sensitivity of method ranking on these frozen responses. The errors are consistent with the figure prose describing underpersonalization in general terms rather than expressly restricting it to cases where customization is appropriate.

Forty-eight physical grading requests succeeded, 24 per prompt, with 79,304 reported tokens, no unknown usage or retries. No generators were run, and no saved result was overwritten. The original strict, offline syntax-only, and explicit-contract tables remain separate. No independent or officially matched leaderboard position can be inferred from these development cases.

The [frozen reconstruction](PROTOCOL.md) gives the TeX retrieval command. After obtaining the same asset, run `normalize.py` locally for the syntax diagnostic and `format_control.py replay` for the scored contract variant. [Strict](RAW_AGGREGATE.json) · [Syntax-only](SYNTAX_DIAGNOSTIC.json) · [Explicit format](FORMAT_CONTROL.json) · [Author Figure 14](https://arxiv.org/html/2601.16621v1)
