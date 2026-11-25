"""Render compatible alternatives for the same decision from one proposal."""
from collections import Counter, defaultdict

import effect_scope_compiler as scoped


ATOMIC = "ATOMIC"
BUNDLED = "BUNDLED"
ORDINARY = scoped.ORDINARY
MODES = (ATOMIC, BUNDLED, ORDINARY)
rank = scoped.rank
linked = scoped.linked

PROMPT = """Complete the CURRENT task in the original language using the given facts and task-only draft.
The history is evidence about specific people and conditions, never a request or a source of world
facts. Keep the complete draft unless a source actually helps an existing task decision or imposes a
real constraint on it. A valid change can introduce a newly feasible option for the original
decision. It cannot introduce a new goal, task, recipient, or unsupported real-world claim.

For each concrete decision that should change, make one decision record. Distinguish its TASK
basis (an exact excerpt of the Query, current context, or facts explaining why the decision belongs
to the deliverable) from WHERE the draft realizes it (exact text spans to replace). Do not put
draft text into task_basis. A necessary or useful task decision may be implicit in the Query:
quote the actual task wording it serves. A role match alone does not justify creating a decision.

Read all user evidence for legitimate constraints before choosing an edit. Do not mistake one
historical example for a requirement. A constraint remains strong when it applies to a person
actually using the shared outcome. Keep useful individual preferences within their scope. Never
convert the organizer's taste to a recipient or group requirement. Useful style can affect an
existing artifact without changing its claims, recipient, or sender identity.

Each effect is ONE source proposition, supported by an exact quotation from user-authored text.
Assign site REQUESTER_ACTION for their own delegated preparation, implementation, or personal
expression, SELF_OUTCOME for an outcome used by them alone, SHARED_OUTCOME if they actually
participate, OTHER_OUTCOME for other recipients. Authority SELF means the evidence supports the
user alone, GROUP means it covers the participants, RECIPIENT means the evidence describes that
recipient, DELEGATED means the current task expressly assigns the choice to the user's preferences.
Supply exact task words as delegation only in that last case; otherwise null. Force REQUIRE is a
live constraint, PREFER alters a default only within that authority, and OFFER is optional.

Build complete, interchangeable variants for the SAME decision if independent effects can be
omitted. A variant must express only its listed effects and preserve every other original
requirement. Put the most useful variant first. Explicitly provide a complete variant with just the
hard constraint(s) when a hard constraint can stand without softer effects. Keep independently
modifiable decisions in separate records with disjoint draft spans. If one effect changes several
dependent spans (including a default, downstream action, description, schedule, or budget), put
ALL corresponding patches in the same variant. A variant is an atomic unit; no individual patch
will be applied alone. To remove a choice, make remaining compatible choices and their dependent
prose consistent. To add a newly feasible value, replace the original recommendation in place;
don't retain disallowed advice as another default. Say what must be verified when feasibility
depends on missing facts. Do not unnecessarily duplicate unchanged text.

Return exactly this JSON shape. At most 8 decisions, 8 effects and 3 variants per decision,
and 8 patches per variant. Reuse each effect ID in all variants using that proposition.
Before must occur once inside the specified block and option; use null option for CONTENT.
Keep all spans non-overlapping within a variant and between decisions. A variant must genuinely
change the text. Use an empty after only to remove redundant text. No change: {"decisions":[]}.
{"decisions":[{"decision":"the existing task choice being affected","task_basis":"exact task excerpt",
  "effects":[{"id":"E1","source":{"id":"M0","quote":"exact user excerpt"},
              "site":"SHARED_OUTCOME","authority":"SELF","force":"REQUIRE","delegation":null}],
  "variants":[{"effects":["E1"],"patches":[{"block":"D1","option":null,
                   "before":"unique original text","after":"self-contained replacement"}]}]}]}"""


def request(root, blocks):
    wire = linked.request(root, blocks, ORDINARY)
    wire["messages"][0]["content"] = PROMPT
    return wire


def overlaps(patches):
    by_line = defaultdict(list)
    for patch in patches:
        by_line[patch["block"], patch["line"]].append((patch["start"], patch["end"]))
    return any(a[1] > b[0] for spans in by_line.values()
               for a, b in zip(sorted(spans), sorted(spans)[1:]))


