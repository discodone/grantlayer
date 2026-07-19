"""The anchor job exercises the anchor-writer grant before anchoring.

The anchor run is itself a granted authority. Before the head is read,
_anchor_audit_chain_sync exercises the anchor-writer grant through the
standard decision path — challenge mint + consume (single-use, same as the
backup hook; no legacy mode), policy evaluation, signature gate, execution
row, chain-linked audit event, use-count consumption — so the exercise
event sits INSIDE the anchored range: the anchor attests to its own
authorization, the same accepted pattern as every post-anchor event.

Fail-closed both ways:
  * denied exercise → status refused_grant_exercise_denied, and the run
    stops before any chain machinery (no context, no probe, no submitted
    row, no network call) — while the denial itself is chain-witnessed;
  * erroring/unavailable decision path (including an internal decision
    failure, which produces no witnessed decision) → status
    refused_grant_exercise_unavailable, same refusal shape.

Decided semantics (rulings, 2026-07-19): the exercise runs in-process via
the decision handler — identity is the anchor-writer grant tuple (subject
'anchor-writer', role 'agent', action 'submit_anchor', resource
'cardano/{network}'), no HTTP dependency. ALLOWED-BUT-SUBMIT-FAILED IS
ACCEPTABLE TRUE HISTORY: if the exercise is allowed and the submit then
fails, the chain honestly witnesses an exercised authority (and a consumed
use) for an anchor that never confirmed — the authority WAS exercised; the
anchor outcome lives in anchor_records, not the audit chain.

Self-provisions SQLite (listed in _sqlite_only_modules.py).
"""

import os
import tempfile
import unittest
from contextlib import ExitStack
from unittest import mock

import backend.src.core.config as _cfg
import backend.src.core.db as _db

_WS = "22222222-2222-2222-2222-222222222222"
_TENANT = "hofer-test"


def _fake_config():
    cfg = mock.MagicMock(name="CardanoConfig")
    cfg.is_fully_configured.return_value = True
    cfg.workspace_id = _WS
    cfg.network = "preprod"
    cfg.anchor_label = 923350
    cfg.blockfrost_project_id = "preprodPID"
    cfg.signing_key = '{"type":"x","cborHex":"00"}'
    cfg.max_wallet_lovelace = None
    cfg.max_fee_lovelace = None
    cfg.expected_address = None
    cfg.effective_min_anchor_events = 1
    return cfg


class _Base(unittest.TestCase):
    def setUp(self):
        self._orig_plaintext = _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE
        self._orig_db = _db.DB_PATH_OR_URL
        os.environ["GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE"] = "true"
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = True

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self._db_path = tmp.name
        _db.DB_PATH_OR_URL = self._db_path
        _db.DB_PATH = self._db_path
        _db.init_db()
        # init_db provisions the app tables; anchor_records + workspaces come
        # from the ORM metadata (alembic-managed in production).
        from sqlalchemy import create_engine

        from backend.src.core.orm import Base
        engine = create_engine(f"sqlite:///{self._db_path}")
        Base.metadata.create_all(engine)
        engine.dispose()
        self._create_workspace_row()

    def tearDown(self):
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = self._orig_plaintext
        _db.DB_PATH_OR_URL = self._orig_db
        _db.DB_PATH = self._orig_db
        try:
            os.unlink(self._db_path)
        except OSError:
            pass

    def _create_workspace_row(self):
        """The job resolves the exercise tenant from the workspace row."""
        from backend.src.core.db import get_session_maker
        from backend.src.core.orm import Workspace

        with get_session_maker()() as session:
            session.add(Workspace(
                id=_WS,
                tenant_id=_TENANT,
                name="anchor-exercise-test",
                slug="anchor-exercise-test",
                owner_id="test-op",
                status="active",
                created_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
            ))
            session.commit()

    def _create_anchor_writer_grant(self) -> str:
        """Signed, live anchor-writer grant via the service layer (role=agent).

        Resource matches the config-derived exercise tuple: cardano/preprod
        for the fake preprod config (cardano/mainnet in production).
        """
        from backend.src.core.db import get_session_maker
        from backend.src.core.models import Grant
        from backend.src.core.repositories_sqlalchemy import SqlAlchemyGrantRepository
        from backend.src.grants.grant_service import GrantService

        grant = Grant(
            subject_id="anchor-writer",
            role="agent",
            action="submit_anchor",
            resource="cardano/preprod",
            valid_from="2026-01-01T00:00:00Z",
            valid_until="2027-01-01T00:00:00Z",
            created_by="test-op",
            reason="anchor exercise contract grant",
        )
        with get_session_maker()() as session:
            svc = GrantService(repo=SqlAlchemyGrantRepository(session), session=session)
            svc.create_grant(grant, tenant_id=_TENANT, workspace_id=_WS)
            session.commit()
        return grant.id

    def _run_job(self, stack: ExitStack):
        from backend.src.anchoring import writer
        from backend.src.workers import jobs

        stack.enter_context(mock.patch(
            "backend.src.anchoring.config.CardanoConfig.from_env",
            return_value=_fake_config(),
        ))
        self.probe = stack.enter_context(mock.patch.object(
            writer, "probe_reachable", return_value=None))
        self.submit = stack.enter_context(mock.patch.object(
            writer, "submit_anchor", return_value="txdeadbeef"))
        stack.enter_context(mock.patch.object(
            writer, "build_chain_context", return_value=mock.MagicMock()))
        return jobs._anchor_audit_chain_sync(None)

    def _events(self):
        import sqlalchemy as sa
        engine = sa.create_engine(f"sqlite:///{self._db_path}")
        with engine.connect() as conn:
            rows = conn.execute(sa.text(
                "SELECT action, subject_id, approved, workspace_id, "
                "challenge_present, challenge_result FROM audit_events"
            )).fetchall()
        engine.dispose()
        return rows

    def _anchor_records(self):
        import sqlalchemy as sa
        engine = sa.create_engine(f"sqlite:///{self._db_path}")
        with engine.connect() as conn:
            rows = conn.execute(sa.text(
                "SELECT status, entry_count FROM anchor_records"
            )).fetchall()
        engine.dispose()
        return rows

    def _challenges(self):
        import sqlalchemy as sa
        engine = sa.create_engine(f"sqlite:///{self._db_path}")
        with engine.connect() as conn:
            rows = conn.execute(sa.text(
                "SELECT status, subject_id, action FROM challenges"
            )).fetchall()
        engine.dispose()
        return rows

    def _grant_use_count(self, grant_id: str) -> int:
        import sqlalchemy as sa
        engine = sa.create_engine(f"sqlite:///{self._db_path}")
        with engine.connect() as conn:
            row = conn.execute(sa.text(
                "SELECT use_count FROM grants WHERE id=:g"), {"g": grant_id}).one()
        engine.dispose()
        return row.use_count


