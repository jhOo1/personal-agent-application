"""Same released author policy across public tasks; no benchmark routing.

The complete historical prompt, including its nonfunctional tool descriptions,
is kept for faithful comparison. No tools are supplied by the API request.
Only extra context/facts need a general input adapter; q/M-only wires are exact
author wires, allowing completed Persist results to be reused verbatim.
"""
from copy import deepcopy
import json

from .development import text_request
from .persist_author_bridge import PersistAuthorBridge


def actor(task, bridge):
    if not isinstance(bridge, PersistAuthorBridge):raise ValueError('Pinned author bridge required')
    memories = [m.text for m in task.memories]
    system = bridge.render(memories, 'qwen3.8-flash', bridge.blobs['GEPA'].decode())
    extra = bool(task.current_context or task.fixed_facts)
    user = ({'query': task.query, 'current_context': task.current_context,
             'fixed_facts': list(task.fixed_facts)} if extra else task.query)
    request = text_request(system, user, cap=4096)
    if 'tools' in request or 'tool_choice' in request:raise ValueError('No real tools authorized by source prompt text')
    return {'request': request, 'view': {'query': task.query, 'current_context': task.current_context,
        'fixed_facts': list(task.fixed_facts), 'original_memory_texts': deepcopy(memories),
        'historical_author_system_prompt': system},
        'audit': {'complete_author_policy': True, 'added_context_container': extra,
                  'no_actual_tool_capabilities': True, 'no_benchmark_or_uid_routing': True,
                  'historical_dates_in_template_preserved_not_current_fact': True}}
