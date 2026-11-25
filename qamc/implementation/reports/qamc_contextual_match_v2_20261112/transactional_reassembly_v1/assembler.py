"""Lossless answer segmentation, literal anchors and atomic reassembly."""
import json
import re

FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
LITERAL = re.compile(
    r"https?://[^\s<>()]+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|"
    r"(?<!\d)\d{4}[-/.]\d{1,2}(?:[-/.]\d{1,2})?(?!\d)|"
    r"(?<!\d)\d{1,2}:\d{2}(?!\d)|"
    r"(?<!\w)(?:[$€£]\s*\d[\d,.]*|[A-Z]{2,}[-#]\d[\d-]*)|"
    r"(?<!\d)\d[\d,.]*(?:\s*(?:mg|kg|km|mL|USD|years? old)\b|元|毫克|千克|公里|岁|%|％)"
)
FACT_VALUES = re.compile(
    r"(?:full name is|mailing address is|email address is|phone number is|account number is)\s+(.+?)(?:[.]?$)",
    re.IGNORECASE,
)


def segment(answer):
    entries, chunk, fence = [], [], None
    for line in answer.splitlines(keepends=True):
        chunk.append(line)
        marker = FENCE.match(line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0]==fence[0] and len(token)>=len(fence) and not line[marker.end():].strip():
                fence = None
        if fence is None and not line.strip():
            if any(part.strip() for part in chunk):
                entries.append("".join(chunk))
                chunk = []
            elif entries:
                entries[-1] += "".join(chunk)
                chunk = []
    if chunk:
        entries.append("".join(chunk))
    result, offset = [], 0
    for i,text in enumerate(entries,1):
        end = offset+len(text.encode())
        result.append({"id":f"U{i:02d}","text":text,"byte_start":offset,"byte_end":end})
        offset=end
    if not result or "".join(e["text"] for e in result)!=answer:
        raise ValueError("Cannot reconstruct base answer bytes")
    return result


def appears(literal, text):
    if literal[0].isdigit() or literal[-1].isdigit():
        return re.search(r"(?<!\d)"+re.escape(literal)+r"(?!\d)",text) is not None
    return literal in text


def anchors(task, answer):
    facts = task["facts"]
    if not isinstance(facts,list) or any(not isinstance(s,str) for s in facts):
        raise ValueError("Unexpected archived fact representation")
    values = set()
    for sentence in [task["query"],task["current_context"],*facts]:
        values.update(x.strip(".,;") for x in LITERAL.findall(sentence))
    for fact in facts:
        values.update(m.group(1) for m in FACT_VALUES.finditer(fact) if 3<=len(m.group(1))<=180)
    values = sorted((stem for stem in values if stem and appears(stem,answer)),
                    key=lambda s:(answer.index(s),-len(s),s))
    return [{"id":f"A{i:02d}","literal":s} for i,s in enumerate(values,1)]


def parse(raw):
    s = raw.strip()
    if s.startswith("```json\n") and s.endswith("\n```"):
        s = s[8:-4]
    def unique(pairs):
        out = {}
        for k,v in pairs:
            if k in out:
                raise ValueError("Duplicate key in reassembly program")
            out[k] = v
        return out
    return json.loads(s,object_pairs_hook=unique)


def execute(program, units, protected):
    source = {x["id"]:x["text"] for x in units}
    literal = {x["id"]:x["literal"] for x in protected}
    base = "".join(source.values())
    if program=={"mode":"KEEP"}:
        return base,{"copies":len(source),"writes":0,"inserts":0,"drops":0,"literal_count":len(literal),
                     "copied_chars":len(base),"written_chars":0,"routing":list(source),"anchor_refs":[]}
    if not isinstance(program,dict) or set(program)!={"mode","pieces"} or program["mode"]!="REASSEMBLE":
        raise ValueError("Expected KEEP or a REASSEMBLE program")
    pieces=program["pieces"]
    if not isinstance(pieces,list) or len(pieces)>2*len(source)+8:
        raise ValueError("Invalid piece list")
    remaining=set(source)
    rendered = ""
    counts={"copies":0,"writes":0,"inserts":0,"drops":0,"literal_count":len(literal),
            "copied_chars":0,"written_chars":0,"routing":[],"anchor_refs":[]}

    def consume(ids):
        if not isinstance(ids,list) or not ids or any(not isinstance(u,str) for u in ids):
            raise ValueError("Invalid consumed units")
        if len(set(ids))!=len(ids) or not set(ids)<=remaining:
            raise ValueError("Duplicate or unknown consumed unit")
        remaining.difference_update(ids)

    def part_text(parts):
        if not isinstance(parts,list) or not parts:
            raise ValueError("A new piece requires literal parts")
        values=[]
        for part in parts:
            if not isinstance(part,dict):
                raise ValueError("Malformed rendered part")
            if set(part)=={"text"} and isinstance(part["text"],str):
                values.append(part["text"])
            elif set(part)=={"anchor"} and isinstance(part["anchor"],str) and part["anchor"] in literal:
                values.append(literal[part["anchor"]])
                counts["anchor_refs"].append(part["anchor"])
            else:
                raise ValueError("Unrecognized textual or anchor part")
        result="".join(values)
        if not result.strip():
            raise ValueError("Empty written part")
        return result

    for entry in pieces:
        if not isinstance(entry,dict):
            raise ValueError("Expected operation object")
        op=entry.get("op")
        if op=="COPY" and set(entry)=={"op","unit"}:
            consume([entry["unit"]])
            outgoing=source[entry["unit"]]
            counts["copies"]+=1
            counts["copied_chars"]+=len(outgoing)
            counts["routing"].append(entry["unit"])
        elif op=="DROP" and set(entry)=={"op","consume"}:
            consume(entry["consume"])
            counts["drops"]+=len(entry["consume"])
            continue
        elif op=="WRITE" and set(entry)=={"op","consume","parts"}:
            consume(entry["consume"])
            outgoing=part_text(entry["parts"])
            counts["writes"]+=1
        elif op=="INSERT" and set(entry)=={"op","parts"}:
            outgoing=part_text(entry["parts"])
            counts["inserts"]+=1
        else:
            raise ValueError("Unknown or malformed reassembly operation")
        separator = "\n\n" if rendered and not rendered.endswith("\n") and not outgoing.startswith("\n") else ""
        rendered += separator+outgoing
        if op!="COPY":
            counts["written_chars"]+=len(outgoing)
    if remaining or not rendered.strip():
        raise ValueError("Omitted unit inventory or empty result")
    if any(not appears(s,rendered) for s in literal.values()):
        raise ValueError("Explicit task literal removed")
    return rendered,counts
