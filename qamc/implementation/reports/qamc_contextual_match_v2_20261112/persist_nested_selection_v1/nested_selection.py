def use_reserve(primary, reserve):
    """An independently selected strict superset can augment a nonempty choice."""
    return bool(primary) and reserve is not None and set(primary) < set(reserve)
