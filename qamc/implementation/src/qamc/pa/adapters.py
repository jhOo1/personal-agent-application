"""Benchmark-specific public formatting; no evaluation labels enter tasks."""
import ast
import re
from pathlib import Path
from .core import Memory, PublicTask


def pure_functions(path, names, constants=None):
    nodes = [n for n in ast.parse(Path(path).read_text()).body
             if isinstance(n, ast.FunctionDef) and n.name in names]
    if {n.name for n in nodes} != set(names): raise ValueError('Pinned upstream interface changed')
    env = dict(constants or {})
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), env)
    return env


def benchpres_public(prompt, uid):
    # Public-text grammar, never evaluation preference_attribute/label fields.
    marker = '\n\nWrite a complete message to recipient'
    if prompt.count(marker) != 1: raise ValueError('Unknown BenchPreS prompt grammar')
    profile, tail = prompt.split(marker)
    preferences = []; facts = []
    for index, line in enumerate(profile.splitlines()):
        if not line.strip(): continue
        if re.search(r'\b(?:prefer(?:s)?|enjoy(?:s)?|dislike(?:s)?|like(?:s)?|love(?:s)?|hate(?:s)?)\b', line, re.I):
            preferences.append(Memory(f'L{index}', line))
        else: facts.append(line)
    if not preferences: raise ValueError('No recognized public preference statements')
    # Preserve all other supplied profile text identically across methods. This
    # is a controlled full-profile track, not a claim of relevant-fact selection.
    return PublicTask(uid, 'Write a complete message to recipient'+tail,
                      tuple(preferences), fixed_facts=tuple(facts))


def prefeval_public(row, uid, upstream, kind='persona', word_limit=300):
    if kind not in {'persona','choice'}: raise ValueError('Unknown implicit form')
    functions = pure_functions(Path(upstream)/'utils/implicit_utils.py',
        {'extract_conversation_to_messages', 'extract_conversation_to_msg_persona',
         'get_implicit_question_prompt'}, {'REMINDER':'', 'COT_PROMPT':''})
    conversation = row['conversation']
    if kind == 'persona':
        messages = functions['extract_conversation_to_msg_persona'](conversation, 'claude')
    else:
        messages, _ = functions['extract_conversation_to_messages'](conversation, 'claude')
    # Use the native formatter for the fixed zero-intervening-turn generation
    # track. Retain role attribution in the memory text; never inject preference.
    native = functions['get_implicit_question_prompt'](
        list(messages), row['question'], [], 'claude', 0, word_limit, False, False)
    history = '\n\n'.join(m['role'].upper()+':\n'+m['content'] for m in native[:-1])
    task = PublicTask(uid, native[-1]['content'], (Memory('CONVERSATION', history),))
    return task, native
