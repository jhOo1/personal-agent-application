# Hosted DeepSeek did not qualify for the proposed nonthinking comparison

Both synthetic requests used the same prompt, requested alias, expected answer (419), cap and temperature. The gateway returned a correct visible answer, successful stop and matching alias for both.

| Requested mode | Reported reasoning tokens | Reasoning field present | Total tokens |
|---|---:|---|---:|
| disabled | 23 | yes | 72 |
| enabled | 24 | yes | 73 |

The disabled request produced positive evidence of reasoning under this gateway configuration. The proposed 29-root nonthinking MemAdapter versus SELECTED_GEPA comparison was not launched. This result is specific to the tested alias, gateway and request format. It places no limit on other providers or interfaces. Physical requests 2, reported tokens 145, no transport errors or retries. No benchmark inputs were used; only usage and field presence were retained. This supplies no new external-baseline scores.
