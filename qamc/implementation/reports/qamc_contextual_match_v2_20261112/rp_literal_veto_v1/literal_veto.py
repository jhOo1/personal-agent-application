"""Screen strength promotion for explicit refusal or exclusive acceptance in source text."""

import re

ROLE = re.compile(r"(?m)^[ \t]*(?P<role>用户|助手|系统|user|assistant|system)[：:]\s*", re.I)
SENTENCE = re.compile(r"[^。！？！？\n.!?]+(?:[。！？\n.!?]|$)")
BINDING = re.compile(
    r"(?:绝对|坚决|完全|一律)(?:不会|不能|不可|不要|不予|不再|不)(?:接[受纳]|选择|推荐|考虑|购买|使用|安排|进入|参加|含有?|碰|吃|喝|有|选|用|去|接受)"
    r"|绝不(?:会)?(?:接受|选择|考虑|推荐|使用|购买|进入|参加|让|吃|喝|选|用|去)"
    r"|(?:完全|坚决|直接)排除|(?:严格|坚决)避免|严禁|不允许|一定不要|(?:只|仅)接受"
    r"|必须(?:完全)?(?:排除|避免|不含|禁止|避开)"
    r"|\b(?:never|absolutely (?:no|not)|under no circumstances|must not|only accept|strictly avoid)\b",
    re.I,
)
REPORTED = re.compile(r"(?:别人|同事|朋友|她|他说|店家|商家|助手)(?:曾经|之前|跟我)?(?:说|表示|要求)[：:]")
HYPOTHETICAL = re.compile(r"(?:假如|假设|如果我说|举个例子|例如有人|imagine if|hypothetically)", re.I)
NEGATED_REQUIREMENT = re.compile(r"(?:没办法|无法|不能|并非|不必|不需要|不一定要|未必能|不可能|不是|不要求)\s*$")


def explicit_refusals(text):
    """Return original snippets and offsets. Turn boundaries restrict speaker identity."""
    roles = list(ROLE.finditer(text))
    if roles:
        segments = [(match.end(), roles[i + 1].start() if i + 1 < len(roles) else len(text), "USER_TURN")
                    for i, match in enumerate(roles) if match["role"].lower() in {"用户", "user"}]
    else:
        segments = [(0, len(text), "UNATTRIBUTED_RECORD")]
    witnesses = []
    for start, end, origin in segments:
        for sentence in SENTENCE.finditer(text, start, end):
            quote = sentence.group()
            if REPORTED.search(quote) or HYPOTHETICAL.search(quote):
                continue
            for cue in BINDING.finditer(quote):
                if not NEGATED_REQUIREMENT.search(quote[:cue.start()]):
                    witnesses.append({"start": sentence.start(), "end": sentence.end(), "text": quote,
                                      "cue": cue.group(), "origin": origin})
                    break
    return witnesses
