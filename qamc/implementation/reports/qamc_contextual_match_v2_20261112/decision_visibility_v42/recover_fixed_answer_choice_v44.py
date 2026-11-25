"""Recover local queue reservations proved to predate the durable network receipt."""
from collections import Counter
import json
import sqlite3

from proposals.qamc_protocol_alignment.sampling import sampling_key
from qamc.common import sha

import run_fixed_answer_choice_v44 as run


def reconcile():
    plan, manifest, _ = run.artifacts()
    runtime = run.RUN / run.STAGE
    journal = runtime / "samples.sqlite"
    keys = {sampling_key(job["unit"]): sha(job["request"]) for job in manifest["units"]}
    before = run.OUT / "WORKER.pid"
    old_pid = int(before.read_text())
    import os
    try:
        os.kill(old_pid, 0)
    except ProcessLookupError:
        pass
    else:
        raise RuntimeError("Previous launcher still exists")
    target = run.OUT / "INITIAL_LAUNCH_RECOVERY.json"
    if target.exists():
        raise ValueError("Recovery is one-time")
    with sqlite3.connect(journal) as db:
        db.execute("BEGIN IMMEDIATE")
        queue = db.execute("SELECT unit_key,request_sha,status FROM samples ORDER BY unit_key").fetchall()
        for key, digest, status in queue:
            if keys.get(key) != digest or status != "STARTED_DELIVERY_UNKNOWN":
                raise ValueError("Initial recovery only covers matching unsettled reservations")
        retained, releasable = [], []
        for key, digest, status in queue:
            folder = runtime / "visible" / key
            info = {"sampling_key": key, "request_sha256": digest, "old_journal_status": status}
            if folder.exists():
                record = run.read(folder / "record.json")
                if record["status"] != "PENDING_DELIVERY_UNKNOWN" or record["request_sha256"] != digest:
                    raise ValueError("Unexpected network receipt")
                retained.append(info)
            else:
                releasable.append(info)
        if len(retained) != 1 or len(releasable) != 7 or not plan["choice_request_cap"] > len(queue):
            raise ValueError("Initial interruption differs from the observed orphaned process")
        unlock = {"old_pid": old_pid, "worker_alive": False, "released_local_reservations": releasable,
                  "retained_physical_delivery_unknown": retained, "transport_retries": 0,
                  "invariant": "No transport is reached until the unit directory and pending physical record are durable."}
        with sqlite3.connect(runtime / "initial_launch_samples_backup.sqlite") as backup:
            # A separate read-only connection can copy the pre-change journal.
            with sqlite3.connect(f"file:{journal}?mode=ro", uri=True) as original:
                original.backup(backup)
        run.probe.freeze(target, unlock)
        db.executemany("DELETE FROM samples WHERE unit_key=? AND status='STARTED_DELIVERY_UNKNOWN'",
                       [(r["sampling_key"],) for r in releasable])
        db.commit()
    print(json.dumps({"released": len(releasable), "preserved_unknown": len(retained)}))


if __name__ == "__main__":
    with run.probe.runner_lock(run.RUN / "runner.lock"):
        reconcile()
