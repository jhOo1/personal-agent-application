"""Published implicit histories only; explicit labels never enter this adapter."""
def implicit_history(conversation, kind):
    result = []
    if kind == 'persona-driven':
        keys = sorted(conversation, key=int)
        for key in keys:
            turn = conversation[key]
            for role in ('user', 'assistant'):
                if not isinstance(turn.get(role), str) or not turn[role]:
                    raise ValueError('Incomplete official dialogue')
                result.append({'role': role, 'content': turn[role]})
    elif kind == 'choice-based':
        for role, key in [('user','query'), ('assistant','assistant_options'),
                          ('user','user_selection'), ('assistant','assistant_acknowledgment')]:
            if not isinstance(conversation.get(key), str) or not conversation[key]:
                raise ValueError('Incomplete official choice conversation')
            result.append({'role': role, 'content': conversation[key]})
    else: raise ValueError('Unknown implicit history form')
    return result
