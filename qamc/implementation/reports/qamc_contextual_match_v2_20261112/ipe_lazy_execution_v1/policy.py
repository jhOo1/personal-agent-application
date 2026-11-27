"""Deferred execution for the frozen nonempty RPEval IPE-C candidate contract."""

def history_on(ipe_orders):
    if not ipe_orders or any(sorted(order) != ["A","B","C"] for order in ipe_orders):
        raise ValueError("A complete IPE ranking for each supplied source is required")
    return any(order[0] == "C" for order in ipe_orders)


def generate(task, *, estimate_ipe, read_orders, estimate_mle, empty_actor, rp_actor):
    """Callbacks retain ownership of their existing request, ledger, and parse contracts."""
    ipe = estimate_ipe(task)
    if not history_on(read_orders(task, ipe)):
        return empty_actor(task)
    mle = estimate_mle(task)
    return rp_actor(task, mle, ipe)
