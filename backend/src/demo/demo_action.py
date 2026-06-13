"""GrantLayer MVP — Protected demo action handler."""

import datetime
import logging
import os
from typing import Optional

from ..audit.audit_log import append_event
from ..auth.challenges import validate_challenge
from ..core.crypto_signing import verify_grant_signature
from ..core.models import AccessRequest, AuditEvent, GrantExecution, PolicyResult
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
) -> dict:
    require_challenge = _get_env_bool("GRANTLAYER_REQUIRE_CHALLENGE")
    if tenant_id is None:
        raise ValueError("tenant_id is required")
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
            execution = create_grant_execution(execution, tenant_id=effective_tenant)

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
                scope="tenant",
            )
            append_event(event)
            update_grant_execution_audit_event_id(execution.id, event.id)
            return {
                "approved": False,
                "reason": "challenge_required",
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

        grants = list_grants(tenant_id=effective_tenant)
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
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
                    }
                    result = PolicyResult(
                        approved=False,
                        reason=deny_map.get(sig_check, f"grant_signature_{sig_check}"),
                        matched_grant_id=result.matched_grant_id,
                    )

        challenge_present = challenge_id is not None
        challenge_result = "legacy_mode"
        resolved_challenge_id: Optional[str] = None

        if challenge_present:
            c_result, c_id = validate_challenge(challenge_id, subject_id, action, resource, tenant_id=effective_tenant)
            challenge_result = c_result
            resolved_challenge_id = c_id
            # Fail-closed: invalid challenge blocks even a valid grant
            if c_result != "valid":
                result = PolicyResult(
                    approved=False,
                    reason=f"Challenge invalid: {c_result}",
                    matched_grant_id=result.matched_grant_id,
                )

        # Atomic grant usage consumption
        if result.approved and result.matched_grant_id:
            from ..grants.grants import try_consume_grant_use
            consumed = try_consume_grant_use(result.matched_grant_id)
            if not consumed:
                result = PolicyResult(
                    approved=False,
                    reason="grant_usage_exhausted",
                    matched_grant_id=result.matched_grant_id,
                )

        # Populate execution record
        execution.grant_id = result.matched_grant_id
        execution.grant_request_id = get_grant_request_id_by_grant_id(result.matched_grant_id) if result.matched_grant_id else None
        execution.challenge_id = resolved_challenge_id
        execution.challenge_result = challenge_result
        execution.policy_result = result.reason
        execution.result = "succeeded" if result.approved else "denied"
        execution.error_code = None if result.approved else result.reason
        execution = create_grant_execution(execution, tenant_id=effective_tenant)

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
            challenge_result=challenge_result,
            grant_signature_result=grant_signature_result,
            tenant_id=effective_tenant,
            scope="tenant",
        )
        append_event(event)
        update_grant_execution_audit_event_id(execution.id, event.id)

        if result.approved:
            return {
                "approved": True,
                "message": f"[DEMO] Action '{action}' on '{resource}' approved for '{subject_id}'.",
                "matchedGrantId": result.matched_grant_id,
                "challengeId": resolved_challenge_id,
                "auditEventId": event.id,
                "grantSignatureResult": grant_signature_result,
                "executionId": execution.id,
            }
        else:
            return {
                "approved": False,
                "reason": result.reason,
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
        execution = create_grant_execution(execution, tenant_id=effective_tenant)
        return {
            "approved": False,
            "reason": "internal_handler_error",
            "grantSignatureResult": "not_checked",
            "executionId": execution.id,
        }
