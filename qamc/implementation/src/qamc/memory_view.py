def actor_view(compiled):
    """No permanent mutation: exclude restricted content while preserving valid projections."""
    return {"task_goal": compiled["task_goal"],
            "evidence": [x for x in compiled["items"] if x["application"] != "SUPPRESS_FOR_QUERY"],
            "constraints": compiled.get("constraints", []), "needs": compiled["needs"],
            "unresolved_needs": compiled.get("unresolved_needs", []),
            "restrictions": [{"memory_ids": x.get("memory_ids", []), "reason": x.get("scope_limit", "")}
                             for x in compiled["items"] if x["application"] == "SUPPRESS_FOR_QUERY"]}
