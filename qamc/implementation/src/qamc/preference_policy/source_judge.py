"""Source-aware automatic diagnostics, separate from every native score.

This same-family model judge is not human calibration or unit-level gold truth.
It cannot establish causal attribution from a final answer alone.
"""
from qamc.common import sha
from .core import fields,strings,short

PROMPT='''Evaluate the answer using the original CURRENT query, task context and supplied raw memory units. You do not know the method. Judge faithful task completion and context-appropriate personalization, not amount of memory mentioned.
Memory not mentioned is not automatically underuse. A preference may be considered and outweighed by present constraints. Ordinary world QA need not restate history. Do not reward invented user times, locations, identities, experiences, causal explanations or commitments. Placeholder text may fail to complete a deliverable, but missing indispensable information may correctly require clarification. Preserve distinction between user beliefs and world facts, past/planned/current states, and requester/recipient/beneficiary. An option answer must be interpreted with the public options, never a private answer key. You have no gold answer or unit labels.
Only flag a concrete unsupported personal assertion, inappropriate preference influence, or source-backed task-critical omission. If evidence is ambiguous keep it uncertain. An omitted unit from these sources is not proof it never existed elsewhere. Do not produce a corrected answer, product choice or correct option letter. Return concise evidence checks, not hidden reasoning.
Return JSON exactly:
{"task_faithfulness":1,"unsupported_personal_facts":[{"answer_quote":"exact answer substring","source_refs":[],"reason":"brief"}],"overuse":[{"answer_quote":"exact answer substring","source_refs":["exact unit id"],"reason":"brief contextual misuse"}],"underuse":[{"query_anchor":"exact query substring","source_refs":["exact unit id"],"reason":"brief actual loss, not lack of mention"}],"uncertain":[]}
task_faithfulness is integer1..5. Each issue list at most6; uncertain is list of short strings. All source_refs reference supplied exact unit IDs. Unsupported personal facts may have empty refs when no evidence supports them. Overuse/underuse require source refs. Empty issue lists are allowed; they are predictions, not verification of truth.'''


def validate(obj,payload,answer):
    fields(obj,'task_faithfulness unsupported_personal_facts overuse underuse uncertain')
    if type(obj['task_faithfulness'])is not int or obj['task_faithfulness']not in range(1,6):raise ValueError('invalid task faithfulness')
    ids={x['unit_id']for x in payload['units']}
    for group in ['unsupported_personal_facts','overuse','underuse']:
        if not isinstance(obj[group],list)or len(obj[group])>6:raise ValueError('bounded diagnostic issues required')
        for row in obj[group]:
            anchor='query_anchor'if group=='underuse'else'answer_quote'
            fields(row,anchor+' source_refs reason')
            text=payload['query']if group=='underuse'else answer
            if short(row[anchor],12000)not in text:raise ValueError('unanchored diagnostic quote')
            refs=strings(row['source_refs'])
            if not set(refs)<=ids or(group!='unsupported_personal_facts'and not refs):raise ValueError('invalid diagnostic references')
            short(row['reason'],600)
    strings(obj['uncertain']);return obj


def score(payload,answer,gateway):
    inp={**payload,'answer':answer}
    return gateway.object('source_diagnostic/'+sha(inp),PROMPT,inp,lambda o:validate(o,payload,answer),4096)
