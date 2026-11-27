"""Bound gains on author B/C positions using only archived strict Match counts."""
from collections import defaultdict
from audit_rpe_protected_repairs import BASE, read, scan


def lower_net(old_total, new_total, target_count, size):
    # Minimum new matches in the target minus maximum old matches there.
    return max(0, new_total - (size - target_count)) - min(old_total, target_count)


def main():
    base = {row["uid"]: row for row in read(BASE)["rows"]}
    by_target = defaultdict(list)
    candidates = scan()["candidates"]
    for row in candidates:
        labels = base[row["uid"]]["labels"]
        for target in ("B", "C", "BC"):
            count = sum(label in target for label in labels)
            lower = lower_net(row["old"]["match"]["matched"], row["new"]["match"]["matched"],
                              count, len(labels))
            if lower > 0:
                by_target[target].append((row["uid"], row["group"], row["method"], lower))
    print("Screened pairs:", len(candidates))
    for target in ("B", "C", "BC"):
        hits = by_target[target]
        print(target, "pairs/tasks/groups:", len(hits), len({x[0] for x in hits}),
              len({x[1] for x in hits}))
        for uid, _, method, lower in hits:
            print(" ", uid, method, lower)


if __name__ == "__main__":
    main()
