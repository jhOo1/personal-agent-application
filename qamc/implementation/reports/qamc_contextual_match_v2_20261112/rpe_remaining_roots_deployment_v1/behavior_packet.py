"""Private, arm-masked copies of the three grade-blind action probes."""
import hashlib
import json
from pathlib import Path

here = Path(__file__).resolve().parent
out = here.parents[2] / "runs" / here.parent.name / here.name
panel = json.loads((out / "PANEL_V2.json").read_text())
targets = {next(u for u, _, t in panel["cards"] if t == s) for s in ("all_A", "B_only", "contains_C")}
responses, mapping = [], {}
for deployment in (1, 2):
    stage = out / f"deployment{deployment}" / "Actor"
    if not (out / f"deployment{deployment}" / "RESULTS.json").exists():
        raise SystemExit("Wait for settlement")
    for p in sorted(stage.glob("visible/*/record.json")):
        record = json.loads(p.read_text())
        uid = record["unit"]["root_id"]
        if uid not in targets or record["status"] != "OK":
            continue
        answer = json.loads(p.with_name("response.json").read_text())["answer"]
        key = hashlib.sha256(f"{deployment}/{p.parent.name}/{answer}".encode()).hexdigest()[:12]
        mapping[key] = dict(deployment=deployment, arm=record["unit"]["method"], uid=uid)
        responses.append(dict(code=key, task=uid, answer=answer))
for name, obj in (("MASKED_ANSWERS",sorted(responses,key=lambda r:r["code"])),("ARM_KEY",mapping)):
    content=json.dumps(obj,ensure_ascii=False,indent=2)
    path=out/f"{name}.json"
    if path.exists():
        assert path.read_text()==content
    else:
        path.write_text(content)
