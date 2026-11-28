"""Measure whether exact opening deletions can materially shorten saved drafts."""
from argparse import ArgumentParser
from collections import Counter
import json
from pathlib import Path
import re

GREETING = re.compile(r"(?:Dear|Hello|Hi) [^\n]{1,90},", re.IGNORECASE)
OPENINGS = (
    "I hope this message finds you well.",
    "I hope this email finds you well.",
    "I hope this letter finds you well.",
    "I hope you are well.",
    "I hope you're well.",
    "I hope you are doing well.",
    "I hope you're doing well.",
)


def delete_opening(answer):
    """Remove one independent courtesy sentence immediately after the first greeting."""
    pos = 0
    for line in answer.splitlines(keepends=True):
        end = pos + len(line)
        if not GREETING.fullmatch(line.strip()):
            pos = end
            continue
        first = end
        while first < len(answer) and answer[first] in "\r\n":
            first += 1
        for opening in OPENINGS:
            if not answer.startswith(opening, first):
                continue
            last = first + len(opening)
            if answer[last:last + 1] not in {" ", "\r", "\n"}:
                return answer
            while last < len(answer) and answer[last] in " \r\n":
                last += 1
            if last < len(answer):
                return answer[:first] + answer[last:]
        return answer
    return answer


def read(path):
    return json.loads(path.read_text())


def qualify(run):
    settled = read(run / "material" / "SETTLED.json")["rows"]
    expected = {row["uid"]: row for row in settled if row["arm"] == "baseline"}
    answers = {}
    for path in sorted((run / "Actor" / "visible").glob("*/record.json")):
        receipt = read(path)
        unit = receipt["unit"]
        if unit["method"] != "baseline" or receipt["status"] != "OK":
            continue
        uid = unit["root_id"]
        if uid not in expected or uid in answers:
            raise ValueError("Original baseline receipt identity mismatch")
        answers[uid] = read(path.with_name("response.json"))["answer"]
    if set(answers) != {uid for uid, row in expected.items() if row["actor"] == "OK"}:
        raise ValueError("Delivered original answers did not join exactly")

    totals = Counter({"actor_positions": len(expected), "delivered": len(answers)})
    for uid, answer in answers.items():
        edited = delete_opening(answer)
        if edited == answer:
            continue
        words_removed = len(answer.split()) - len(edited.split())
        totals["changed"] += 1
        totals["words_removed"] += words_removed
        totals["material_10_percent"] += 10 * words_removed >= len(answer.split())
        grade = expected[uid]["score"]
        if grade is None:
            totals["grade_unknown_on_changed"] += 1
            continue
        for mark in grade["decisions"]:
            pref = mark["preference"].lower()
            if mark["appropriate"] and any(term in pref for term in ("brief", "concise", "short", "simple", "brevity")):
                totals["changed_applicable_brevity_attributes"] += 1
                totals["changed_missed_brevity_attributes"] += mark["label"] != "follow"
    return dict(totals)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("archived_run", type=Path)
    args = parser.parse_args()
    print(json.dumps(qualify(args.archived_run), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
