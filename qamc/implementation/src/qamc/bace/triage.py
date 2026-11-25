"""Two-score triage. Thresholds must be supplied by a frozen protocol."""
from dataclasses import dataclass
from .contract import UseKey


@dataclass(frozen=True)
class Thresholds:
    low: float
    high: float
    version: str
    calibration_hash: str | None = None

    def __post_init__(self):
        if not 0 <= self.low < self.high <= 1 or not self.version:
            raise ValueError('Explicit ordered thresholds and version required')


@dataclass(frozen=True)
class VerifiedConflict:
    key: UseKey
    constraint_anchor: str
    verification_id: str

    def validate(self,query):
        if not self.constraint_anchor or self.constraint_anchor not in query or not self.verification_id:
            raise ValueError('Hard conflict requires a separately recorded check')
        return self


def decide(key, allow, deny, thresholds, *, supported=False, verified_conflict=None,
           query='', calibrated_scores=None):
    # The role's hard_conflict_claimed flag alone is never a verified veto.
    if verified_conflict is not None:
        verified_conflict.validate(query)
        if verified_conflict.key != key:
            raise ValueError('Conflict belongs to a different use')
        return 'DENY_THIS_USE'
    for role,a in (('allow',allow),('deny',deny)):
        if a is not None and (a.key != key or a.role != role):
            raise ValueError('Cannot compare different uses or swapped roles')
    if allow is None or deny is None or any(a.status != 'ASSESSED' for a in (allow,deny)):
        return 'REVIEW'
    a,d = (allow.raw_score,deny.raw_score)
    if calibrated_scores is not None:
        if not thresholds.calibration_hash:
            raise ValueError('Calibrated values require frozen calibration provenance')
        a,d=calibrated_scores
    if not all(type(v) in (int,float) and 0 <= v <= 1 for v in (a,d)):
        raise ValueError('Invalid score')
    if not supported:
        return 'REVIEW'
    if a >= thresholds.high and d <= thresholds.low:
        return 'ALLOW'
    if d >= thresholds.high and a <= thresholds.low:
        return 'DENY_THIS_USE'
    return 'REVIEW'
