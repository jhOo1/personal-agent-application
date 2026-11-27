"""Read aggregate exposed dev grades and verify the corpus bytes against the original manifest."""
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
read = lambda p: json.loads(p.read_text())
manifest = read(root / "DATA_MANIFEST.json")
archive = root / "reports/qamc_b6"
categories = read(archive / "DEV_PER_CATEGORY.json")
result = {}
for task, data in categories.items():
    methods = data.get("memsyco", {})
    if not methods.get("A_task"):
        continue
    descriptor = manifest["sources"][task]
    actual = hashlib.sha256((root / descriptor["path"]).read_bytes()).hexdigest()
    if actual != descriptor["sha256"]:
        raise ValueError(f"Source hash mismatch for {task}")
    result[task] = {arm: methods[arm]["native_joint"] for arm in ("A_task", "E_full", "F_adaptive")}
pair = read(archive/"PAIRED_ANALYSIS.json")["dev"]["E_full -> F_adaptive"]["memsyco"]
if len(result) != 5 or sum(x["F_adaptive"][1] for x in result.values()) != pair["common"]:
    raise ValueError("Scope mismatch")
print(json.dumps({"tracks":result,"E_to_F_paired":{k:pair[k] for k in ("common","win","loss","tie")},
                  "upstream_in_manifest":manifest["commits"]["MemSyco-Bench"]},indent=2))
