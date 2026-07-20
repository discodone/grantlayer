"""GrantLayer MVP — Protected demo action handler."""

import datetime
import logging
import os
import uuid
from typing import Optional, cast

from ..audit.audit_log import append_event
from ..auth.challenges import validate_challenge
from ..core.crypto_signing import verify_grant_signature
from ..core.db import get_session_maker
from ..core.models import AccessRequest, AuditEvent, ChallengeResult, GrantExecution, PolicyResult
from ..grants.grant_executions import (
    create_grant_execution,
    update_grant_execution_audit_event_id,
)
from ..grants.grant_requests import get_grant_request_id_by_grant_id
from ..grants.grants import list_grants
from ..policy.policy_engine import evaluate_access

logger = logging.getLogger(__name__)


def _get_env_bool(name: str) -> bool:
    value = os.environ.get(name, "").strip().lower()
    return value in ("1", "true", "yes", "on")


def handle_demo_action(
    subject_id: str,
    role: str,
    action: str,
    resource: str,
    challenge_id: Optional[str] = None,
    operator_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    *,
    workspace_id: str,
) -> dict:
    require_challenge = _get_env_bool("GRANTLAYER_REQUIRE_CHALLENGE")
    if tenant_id is None:
        raise ValueError("tenant_id is required")
    if not workspace_id:
        raise ValueError("workspace_id is required")
    effective_tenant = tenant_id

    # Pre-allocate execution record for every attempt
    execution = GrantExecution(
        action=action,
        resource=resource,
        operator_id=operator_id,
        challenge_id=challenge_id,
    )

    try:
        # If challenge is required but missing, fail closed immediately.
        if require_challenge and not challenge_id:
            execution.challenge_result = "required_missing"
            execution.policy_result = "denied"
            execution.result = "denied"
            execution.error_code = "challenge_required"
            event = AuditEvent(
                subject_id=subject_id,
                role=role,
                action=action,
                resource=resource,
                approved=False,
                reason="challenge_required",
                challenge_present=False,
                challenge_result="required_missing",
                grant_signature_result="not_checked",
                tenant_id=effective_tenant,
                workspace_id=workspace_id,
                scope="tenant",
            )
            # Denial + its audit event commit together: an audit-write failure
            # rolls back the execution row (no record without its event).
            with get_session_maker()() as session:
                try:
                    execution = create_grant_execution(
                        execution,
                        tenant_id=effective_tenant,
                        workspace_id=workspace_id,
                        session=session,
                    )
                    append_event(event, conn=session.connection())
                    update_grant_execution_audit_event_id(
                        execution.id, event.id, session=session
                    )
                    session.commit()
                except Exception:
                    session.rollback()
                    raise
            return {
                "approved": False,
                "result": "denied",
                "reason": "challenge_required",
                "reasonCode": "challenge_required",
                "challengeResult": "required_missing",
                "auditEventId": event.id,
                "grantSignatureResult": "not_checked",
                "executionId": execution.id,
        }

        request = AccessRequest(
            subject_id=subject_id,
            role=role,
            action=action,
            resource=resource,
        )

        # Workspace-scoped matching: a grant is only eligible if it lives in the
        # caller's RESOLVED workspace — a sibling workspace's grant in the same
        # tenant must never authorize this request.
        grants = list_grants(tenant_id=effective_tenant, workspace_id=workspace_id)
        now = datetime.datetime.now(datetime.timezone.utc)
        result: PolicyResult = evaluate_access(request, grants, now)

        # Sprint 2B: verify grant signature before proceeding
        grant_signature_result: str = "not_checked"
        if result.matched_grant_id:
            matched_grant = next(
                (g for g in grants if g.id == result.matched_grant_id), None
            )
            if matched_grant is not None:
                sig_check = verify_grant_signature(matched_grant)
                grant_signature_result = sig_check
                if sig_check != "valid":
                    deny_map = {
                        "missing":       "grant_signature_missing",
                        "invalid":       "grant_signature_invalid",
                        "hash_mismatch": "grant_payload_hash_mismatch",
                        "unknown_key":   "grant_signature_unknown_key",
                    }
                    sig_code = deny_map.get(sig_check, f"grant_signature_{sig_check}")
                    result = PolicyResult(
                        approved=False,
                        reason=sig_code,
                        matched_grant_id=result.matched_grant_id,
                        reason_code=sig_code,
                    )

        challenge_present = challenge_id is not None
        challenge_result = "legacy_mode"
        resolved_challenge_id: Optional[str] = None

        if challenge_present:
            c_result, c_id = validate_challenge(cast(str, challenge_id), subject_id, action, resource, tenant_id=effective_tenant)
            challenge_result = c_result
            resolved_challenge_id = c_id
            # Fail-closed: invalid challenge blocks even a valid grant
            if c_result != "valid":
                result = PolicyResult(
                    approved=False,
                    reason=f"Challenge invalid: {c_result}",
                    matched_grant_id=result.matched_grant_id,
                    reason_code="challenge_invalid",
                )

        # Decision writes are ATOMIC: grant-use consumption, the execution
        # row, the audit event, and the event link commit together on one
        # session. An audit-write failure rolls back the consumed use and the
        # execution row — a durable execution without its audit event would be
        # a permanent gap in the anchored chain.
        with get_session_maker()() as session:
            try:
                if result.approved and result.matched_grant_id:
                    from ..grants.grants import try_consume_grant_use
                    consumed = try_consume_grant_use(
                        result.matched_grant_id, session=session
                    )
                    if not consumed:
                        result = PolicyResult(
                            approved=False,
                            reason="grant_usage_exhausted",
                            matched_grant_id=result.matched_grant_id,
                            reason_code="grant_usage_exhausted",
                        )

                # Populate execution record
                execution.grant_id = result.matched_grant_id
                execution.grant_request_id = get_grant_request_id_by_grant_id(result.matched_grant_id) if result.matched_grant_id else None
                execution.challenge_id = resolved_challenge_id
                execution.challenge_result = challenge_result
                execution.policy_result = result.reason
                execution.result = "succeeded" if result.approved else "denied"
                # error_code carries the stable machine code; policy_result
                # keeps the human reason — no more mirrored strings.
                execution.error_code = None if result.approved else result.reason_code
                execution = create_grant_execution(
                    execution,
                    tenant_id=effective_tenant,
                    workspace_id=workspace_id,
                    session=session,
                )

                event = AuditEvent(
                    subject_id=subject_id,
                    role=role,
                    action=action,
                    resource=resource,
                    approved=result.approved,
                    reason=result.reason,
                    matched_grant_id=result.matched_grant_id,
                    challenge_id=resolved_challenge_id,
                    challenge_present=challenge_present,
                    challenge_result=cast(ChallengeResult, challenge_result),
                    grant_signature_result=grant_signature_result,
                    tenant_id=effective_tenant,
                    workspace_id=workspace_id,
                    scope="tenant",
                )
                append_event(event, conn=session.connection())
                update_grant_execution_audit_event_id(
                    execution.id, event.id, session=session
                )
                session.commit()
            except Exception:
                session.rollback()
                raise

        if result.approved:
            return {
                "approved": True,
                "result": "allowed",
                "message": f"Action '{action}' on '{resource}' approved for '{subject_id}'.",
                "reason": result.reason,
                "reasonCode": result.reason_code or "access_granted",
                "matchedGrantId": result.matched_grant_id,
                "challengeId": resolved_challenge_id,
                "auditEventId": event.id,
                "grantSignatureResult": grant_signature_result,
                "executionId": execution.id,
            }
        else:
            return {
                "approved": False,
                "result": "denied",
                "reason": result.reason,
                "reasonCode": result.reason_code or "denied",
                "challengeResult": challenge_result,
                "auditEventId": event.id,
                "grantSignatureResult": grant_signature_result,
                "executionId": execution.id,
            }

    except Exception as exc:
        # Internal handler error after authorization path began
        logger.error(
            "demo_action unexpected failure: component=demo_action action=%s exception_type=%s",
            action,
            type(exc).__name__,
        )
        execution.policy_result = "error"
        execution.result = "failed"
        execution.error_code = "internal_handler_error"
        # Fresh identity for the failure record: everything the try block wrote
        # was rolled back with its session, and a distinct id makes it
        # structurally impossible for this row to collide with — or contradict —
        # any durable decision row.
        execution.id = str(uuid.uuid4())
        execution = create_grant_execution(
            execution, tenant_id=effective_tenant, workspace_id=workspace_id
        )
        return {
            "approved": False,
            "result": "failed",
            "reason": "internal_handler_error",
            "reasonCode": "internal_handler_error",
            "grantSignatureResult": "not_checked",
            "executionId": execution.id,
        }