class TestDeniedExerciseRefusesAnchor(_Base):
    def test_no_grant_means_no_anchor_and_no_network(self):
        # No anchor-writer grant exists → the exercise denies → the run refuses
        # before any chain machinery.
        with ExitStack() as stack:
            result = self._run_job(stack)
        self.assertEqual(result["status"], "refused_grant_exercise_denied")
        self.assertEqual(result["reason_code"], "no_matching_grant")
        self.assertEqual(self.probe.call_count, 0, "no reachability probe on refusal")
        self.assertEqual(self.submit.call_count, 0, "no submit on refusal")
        self.assertEqual(self._anchor_records(), [], "no submitted row on refusal")
        # the denial itself is still witnessed (standard decision path)
        denied = [e for e in self._events()
                  if e.action == "submit_anchor" and e.approved == 0]
        self.assertEqual(len(denied), 1, "the denied exercise must be chain-witnessed")


class TestAllowedExerciseIsInsideAnchoredRange(_Base):
    def test_exercise_event_commits_before_head_read(self):
        self._create_anchor_writer_grant()
        with ExitStack() as stack:
            result = self._run_job(stack)
        self.assertEqual(result["status"], "confirmed", result)
        exercised = [e for e in self._events()
                     if e.action == "submit_anchor" and e.approved == 1
                     and e.subject_id == "anchor-writer" and e.workspace_id == _WS]
        # grant creation writes one submit_anchor event (grant_created reason);
        # the exercise must add a second, approved, decision event.
        self.assertGreaterEqual(len(exercised), 2,
                                "the allowed exercise must be chain-witnessed")
        # the head was computed AFTER the exercise committed: the anchored
        # entry_count covers every workspace event including the exercise.
        records = self._anchor_records()
        self.assertEqual(len(records), 1)
        ws_events = [e for e in self._events() if e.workspace_id == _WS]
        self.assertEqual(records[0].entry_count, len(ws_events),
                         "anchored range must include the exercise event")

    def test_exercise_uses_a_real_single_use_challenge(self):
        # Ruling: full challenge mint + consume, like the backup hook — the
        # exercise decision must carry a validated challenge, and the minted
        # challenge must be burned.
        self._create_anchor_writer_grant()
        with ExitStack() as stack:
            self._run_job(stack)
        decision_events = [e for e in self._events()
                           if e.action == "submit_anchor" and e.approved == 1
                           and e.challenge_present == 1]
        self.assertEqual(len(decision_events), 1,
                         "the exercise decision must carry a challenge")
        self.assertEqual(decision_events[0].challenge_result, "valid")
        used = [c for c in self._challenges()
                if c.subject_id == "anchor-writer" and c.status == "used"]
        self.assertEqual(len(used), 1, "the minted challenge must be single-use burned")

    def test_exercise_consumes_a_use_like_any_other(self):
        gid = self._create_anchor_writer_grant()
        with ExitStack() as stack:
            self._run_job(stack)
        self.assertEqual(self._grant_use_count(gid), 1,
                         "the standard decision path consumes a use")


class TestUnavailableExercisePathRefusesAnchor(_Base):
    def test_decision_path_error_refuses_fail_closed(self):
        self._create_anchor_writer_grant()
        with ExitStack() as stack:
            stack.enter_context(mock.patch(
                "backend.src.demo.demo_action.handle_demo_action",
                side_effect=RuntimeError("decision path unavailable"),
            ))
            result = self._run_job(stack)
        self.assertEqual(result["status"], "refused_grant_exercise_unavailable")
        self.assertEqual(self.submit.call_count, 0)
        self.assertEqual(self._anchor_records(), [], "no submitted row on refusal")


if __name__ == "__main__":
    unittest.main()
