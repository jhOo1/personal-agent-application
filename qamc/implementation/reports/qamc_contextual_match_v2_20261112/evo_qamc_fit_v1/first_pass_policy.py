"""Construct and validate general system instructions without deploying offline traces."""
from mutation_contract import _ID, _WORDS, corpus_ngrams
from qamc.common import parse_object

ARMS = ('GENERIC_SEARCH', 'CRITERIA_SEARCH')

PROPOSER = """You are optimizing a first-pass assistant that answers tasks given current task fields,
a tentative task-only plan, and selected verbatim history. The examples are earlier private
development outcomes. Scores are imperfect: inspect the drafts for actual behavior. Compare useful
personalization, misuse, omitted constraints, and completeness. Write a COMPLETE replacement
system instruction for a single final answer. Learn reusable behavior only. Do not cite or mention
examples, evaluation names, metrics, identifiers, specific topics or outputs from the examples.
The new instruction must work across open recommendations, formal deliverables, and objective
guidance, without assuming a fixed benchmark, format, or language. Keep the plan optional
guidance, answer in the requested language and format, and output only the user's deliverable.
Return a JSON object with exactly one key, actor_system, whose value is an English string of
900–3200 characters. Avoid schemas for final answers or extra model calls."""

SEED = """Produce the complete deliverable in the requested language and format.
Treat the current request as the specification, current facts as factual inputs, original
memory as evidence, and the task-only plan as a revisable suggestion.

Organize the answer around the choices, content and language the task requires or delegates.
Implement currently applicable restrictions in the actual recommendation or instruction;
do not weaken them into a disclaimer. Use a fitting soft preference to make a concrete
compatible choice when it adds value. A personal experience or belief is evidence of the
experience or belief, not by itself a requirement, a ranking criterion, or a public fact.
Apply a personal preference to a joint decision only when the present remit and evidence
support that influence. When requirements differ across participants, construct a workable
solution instead of silently applying one person's constraint to everyone or ignoring it.

In a communication, realize appropriate style and emphasis in the actual text while keeping
the factual states, relevant people, requests, commitments and all essential details accurate.
For objective claims and recommendations that affect others, use support appropriate to that
purpose. Resolve the whole deliverable coherently and revise an unhelpful plan. Output only
the finished answer. Keep internal steps and unnecessary private information out of it."""

METHOD = {
    'GENERIC_SEARCH': """Review each trace, its available facts and its evaluation feedback.
Find reusable causes of good and bad performance. Optimize the full instruction freely.""",
    'CRITERIA_SEARCH': """Compare each matched pair of traces on the same task and evidence
available to each run. Distinguish a change in actual ranking, constraint enforcement, expression
or public claim from merely mentioning history. Inspect whether the answer changed a task-authorized
criterion, and where a requirement survived or went missing. Do not attribute a difference to a
single factor unless the supplied records isolate it. Use this comparison to rewrite the full
instruction; do not just add a warning or produce a separate intermediate analysis.""",
}


def validate(content, feedback):
    proposal = parse_object(content)
    if not isinstance(proposal, dict) or set(proposal) != {'actor_system'}:
        raise ValueError('EXPECTED_ONE_ACTOR_SYSTEM')
    system = proposal['actor_system']
    if not isinstance(system, str) or not 900 <= len(system.strip()) <= 3200:
        raise ValueError('ACTOR_SYSTEM_SIZE')
    if _ID.search(system):
        raise ValueError('CASE_IDENTIFIER_IN_POLICY')
    forbidden = corpus_ngrams(feedback)
    tokens = _WORDS.findall(system.casefold())
    if any(tuple(tokens[i:i+8]) in forbidden for i in range(len(tokens)-7)):
        raise ValueError('EXAMPLE_COPY_IN_POLICY')
    return system.strip()
