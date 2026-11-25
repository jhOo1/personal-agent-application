"""Recheck the four observed headroom cases without exposing native scores or labels."""
from argparse import ArgumentParser
import json
from pathlib import Path
from unittest.mock import patch

from qamc.common import canonical, sha

from blind_main_recall import PROMPT, validate as validate_use
from blind_optional_effect import MODEL
import run_task_conditioned_value as run


OUT = run.OUT / "blind_headroom"
RUN = run.RUN / OUT.name
probe, read = run.probe, run.read
GENERIC, RP = run.method.GENERIC, run.parent.ARCHIVED[-1]
CASES = ("explicit/070", "implicit/070", "explicit/073", "implicit/147")
MIRRORED = {"implicit/070", "implicit/147"}
CAP = 6
INSTRUCTION = PROMPT + """
Also add a top-level "completion" object keyed by both answer IDs. For each answer
give {"status":"COMPLETE|MATERIAL_GAP|UNCERTAIN","quote":"a short exact excerpt or empty"}.
Judge delivery against the current task, not answer length. Do not treat unverifiable real-world
claims as confirmed. Do not rank the answers or combine the judgments into a score."""


def prepare():
    spec, _, roots, _, _, _ = run.prepare("pilot")
    source = run.OUT / "contract_recovery"
    if read(source / "RUN_STATE.json")["state"] != "COMPLETE":
        raise ValueError("The repaired comparison must be settled")
    settled = read(source / "SETTLED.json")
    jobs = {}
    for index, suffix in enumerate(CASES):
        row, = [r for r in settled["rows"] if r["uid"].endswith("/" + suffix)]
        uid = row["uid"]
        root = roots[uid]
        sources = root["original_sources"]
        archived = root["archived"][RP]
        answers = {GENERIC: row["outputs"][GENERIC], RP: archived["answer"]}
        if row["native"][RP]["fields"] != archived["fields"]:
            raise ValueError("Archived answer and native fields are no longer paired")
        order = (GENERIC, RP) if index % 2 == 0 else (RP, GENERIC)
        for repeat in range(1 + (suffix in MIRRORED)):
            arms = dict(zip(("V1", "V2"), order[::1 - 2 * repeat], strict=True))
            public = {"task": root["public_task"], "focal_sources": sources,
                      "answers": {key: answers[arm] for key, arm in arms.items()}}
            wire = {"model": MODEL, "stream": True, "messages": [
                {"role": "system", "content": INSTRUCTION}, {"role": "user", "content": canonical(public)}]}
            key = sha([OUT.name, uid, repeat])
            jobs[key] = {"uid": uid, "group": row["group"], "repeat": repeat, "arms": arms, "wire": wire,
                         "wire_sha256": sha(wire),
                         "labels": dict(zip((s["memory_id"] for s in sources), row["labels"], strict=True))}
    if len(jobs) != CAP or len({j["wire_sha256"] for j in jobs.values()}) != CAP:
        raise ValueError("Unexpected blind request identities")
    return {"jobs": jobs, "cap": CAP, "native_scores_modified": 0,
            "automatic_retries": 0, "service_reference_sha256": spec["service_reference_sha256"],
            "settlement_sha256": sha(settled), "implementation_sha256": sha(Path(__file__).read_bytes())}


def validate(value, wire):
    if set(value) != {"answers", "completion"}:
        raise ValueError("Expected source and completion assessments")
    validate_use({"answers": value["answers"]}, wire)
    answers = json.loads(wire["messages"][1]["content"])["answers"]
    if value["completion"].keys() != answers.keys():
        raise ValueError("Missing completion assessment")
    for key, cell in value["completion"].items():
        if (set(cell) != {"status", "quote"} or cell["status"] not in {"COMPLETE", "MATERIAL_GAP", "UNCERTAIN"}
                or not isinstance(cell["quote"], str) or cell["quote"] not in answers[key]):
            raise ValueError("Invalid completion assessment")


def report(plan):
    rows = []
    for key, job in plan["jobs"].items():
        folder = RUN / "Blind" / sha(key)
        path = folder / "record.json"
        record = read(path) if path.exists() else None
        vote = None
        if record:
            if record["request_sha256"] != job["wire_sha256"]:
                raise ValueError("Blind receipt differs from the frozen packet")
            if record["status"] == "OK":
                recorded = read(folder / "vote.json")
                validate(recorded, job["wire"])
                vote = {section: {job["arms"][k]: v for k, v in cells.items()} for section, cells in recorded.items()}
        rows.append({k: v for k, v in job.items() if k != "wire"} | {"receipt": record, "vote": vote})
    return {"rows": rows, "assigned": CAP, "valid": sum(r["vote"] is not None for r in rows),
            "native_scores_modified": 0, "evidence_type": "targeted blind AI diagnostic"}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "report"))
    args = parser.parse_args()
    plan = prepare()
    path = OUT / "FROZEN.json"
    with probe.runner_lock(RUN / "runner.lock"):
        if args.action == "freeze":
            probe.freeze(path, plan)
        else:
            if read(path) != plan:
                raise ValueError("Blind audit changed after freezing")
            if args.action == "run":
                with (patch.object(probe, "OUT", OUT), patch.object(probe, "RUN", RUN),
                      patch.object(probe, "CAP", {"Blind": CAP}), patch.object(probe, "validate_blind", validate),
                      patch.object(probe, "answer_grid", lambda roots: {r["uid"]: {"ready": True} for r in roots}),
                      patch.object(probe, "blind_wire", lambda root, _: plan["jobs"][root["uid"]]["wire"])):
                    probe.blind({"roots": [{"uid": key} for key in plan["jobs"]],
                                 "service_reference_sha256": plan["service_reference_sha256"]})
            results = report(plan)
            if args.action == "run":
                if all(r["receipt"] is not None and r["receipt"]["status"] != "PENDING_DELIVERY_UNKNOWN"
                       for r in results["rows"]):
                    probe.freeze(OUT / "RESULTS.json", results)
            else:
                if read(OUT / "RESULTS.json") != results:
                    raise ValueError("Stored blind audit differs from replay")
            print(json.dumps({"assigned": CAP, "valid": results["valid"],
                              "physical_requests": sum(r["receipt"] is not None for r in results["rows"])}))
