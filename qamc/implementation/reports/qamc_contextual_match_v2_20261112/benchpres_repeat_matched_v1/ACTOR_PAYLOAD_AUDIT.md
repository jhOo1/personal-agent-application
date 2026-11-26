# BenchPreS frozen Actor payload composition

A read-only audit of the committed preflight allocation found 43 roots with both Actor payloads available. It verified byte-level GEPA template boundaries and identical request hashes across each arm's three draws. The table counts UTF-8 bytes of message contents with each root counted once. It does not count transport framing, model tokens, Selector inference, or Judge costs.

| Component | Strong Gate | Author Selectivity |
|---|---:|---:|
| Static rendered GEPA system text, excluding the entire memory block | 959,760 | — |
| System memory block, including XML/list formatting | 5,257 | — |
| User message | 415,096 | 389,076 |
| Total | 1,380,113 | 389,076 |

Strong Gate's static GEPA text is 22,320 bytes per root. It represents 69.5% of Strong Gate's message content and 96.8% of the byte difference between arms. Strong Gate's user message includes fixed facts (381,549 bytes of serialized values) and ordered source-use guidance (20,258 bytes). The Selectivity arm uses its full assembled author user message and has no separate system message.

This accounts for most of the *payload-size* gap in the frozen requests. The [first-wave ledger](WAVE0_COSTS.md) separately measures actual input and output tokens. The two methods differ in system policy, evidence presentation, and guidance as well as memory control. This comparison cannot assign the observed score difference to a Selector, GEPA policy, or prompt length independently. A later isolation experiment would need to share the Actor policy and vary admission or evidence presentation explicitly.

Reproduce with the private frozen plan and pinned PersistBench author checkout using the [audit script](../../../scripts/audit_qamc_benchpres_repeat_payload.py) and the [study protocol](PROTOCOL.md). Public artifacts contain only aggregate sizes and provenance hashes. [Machine-readable totals](ACTOR_PAYLOAD_AUDIT.json)
