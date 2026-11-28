"""Repeat the Figure 14 diagnostic with a separate, explicit response contract."""
import argparse
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
prior = run_path(str(HERE / "evaluate.py"))
run, prepare, probe, sha, archive = (prior[k] for k in ("run", "prepare", "probe", "sha", "archive"))
RUN = prior["RUN"].with_name("rpeval_figure14_contract_v1")
PRIVATE = RUN / "private"
ADDENDUM = """Output contract: Return strictly valid JSON. MICRO must be a quoted fraction "n/{positions}", using exactly the count of individual supplied preference positions as the denominator, including each Ignore position. Count how many positions the response aligns with. MACRO is a JSON boolean and must be true exactly when all positions align. Preserve the published definitions of the six severity fields. Do not output additional fields."""
STAGE = "Figure14ContractJudge"


def frozen(asset):
    original, cohort, raw = prepare(asset)
    if original != archive.read(prior["PRIVATE"] / "FROZEN.json"):
        raise ValueError("Previous cohort or request drift")
    wires = {}
    for (uid, method), wire in raw.items():
        system, user = wire["messages"]
        message = user["content"] + "\n\n" + ADDENDUM.format(positions=cohort[uid]["positions"])
        wires[uid, method] = {**wire, "messages": [system, {**user, "content": message}]}
    results = archive.read(prior["PRIVATE"] / "RESULTS.json")["aggregate"]
    pin = {"original_pin_sha256": sha(original), "original_contract_outcomes": results["contracts"],
           "requests": sha(list(wires.values())), "cap": len(wires),
           "reference": probe.read_reference()[1], "control": sha(Path(__file__).read_bytes())}
    return pin, cohort, wires


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("freeze", "run", "replay"))
    p.add_argument("figure", type=Path)
    args = p.parse_args()
    data = frozen(args.figure.read_bytes())
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = PRIVATE / "FROZEN.json"
    if args.action == "freeze":
        probe.freeze(path, data[0])
        seen, _ = prior["previous"]["support"]["prior"]["find_archived"](data[2], HERE.parents[2])
        if seen:
            raise ValueError("Find and preserve prior exact receipts")
        print({"new_judges": data[0]["cap"]})
    elif archive.read(path) != data[0]:
        raise ValueError("Frozen comparison drift")
    else:
        run.__globals__.update(RUN=RUN, PRIVATE=PRIVATE, STAGE=STAGE)
        run(*data, live=args.action == "run")