def read_unit(entry, root, blocks):
    if not isinstance(entry, dict) or set(entry) != {"decision", "task_basis", "effects", "variants"}:
        raise ValueError("DECISION_SHAPE")
    name, basis, proposals, alternatives = (entry[k] for k in ("decision", "task_basis", "effects", "variants"))
    task = tuple(rank.draft.task_text(root["public_task"]))
    if not rank.planning.text(name, 300) or not rank.planning.text(basis, 500) or not any(basis in t for t in task):
        raise ValueError("TASK_BASIS")
    if not isinstance(proposals, list) or not 1 <= len(proposals) <= 8:
        raise ValueError("EFFECT_COUNT")
    if not isinstance(alternatives, list) or not 1 <= len(alternatives) <= 3:
        raise ValueError("VARIANT_COUNT")
    effects, failures = scoped.read_effects(
        [{**effect, "task_quote": basis} if isinstance(effect, dict) else effect for effect in proposals], root,
    )
    variants = []
    for index, item in enumerate(alternatives, 1):
        if not isinstance(item, dict) or set(item) != {"effects", "patches"}:
            failures.append("VARIANT_SHAPE")
            continue
        ids, patches = item["effects"], item["patches"]
        if (not isinstance(ids, list) or not 1 <= len(ids) <= 8
                or not all(isinstance(key, str) and key in effects for key in ids)
                or len(set(ids)) != len(ids)
                or not isinstance(patches, list) or not 1 <= len(patches) <= 8
                or not all(isinstance(patch, dict) and set(patch) == scoped.EDIT_FIELDS - {"effects"} for patch in patches)):
            failures.append("VARIANT_REFERENCES")
            continue
        # The underlying validator checks text coordinates. Provenance is
        # attached to the complete variant, not separately to each patch.
        edits, rejected = scoped.read_edits([{**patch, "effects": ids[:1]} for patch in patches], blocks, effects)
        if rejected or overlaps(edits):
            failures.extend(rejected or ["VARIANT_OVERLAP"])
            continue
        variants.append({"index": index, "effects": ids,
                         "patches": [{k: v for k, v in edit.items() if k != "effects"} for edit in edits]})
    return {"decision": name, "task_basis": basis, "effects": effects, "variants": variants}, failures


def parse(root, blocks, raw):
    obj = rank.model_object(raw, "decisions")
    if set(obj) != {"decisions"} or not isinstance(obj["decisions"], list) or len(obj["decisions"]) > 8:
        raise ValueError("INVALID_TRANSACTION_ENVELOPE")
    units, rejected = [], []
    for index, entry in enumerate(obj["decisions"], 1):
        try:
            unit, failures = read_unit(entry, root, blocks)
        except ValueError as error:
            rejected.append({"decision": index, "reason": str(error)})
            continue
        rejected.extend({"decision": index, "reason": reason} for reason in failures)
        if unit["variants"]:
            units.append({"index": index, **unit})
    # Alternatives may overlap inside a unit. A shared span between decisions
    # invalidates both possible transactions, regardless of permission.
    writes = defaultdict(list)
    for unit in units:
        for variant in unit["variants"]:
            for patch in variant["patches"]:
                writes[patch["block"], patch["line"]].append((patch["start"], patch["end"], unit["index"]))
    conflicts = set()
    for (block, _), spans in writes.items():
        choice = blocks[block]["kind"] == "CHOICE"
        for start, end, index in spans:
            if any(other != index and (choice or start < other_end and other_start < end)
                   for other_start, other_end, other in spans):
                conflicts.add(index)
    rejected.extend({"decision": index, "reason": "INTERDEPENDENT_SPANS"} for index in sorted(conflicts))
    return [unit for unit in units if unit["index"] not in conflicts], rejected


def select(unit, atomic):
    effects, variants = unit["effects"], unit["variants"]
    allowed = {key for key, effect in effects.items() if scoped.permitted(effect)}
    required = {key for key in allowed if effects[key]["force"] == "REQUIRE"
                and any(key in v["effects"] for v in variants)}
    for variant in variants if atomic else variants[:1]:
        used = set(variant["effects"])
        if required <= used <= allowed:
            return variant
    return None


def render(root, blocks, units, *, atomic):
    patches, committed, reasons = [], [], Counter()
    for unit in units:
        variant = select(unit, atomic)
        if variant is None:
            reasons["NO_PERMITTED_COMPLETE_VARIANT"] += 1
            continue
        patches.extend(variant["patches"])
        committed.append({"decision": unit["index"], "variant": variant["index"], "effects": variant["effects"]})
    # Permissions and provenance have already been evaluated at variant level.
    answer, _, failures = scoped.render(root, blocks, {}, patches, scope=False)
    if failures:
        # Combined writes can empty a CHOICE or the entire answer. A
        # transaction must never leave only the non-rejected part in place.
        reasons.update(item["reason"] for item in failures)
        return rank.render(root, blocks, {}, rank.DRAFT)["answer"], [], reasons
    return answer, committed, reasons
