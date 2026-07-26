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
from typing import Optional

# Closed set of constraint types this build understands. An unknown key in a
# grant's constraints — possible only through version skew or tampering, since
# creation rejects unknown keys with 422 — must deny, never be skipped.
KNOWN_CONSTRAINTS = frozenset({"max_fee_lovelace"})


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

    limit = constraints["max_fee_lovelace"]
    if not _valid_limit(limit):
        return ConstraintDenial(
            "constraint_invalid",
            "max_fee_lovelace must be a non-negative integer",
        )

    if attempted_fee_lovelace is None:
        return ConstraintDenial(
            "constraint_attempt_undeclared",
            "grant is fee-constrained; the request must declare "
            "attemptedFeeLovelace",
        )

    if attempted_fee_lovelace > limit:
        return ConstraintDenial(
            "constraint_violated_max_fee",
            f"attempted fee {attempted_fee_lovelace} lovelace exceeds the "
            f"signed limit {limit} lovelace",
            violation=canonical_violation(
                "max_fee_lovelace", limit, attempted_fee_lovelace
            ),
        )

    return None
