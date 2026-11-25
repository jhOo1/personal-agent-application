"""Use an explicit Qwen reasoning cap without changing archived samplers."""
import importlib.util

from proposals.qamc_protocol_alignment import sampling, transport
from qamc.contextual_match.usage_observability import UsageObservableSampler


FIELD = "thinking_budget"
MODEL = "qwen3.8-flash"


def validate_budget_request(wire):
    if not isinstance(wire, dict):
        raise ValueError("A native request object is required")
    sampling.validate_public_request({k: value for k, value in wire.items() if k != FIELD})
    budget = wire.get(FIELD)
    if wire["model"] != MODEL or type(budget) is not int or budget <= 0:
        raise ValueError("A Qwen request requires an explicit positive thinking budget")


def controlled_wire(wire, budget):
    sampling.validate_public_request(wire)
    prepared = {**wire, FIELD: budget}
    validate_budget_request(prepared)
    return prepared


def isolated_contract(module):
    spec = importlib.util.spec_from_file_location(f"{module.__package__}._budget_{module.__name__.split('.')[-1]}",
                                                  module.__file__)
    internal = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(internal)
    internal.validate_public_request = validate_budget_request
    return internal


_budget_journal = isolated_contract(sampling)
_budget_init = isolated_contract(transport)
_budget_init.SamplingJournal = _budget_journal.SamplingJournal


class ThinkingBudgetSampler(UsageObservableSampler):
    """Freeze the budget in both request identity and sampling configuration."""

    def __init__(self, root, manifest, **options):
        for row in manifest["units"]:
            stage = manifest["protocol"]["stages"][row["unit"]["stage"]]
            wire = row["request"]
            validate_budget_request(wire)
            if wire[FIELD] != stage.get(FIELD):
                raise ValueError("Unfrozen thinking budget")
        # The constructor and journal need the extended contract. The
        # inherited dispatch, SSE reader, sanitizer and receipt stay intact.
        _budget_init.NativeSampler.__init__(self, root, manifest, **options)
