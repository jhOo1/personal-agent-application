# Frozen task-level exposure decisions

The ordinary Gate completed before any comparison endpoint was newly generated or scored. Checked every saved decision against its frozen request hash. The subsequent three batches use those decisions unchanged.

| Assigned | OFF | SELECTED | FULL | Gate delivery unknown | Invalid Gate response | No compatible Scope Actor |
|---|---:|---:|---:|---:|---:|---:|
| RPEval, 126 | 41 | 83 | 0 | 1 | 0 | 1 |
| BenchPreS, 4 | 4 | 0 | 0 | 0 | 0 | 0 |
| PersistBench, 32 | 10 | 19 | 1 | 0 | 1 | 1 |
| Total, 162 | 55 | 102 | 1 | 1 | 1 | 2 |

The controller chose OFF for every formal-writing task in the one-profile BenchPreS subset. This is an observable prior decision, not a scored loss. It makes the protection comparison with the literal OFF and SELECTED endpoints especially informative. The only FULL decision is in PersistBench. The full-history control remains assigned to all eligible tasks regardless of that decision frequency.

Gate cost was 160 physical requests and 488,233 reported tokens. One unknown delivery had no reported usage. There were no automatic retries. One successful transport failed the Gate response contract. The two resulting missing decisions have no fallback and will not be counted as a wrong answer. [Frozen generation and scoring protocol](EXPOSURE_CONTROLS_PROTOCOL.md)
