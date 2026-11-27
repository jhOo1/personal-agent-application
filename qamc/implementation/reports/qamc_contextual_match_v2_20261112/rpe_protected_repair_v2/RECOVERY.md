# Protected repair recovery

The public archive includes the locator and repair prompts, deterministic executor, unit tests, runner source and frozen hashes. The executor tests can run using Python's standard library from the folder holding the test.

```bash
python3 -B -m unittest discover -v -p test_protected.py
```

Run the full trial from the restored private QAMC research checkout. It uses the original project Python environment and its shared API transport. Restore the private task, full candidate and visible receipt artifacts from the previous single-preference bridge, reward comparison and conflict-witness study. Restore the pinned detailed RPEval scorer source and its references. The runner also imports the shared journal and historical receipt scanner from the original checkout. Examples are `proposals/qamc_protocol_alignment/sampling.py`, `src/qamc/pa/rpeval_scoring.py` and `reports/qamc_contextual_match_v2_20261112/persist_frozen_utility_review_v1/extend.py`. Those direct runtime sources and the private input inventories are required for end-to-end recovery. The public archive's [migration guide](../../../../MIGRATION.md) describes how to restore the private checkout.

```bash
trial=reports/qamc_contextual_match_v2_20261112/rpe_protected_repair_v2
bash "$trial/run.sh" report
```

The report action reconstructs input and archived grade bindings and reads settled receipts without dispatching model requests. If an authorized trial was interrupted, check the actual process and journal before resuming. For a terminal process with incomplete work, run the same frozen command with `run` after restoring the original service identity and ledger. The journal keeps durable started and terminal attempt states. Delivery-unknown requests remain recorded under the frozen policy. Do not remove a lock or start a parallel copy merely because a status read timed out.

In the original checkout, the private settlement directory is `runs/qamc_contextual_match_v2_20261112/rpe_protected_repair_v2`. It holds `FROZEN.json`, stage manifests, private answer locks, score bindings and the request ledger. `FROZEN_DESIGN.json` in the public folder contains only hashes and caps. The private run directory is necessary to replay or continue this exact run.
