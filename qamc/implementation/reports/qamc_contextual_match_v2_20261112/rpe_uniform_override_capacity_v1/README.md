# How much can a task-only override repair in an already selective system?

Archived RPEval V41, 233 exposed tasks, 48 distinct serialized task-only requests. The unchanged fallback on each row is IPE-C, so it can already behave differently for different histories of the same request. An oracle chooses KEEP, force TASK_ONLY or force FULL for each block. Every affected row must retain or improve its archived Match and all five severity scores (OPB, UPB, FM, RII, VG). Maximize additional exact tasks, then matched positions, then minimize changed answers. Exact means all Match positions correct. Evaluation labels and scores are used only to set a retrospective ceiling. No new calls.

| Identical complete blocks, identical task denominators | Baseline exact / matched positions (counts) | Per-history oracle gain, exact / positions | Uniform override gain, exact / positions |
|---|---:|---:|---:|
| 41 blocks, 190 tasks | 73 / 685 | +12 / +45 | +2 / +7 |
| 17 blocks consistently free of known flags, 71 tasks | 39 / 299 | +5 / +24 | 0 / 0 |

216/233 tasks have all three Match scores. We keep incumbent answers in blocks containing even one missing grade; for the sensitivity analysis a known flag also closes the entire block. The main comparison above removes closed blocks from BOTH oracles. When allowing all 216 individually valid tasks, per-history gain becomes +13 / +49 and the blockwise gain stays +2 / +7. Three answers change across the two improving complete blocks. File hashes identify exact serialized task-only requests, not statistical independence.

This bounds a specific follow-up change to IPE-C: overriding its decision with the same fixed endpoint across a task's observed history variants. These constraints are stricter than aggregate non-regression. On the identical flag-free blocks, different decisions for different histories could recover five perfect scores, while a uniform override cannot recover one. Per-history selection here reads outcomes and is not deployable. Even a perfect override over the two endpoints cannot synthesize missing behavior. These development counts do not prove incompatibility of benchmarks or that generating a new draft will outperform the strong paths.

Reproduction: python3 replay.py in the original research repository. Inputs are ipe_c_two_endpoint_completion_v1/RESULTS.json (saved scores) and counterfactual_rpeval_v41/FROZEN.json (exposed UID, source group and task request hash). Public output contains only aggregates.
