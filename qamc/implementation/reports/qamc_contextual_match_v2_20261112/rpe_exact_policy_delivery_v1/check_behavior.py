"""Check post-hoc reading notes against the complete, hash-validated archived RP answers."""
from collections import Counter
from pathlib import Path
import runpy
from contextlib import redirect_stdout
from io import StringIO
from hashlib import sha256
import json

here = Path(__file__).resolve().parent
with redirect_stdout(StringIO()):
    inventory = runpy.run_path(str(here/"inventory.py"))
notes = {n["case"]: n for n in json.loads((here/"behavior_annotations.json").read_text())}
seen = set()
for row in inventory["raw"]:
    uid = row["uid"]
    short = "/".join(uid.split("/")[-2:])
    if row["method"] != "RPR_PAPER_FULL" or short not in notes:
        continue
    payload = json.loads(row["actor_request"]["messages"][-1]["content"])
    policy = "".join(v["policy"] for v in payload["preference_use_policy"])
    archived = inventory["endpoints"][uid]
    assert policy == archived["labels"] and policy.count("C")==1
    assert sha256(row["answer"].encode()).hexdigest()==archived["scores"]["RPR_PAPER_FULL"]["answer_sha256"]
    note = notes[short]
    assert note["answer_hash"] == archived["scores"]["RPR_PAPER_FULL"]["answer_sha256"]
    texts = (payload["source_evidence"][policy.index("C")]["text"], row["answer"])
    assert len(note["witnesses"]) == len(texts)
    for witness, text in zip(note["witnesses"], texts):
        start = witness["offset"]
        assert sha256(text[start:start+witness["chars"]].encode()).hexdigest() == witness["sha256"]
    seen.add(short)
assert len(seen)==sum(inventory["multiplicity"].values())==len(notes)==13
print(dict(Counter(n["status"] for n in notes.values())))
