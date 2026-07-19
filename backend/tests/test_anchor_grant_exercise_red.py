"""RED contract — the anchor job exercises the anchor-writer grant first.

STATUS: RED BY DESIGN. These tests express a decided-but-unbuilt contract
(design intent: the anchor run is itself a granted authority and must be
exercised — and witnessed — like one). Do not make them pass without the
corresponding decision record; open implementation questions are listed at
the bottom of this docstring.

Pinned contract (extends the gate order pinned in test_anchor_job_gate.py):

  1. config gate and same-(workspace, UTC-day) idempotency guard run first,
     unchanged;
  2. THEN the job exercises the anchor-writer grant (subject 'anchor-writer',
     action 'submit_anchor') through the standard decision path — the same
     policy evaluation + signature gate + execution row + chain-linked audit
     event that any /v1/exercise call produces, use-count consumption
     included;
  3. the exercise decision commits BEFORE the head is read, so the exercise
     event sits INSIDE the anchored range — the anchor attests to its own
     authorization (the pattern already accepted for post-anchor events:
     each anchor covers everything before it, the next anchor covers the
     rest);
  4. FAIL-CLOSED: a denied exercise refuses the run — no head read, no
     chain context, no probe, no submitted row, no network call
     (status: refused_grant_exercise_denied);
  5. FAIL-CLOSED: an erroring/unavailable decision path refuses the same
     way (status: refused_grant_exercise_unavailable).

Where this hooks in (audit, 2026-07-19):
  - backend/src/workers/jobs.py::_anchor_audit_chain_sync — the only
    correct insertion point is between the idempotency guard and the
    fail-closed head read (currently both inside the first
    `with maker() as session` block): the exercise must commit before
    `anchor_head(session, workspace_id)` runs.
  - ~/grantlayer-ops/run_anchor.sh calls _anchor_audit_chain_sync directly
    (no HTTP server involved), so a shell-level pre-step would only cover
    manual runs and would NOT be enforced for the arq cron path — the hook
    belongs in the job, not the script.

Open questions (Anton rules; the RED below provisionally pins answers that
are cheap to change):
  a. Caller identity/transport: an anchor-writer API key over HTTP (server
     must be up during anchor runs) vs invoking the decision handler
     in-process (no server dependency, same decision semantics). RED pins
     the in-process seam (backend.src.demo.demo_action.handle_demo_action).
  b. Challenge: should the job mint + consume a single-use challenge like
     the backup hook does (parity), or exercise in legacy mode until
     GRANTLAYER_REQUIRE_CHALLENGE is enforced? RED exercises without a
     challenge.
  c. Allowed-but-anchor-fails: if the exercise is allowed and the submit
     then fails, the chain witnesses an exercised authority for an anchor
     that never confirmed (and a use was consumed). Acceptable, or should
     the exercise reason/metadata mark it submit-pending?
  d. Sequencing with gl-364: the exercise tuple/resource ('cardano/mainnet')
     is read from the live grant; if the endpoint rename merges first,
     nothing here changes — the in-process seam is rename-agnostic.

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
        # init_db provisions the app tables; anchor_records comes from the ORM
        # metadata (alembic-managed in production) and must exist for the job.
        from sqlalchemy import create_engine

        from backend.src.core.orm import Base
        engine = create_engine(f"sqlite:///{self._db_path}")
        Base.metadata.create_all(engine)
        engine.dispose()

    def tearDown(self):
        _cfg.GRANTLAYER_ALLOW_PLAINTEXT_PRIVATE_KEY_FILE = self._orig_plaintext
        _db.DB_PATH_OR_URL = self._orig_db
        _db.DB_PATH = self._orig_db
        try:
            os.unlink(self._db_path)
        except OSError:
            pass

    def _create_anchor_writer_grant(self) -> str:
        """Signed, live anchor-writer grant via the service layer (role=agent)."""
        from backend.src.core.db import get_session_maker
        from backend.src.core.models import Grant
        from backend.src.core.repositories_sqlalchemy import SqlAlchemyGrantRepository
        from backend.src.grants.grant_service import GrantService

        grant = Grant(
            subject_id="anchor-writer",
            role="agent",
            action="submit_anchor",
            resource="cardano/mainnet",
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
                "SELECT action, subject_id, approved, workspace_id FROM audit_events"
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
        self.assertEqual(self.probe.call_count, 0, "no reachability probe on refusal")
        self.assertEqual(self.submit.call_count, 0, "no submit on refusal")
        self.assertEqual(self._anchor_records(), [], "no submitted row on refusal")
        # the denial itself is still witnessed (standard decision path)
        denied = [e for e in self._events()
                  if e.action == "submit_anchor" and e.approved == 0]
        self.assertEqual(len(denied), 1, "the denied exercise must be chain-witnessed")


class TestAllowedExerciseIsInsideAnchoredRange(_Base):
    def test_exercise_event_commits_before_head_read(self):
        gid = self._create_anchor_writer_grant()
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
