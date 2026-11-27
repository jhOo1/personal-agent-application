# Fixed-response reflection follow-up

The model diagnostic froze 14 paired tasks from the already scored development answers. It attempted four GPT-6.1-sol requests and retained all four records. One returned an in-band error. The original parser also rejected one completed stream for its unfamiliar finish reason. A versioned parser accepted that finish-reason form on new requests, but both subsequently issued streams ended with `in_progress`. Their safe visible text was retained, including one JSON reply. Neither had accepted completion evidence. There are zero accepted votes, zero human judgments, four requests with unreported usage, and 24 slots never dispatched. The runner settled after the frozen two-failure condition. No request was retried. [Frozen protocol and parser change](REFLECTION_MODEL_PROTOCOL.md) · [Aggregate](REFLECTION_MODEL_SETTLED.json)

## What can be verified from the answers already delivered

The fixed-response inventory permits comparison of all 115 paired Actor draws without requiring an aggregate Qwen grade. A case-sensitive whole-word search tests whether the author-designated inappropriate nickname occurs anywhere in the exact answer. The inappropriate designation comes from the author reference. The text search is only an occurrence check.

| Available paired answers | Paired nickname attributes | Strong Gate occurrences | Author Selectivity occurrences |
| --- | ---: | ---: | ---: |
| Both original aggregate scores valid | 106 | 0 | 39 |
| Both answers available, at least one aggregate score missing | 9 | 0 | 5 |
| All paired answers | 115 | 0 | 44 |

The nine additional pairs extend the directly observable nickname finding beyond the original strict score intersection. This does not recover missing answers, replace the original MR scores, or determine any effect on non-nickname and non-bold semantic attributes. The text replay used no model requests. No new Actor responses or sealed cases were used. [Occurrence counts](REFLECTION_LITERAL.json) · [Replay](trace_reflection_literal.py) · [Independent-review inventory](REFLECTION_VALIDATION.md)
