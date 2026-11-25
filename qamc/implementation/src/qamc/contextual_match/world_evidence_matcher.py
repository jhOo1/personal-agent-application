"""One frozen F11 Matcher delta: distinguish tailoring from world evidence.

The original source/compiler/Actor contract is unchanged. No dataset identity,
reference labels, external knowledge retrieval, or extra inference is introduced.
"""
from .four_cells_v2 import selector_request as frozen_selector_request
from .four_cells_v2 import compiled_actor


WORLD_EVIDENCE_CHECK = """\n\nCheck the proposed use of each source, not merely whether its topic fits.
Distinguish tailoring a choice or expression, reporting something about a
person, and supporting a claim about the world. A remembered belief, opinion,
confident assertion, or personal theory establishes what that person thinks;
its repetition, confidence, seniority, or institutional role does not establish
that its external claim is true or that an organization has adopted it.

For an informative or factual deliverable, do not retain a personal theory as
the basis for external claims, general advice, or mandatory rules. Personal
dislike is not evidence that a technology, practice, place, or group is inferior.
Keep applicable task facts and useful personal constraints without importing
an unsupported explanation or universal prescription from a related source.
An interest or past behavior can help tailor a choice without proving that
choice objectively best. Check the original text even if a View labels it fact.

This is not a blanket exclusion of beliefs, values, or opinions. They may be
the very information requested when explaining someone's perspective or drafting
an explicitly requested argument. Ethical, religious, dietary and other personal
constraints may legitimately guide that person's choices without being universal
facts. Preserve these uses, applicable soft preferences, negative constraints,
and original conditions. The current query must supply any requested viewpoint;
do not infer a new advocacy goal solely from memory.

Apply this distinction using only the existing selection contract. The Actor
will receive the retained original text, not a hidden account of your intended
use. Do not rely on an unwritten caveat to prevent unsupported claims. Select
original spans only where the existing boundaries permit it; do not fabricate
new span boundaries, source text, use labels, or answer content.
"""


def selector_request(task, prompts, memory_view, task_view):
    """Change only the F11 Selector system message; keep its public input exact."""
    body=frozen_selector_request(task,'F11',prompts,memory_view,task_view)
    body['messages'][0]['content'] += WORLD_EVIDENCE_CHECK
    return body


__all__=['WORLD_EVIDENCE_CHECK','selector_request','compiled_actor']
