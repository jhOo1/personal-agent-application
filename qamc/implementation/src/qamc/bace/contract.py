"""Source and bilateral-assessment contracts, not semantic truth guarantees."""
from dataclasses import dataclass
import math
import re

USES = frozenset({'PERSONAL_RANKING','PLAN_ADAPTATION','STYLE_ADAPTATION','USER_HISTORY','FACT_EVIDENCE'})


@dataclass(frozen=True, order=True)
class UseKey:
    unit_id: str
    scope_id: str
    use_kind: str

    def __post_init__(self):
        if not self.unit_id or not self.scope_id or self.use_kind not in USES:
            raise ValueError('Invalid concrete UseKey')


@dataclass(frozen=True)
class Span:
    unit_id: str
    start: int
    end: int
    exact_quote: str

    def validate(self, units):
        u = units[self.unit_id]
        if type(self.start) is not int or type(self.end) is not int:
            raise ValueError('Offsets must be integers')
        if not 0 <= self.start < self.end <= len(u['exact_text']):
            raise ValueError('Out-of-range span')
        if u['exact_text'][self.start:self.end] != self.exact_quote:
            raise ValueError('Quote differs from original source')
        return self


@dataclass(frozen=True)
class Assessment:
    key: UseKey
    role: str
    status: str
    raw_score: float | None
    evidence: tuple[Span, ...]
    reason: str
    uncertainty: str
    hard_conflict_claimed: bool = False

    def validate(self, units, scope_ids):
        if self.key.unit_id not in units or self.key.scope_id not in scope_ids:
            raise ValueError('Unknown use unit or scope')
        if self.role not in {'allow','deny'} or self.status not in {'ASSESSED','UNASSESSED'}:
            raise ValueError('Invalid assessment state')
        if self.status == 'UNASSESSED':
            if self.raw_score is not None:
                raise ValueError('Missing assessment must not have a numeric score')
        elif type(self.raw_score) not in (int,float) or not math.isfinite(self.raw_score) or not 0 <= self.raw_score <= 1:
            raise ValueError('Assessed score must be finite and in [0,1]')
        for span in self.evidence:
            span.validate(units)
        if not isinstance(self.reason,str) or not isinstance(self.uncertainty,str):
            raise ValueError('Reason and uncertainty must be explicit strings')
        return self


def require_context_boundary(span,units):
    """Conservative sentence-boundary contract, not a semantic parser.

    Sub-sentence extraction needs a later explicit context proof instead of
    silently clipping 'used to', 'not', 'but now', or a following reason. This
    may reject legitimate short clauses; that loss is reported, never hidden.
    """
    span.validate(units)
    text=units[span.unit_id]['exact_text']
    before=text[:span.start];after=text[span.end:]
    left_ok=not before.strip() or before.rstrip().endswith(('.', '!', '?')) or before.endswith('\n')
    right_ok=not after.strip() or span.exact_quote.rstrip().endswith(('.', '!', '?')) or after.startswith('\n')
    if not left_ok or not right_ok:
        raise ValueError('Partial sentence requires explicit qualifier-context proof')
    return span


def canonical_choice(answer):
    """Normalize letter-only formatting; do not infer an answer from free prose."""
    m = re.fullmatch(r'\s*\(?([a-dA-D])\)?[.]?\s*', answer)
    return m.group(1).lower() if m else None


def generation_input(payload):
    """An allowlist prevents evaluation metadata from silently reaching models."""
    from copy import deepcopy
    allowed = {'query','current_context','query_time','units','source_metadata',
               'profile_navigation','annotation_legend'}
    unexpected = set(payload) - allowed
    if unexpected:
        raise ValueError('Unexpected generation fields: '+','.join(sorted(unexpected)))
    # Derived navigation is not another evidence vote. Its schema is checked by
    # the frozen input adapter, and no evaluator result may be added recursively.
    forbidden={'gold','reference','reference_answer','correct_answer','preference_label',
               'judge_explanation','use_gold','test_labels','correct_idx','aligned_op',
               'explanation','violation_probability','preference_attribute'}
    def inspect(x):
        if isinstance(x,dict):
            if forbidden & set(x):
                raise ValueError('Evaluation field in generation input')
            for value in x.values(): inspect(value)
        elif isinstance(x,list):
            for value in x: inspect(value)
    inspect(payload)
    return deepcopy(payload)
