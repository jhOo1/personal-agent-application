# BenchPreS halfway comparison using valid individual grades

The primary replay compares draws with all six scores valid. This separate diagnostic reconstructs every Judge request from its exact saved Actor answer, original task and evaluation inputs. It applies the frozen per-field rules to each successful receipt, even if another field prevented the aggregate grade from parsing. The original grades remain unchanged. [Primary result](WAVES012_READOUT.md) · [Replay script](trace_partial_grades.py) · [Diagnostic counts](WAVES012_FIELDWISE.json)

On the three settled waves, one Gate draw has five valid attribute grades and invalid completeness. One Selectivity draw has four valid attribute grades and valid completeness. The unsuccessful Gate Actor stream and the three draws without a historical Gate wire still lack scores.

| Metric | Common field positions | Strong Gate | Selectivity | Full-allocation Gate minus Selectivity bounds |
| --- | ---: | ---: | ---: | ---: |
| MR | 221 | 1 | 26 | −11.54 to −5.98 percentage points |
| AAR | 118 | 101 | 83 | +10.32 to +16.67 percentage points |
| Bold AAR | 42 | 41 | 26 | +35.71 percentage points |
| Non-bold AAR | 76 | 60 | 57 | −2.38 to +7.14 percentage points |
| Completeness | 67 | 320 | 315 | −0.19 to +0.08 points out of 5 |

Full-allocation bounds cover all three draws for the 24 settled-wave tasks. Missing fields vary over their allowed score ranges, including opposite assignments for the two arms. These are deterministic bounds on the frozen Qwen scores, separate from the profile bootstrap and the full six-wave roster. They show that the early MR and overall AAR advantages survive missingness. The non-bold and completeness differences can change direction. All bold AAR fields are observed, including on draws with invalid aggregate scores. This narrows the paper claim to the formality and formatting behaviors supported by the current comparison.

No new model requests, regrades or imputations were made. Wave four continues under the original protocol.
