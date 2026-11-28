# Qualify the inference mode before a same-Actor PersistBench comparison

The proposed external comparison would use a hosted DeepSeek alias on both sides. MemAdapter's released local configuration disables thinking. First test whether the gateway exposes the requested mode on one synthetic request per setting. No benchmark data, external method implementation or Judge is involved.

Use the same arithmetic instruction, visible answer, model alias, output cap and temperature; toggle only the DeepSeek chat API's top-level thinking.type (disabled versus enabled). Request and response identity, time, usage and presence of a reasoning field may be inspected. Store no reasoning text or authentication fields. Keep every first receipt, including HTTP and incomplete responses. A positive result requires both successful, correct visible responses, the requested alias and stopped completions; an explicit zero reasoning-token count and no emitted reasoning for disabled, plus positive reasoning tokens or a nonempty reasoning field for enabled. Without positive evidence, cancel this proposed nonthinking external comparison on this route. Even a pass only qualifies the observed gateway behavior: a hosted alias is not a reproduction of the authors' local checkpoint. The two probes cannot establish Benchmark performance.

[API setting](https://api-docs.deepseek.com/guides/thinking_mode/)
