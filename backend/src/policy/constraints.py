"""Typed grant constraints — the narrow, signed limit vocabulary.

Deliberately NOT a policy language: constraints are a closed set of fixed
numeric fields (this slice: max_fee_lovelace only). No expressions, no DSL —
the dependency-free chain verifier never needs to understand them, and typed
numbers cannot carry PII into the signed payload or the witnessed chain.

Canonical forms pinned here (both enter hashed/signed bytes, so their exact
serialization is frozen by golden tests):

  * canonical_constraints: the grant-side constraints object as stored AND
    signed — sorted keys, compact separators (the row-hash canonical style).
  * canonical_violation: the witnessed denial payload
    {"type":...,"limit":...,"attempted":...} — key order pinned as
    type, limit, attempted (decision locked with the feature), compact
    separators, integers unquoted.

Fail-closed evaluation: an unknown constraint type denies (mirroring the
api-keys unknown-scope rank rule: unknown never confers, unknown requested
always refuses), a malformed value denies, and a constrained grant with an
UNDECLARED attempt denies — compliance is proven, never assumed.
"""

from __future__ import annotations

import json
from typing import Callable, NamedTuple, Optional


class _ConstraintSpec(NamedTuple):
    """Everything the fail-closed check needs to enforce one constraint type.

    The wording is part of the spec: reason strings flow into witnessed audit
    events, so each type pins its exact messages here rather than deriving
    them — adding a type never rewords an existing one."""

    declared_field: str            # the camelCase request field carrying the attempt
    violated_code: str             # stable machine code for a limit violation
    undeclared_reason: str
    violated_reason: Callable[[int, int], str]  # (limit, attempted) -> reason


# Closed set of constraint types this build understands. An unknown key in a
# grant's constraints — possible only through version skew or tampering, since
# creation rejects unknown keys with 422 — must deny, never be skipped.
_CONSTRAINT_SPECS: dict[str, _ConstraintSpec] = {
    "max_fee_lovelace": _ConstraintSpec(
        declared_field="attemptedFeeLovelace",
        violated_code="constraint_violated_max_fee",
        undeclared_reason=(
            "grant is fee-constrained; the request must declare "
            "attemptedFeeLovelace"
        ),
        violated_reason=lambda limit, attempted: (
            f"attempted fee {attempted} lovelace exceeds the "
            f"signed limit {limit} lovelace"
        ),
    ),
}

KNOWN_CONSTRAINTS = frozenset(_CONSTRAINT_SPECS)


def canonical_constraints(constraints: dict) -> str:
    """Deterministic bytes for the grant-side constraints object (stored and
    signed). Sorted keys + compact separators, like the row-hash canonical."""
    return json.dumps(
        constraints, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )


def canonical_violation(constraint_type: str, limit: int, attempted: int) -> str:
    """Deterministic bytes for the witnessed violation. Key order is pinned as
    type, limit, attempted — NOT alphabetical; json.dumps preserves insertion
    order, and this builder is the single write path."""
    return json.dumps(
        {"type": constraint_type, "limit": limit, "attempted": attempted},
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _valid_limit(value: object) -> bool:
    # bool is an int subclass; a true/false "limit" is malformed, not a number.
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


class ConstraintDenial:
    """A fail-closed denial from the constraint check.

    reason_code is the stable machine code; violation is the pinned canonical
    witness JSON for an actual limit violation (None for unknown/invalid/
    undeclared denials, where no {limit, attempted} pair exists).
    """

    __slots__ = ("reason_code", "reason", "violation")

    def __init__(self, reason_code: str, reason: str, violation: Optional[str] = None):
        self.reason_code = reason_code
        self.reason = reason
        self.violation = violation


def check_constraints(
    constraints_text: Optional[str],
    attempted_fee_lovelace: Optional[int],
) -> Optional[ConstraintDenial]:
    """Evaluate a grant's stored constraints against the declared attempt.

    Returns None when the grant passes (including the constraint-free case —
    the additive guarantee: no constraints, no new behavior). Returns a
    ConstraintDenial for every fail-closed path.
    """
    if constraints_text is None:
        return None

    try:
        constraints = json.loads(constraints_text)
    except (TypeError, ValueError):
        return ConstraintDenial(
            "constraint_invalid", "grant constraints are not valid JSON"
        )
    if not isinstance(constraints, dict) or not constraints:
        return ConstraintDenial(
            "constraint_invalid", "grant constraints must be a non-empty object"
        )

    unknown = set(constraints) - KNOWN_CONSTRAINTS
    if unknown:
        return ConstraintDenial(
            "constraint_unknown",
            "grant carries unknown constraint type(s): "
            + ", ".join(sorted(unknown)),
        )

    # Per-constraint ladder, alphabetical key order for a deterministic first
    # denial when several constraints fail. Each key runs the same fail-closed
    # sequence: malformed limit -> undeclared attempt -> limit comparison.
    declared = {"max_fee_lovelace": attempted_fee_lovelace}
    for key in sorted(constraints):
        spec = _CONSTRAINT_SPECS[key]
        limit = constraints[key]
        if not _valid_limit(limit):
            return ConstraintDenial(
                "constraint_invalid",
                f"{key} must be a non-negative integer",
            )

        attempted = declared.get(key)
        if attempted is None:
            return ConstraintDenial(
                "constraint_attempt_undeclared", spec.undeclared_reason
            )

        if attempted > limit:
            return ConstraintDenial(
                spec.violated_code,
                spec.violated_reason(limit, attempted),
                violation=canonical_violation(key, limit, attempted),
            )

    return None
