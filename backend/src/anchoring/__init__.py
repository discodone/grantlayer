"""GrantLayer audit-chain anchoring (GL-350).

Pins the externally-exportable audit trail's head hash to a public chain so an
outside party can prove the trail has not been rewritten since a given time.

This package is pure-Python config + model in this step; the PyCardano writer
and the keyless verifier land in later steps.
"""
