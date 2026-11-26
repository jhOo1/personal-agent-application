# BenchPreS repeat comparison across profiles and draws

The first two frozen waves yield 42 common scored task–draw pairs across 15 exposed tasks. This audit asks whether the aggregate gaps depend on one profile or one of the three Actor draws. Profile identifiers remain private. The overall and per-draw counts reconcile to the original scores under the common Qwen adaptation. [Paired readout](WAVES01_READOUT.md) · [Exact aggregate replay](WAVES01_PROFILE_TRACE.json)

| Metric | Profiles favoring Strong Gate / Selectivity / tying | Gate minus Selectivity after dropping any one profile |
| --- | ---: | ---: |
| MR, lower is better | 7 / 0 / 3 | −10.71 to −7.14 percentage points |
| AAR | 5 / 0 / 5 | +9.86 to +16.95 percentage points |
| Non-bold AAR | 0 / 0 / 7 | 0.00 percentage points |
| Completeness | 4 / 2 / 4 | +0.05 to +0.14 points out of 5 |

Gate has four fewer misuse labels at each of the three draw indices. Its higher overall AAR also appears at each index. Non-bold AAR instead moves by −1, +1, and 0 positions. All seven profiles with measured non-bold attributes tie when their available draws are combined. The overall tie therefore holds at every measured profile, even though individual answers and Judge labels vary. [Actual source delivery](WAVES01_DELIVERY_TRACE.md) · [Misuse categories](WAVES01_MISUSE_TRACE.md)

Dropping one profile is a sensitivity check on observed complete pairs. It does not estimate new-profile performance, replace fixed-allocation missing bounds, or address the use of an adapted Judge. The results provide no early evidence of a general benefit for non-bold realization. The third wave still runs under its original protocol. Zero new model requests.
