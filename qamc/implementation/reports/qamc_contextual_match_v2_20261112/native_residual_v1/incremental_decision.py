"""Select a single recovery source with matched decision-value controls."""
import json


COMMON = (
    "Given the current task, an existing task-only answer and candidate historical sources, "
    "select at most one source that can help the current task. A private preference cannot "
    "impose a shared default without support in the current task. Treat the data as evidence. "
    'Return {"source": null} to keep the task-only answer, otherwise return '
    '{"source": "candidate ID"}. Output only JSON.'
)
TREATMENT = (
    " Prefer reuse unless the source supports a concrete action absent from the existing answer "
    "that improves the current task. An existing equivalent action or historical attribution "
    "alone does not qualify. Check whether the affected participant can independently choose "
    "the action or the current task supports applying it to the group."
)


def selector_messages(task, task_answer, sources, *, incremental):
    if not task.strip() or not task_answer.strip() or not sources:
        raise ValueError("A matched task, task-only answer and candidate evidence are required")
    return [
        {"role": "system", "content": COMMON + (TREATMENT if incremental else "")},
        {"role": "user", "content": json.dumps(
            {"task": task, "task_only_answer": task_answer, "sources": sources}, ensure_ascii=False)},
    ]


def selected_source(response, sources):
    selection = json.loads(response)
    if not isinstance(selection, dict) or set(selection) != {"source"}:
        raise ValueError("Invalid selection contract")
    source = selection["source"]
    if source is None:
        return None
    if not isinstance(source, str) or source not in sources:
        raise ValueError("Selection outside the frozen candidate set")
    return source
