"""
tests/test_govt_sync_poll_lock.py — regression test for the advisory lock
added around main.py's _run_govt_sync_poll() (govt-sync fixation plan, Step 1).

Confirmed via code trace (see the resilience review, section J1) that this
sweep runs unconditionally, with no other leader-election, inside every
worker process that imports main.py — backend's 2 uvicorn workers AND
backend_govt_live's own separate single worker (3 processes total). This
test proves the Python control flow around the new lock is correct:
poll_all_pending() runs when the lock is acquired, is skipped entirely when
it isn't, the lock is only ever released by whichever call actually
acquired it (never unlocking a lock another process legitimately holds),
and a failure inside poll_all_pending() still releases the lock rather than
leaking it for the rest of that process's lifetime.

Real Postgres session-scoped advisory-lock semantics (does a second real
connection actually get refused while the first holds it, does the lock
clear automatically on disconnect) are validated separately against a real
local Postgres instance, not re-proven here against SQLite's fake — SQLite
can't express real cross-connection locking semantics, only the branching
logic that reacts to whatever pg_try_advisory_lock returns.
"""
import os
import sys
from unittest.mock import MagicMock, patch

os.environ["JWT_SECRET"] = "test-secret-key-32-characters-minimum-ok"
os.environ["DATABASE_URL"] = "sqlite:///./test_govt_sync_poll_lock.db"
os.environ["ENV"] = "test"
os.environ["OPENAI_API_KEY"] = "sk-test-fake-key-for-testing"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import event
from sqlalchemy.engine import Engine


@event.listens_for(Engine, "connect")
def _sqlite_register_pg_lock_functions(dbapi_connection, connection_record):
    # main.py's own module-level startup code calls pg_try_advisory_lock
    # during import (the migration lock) — SQLite needs this fake in place
    # before `import main` runs, same fixture every other govt_sync test
    # file in this suite already registers.
    try:
        dbapi_connection.create_function("pg_try_advisory_lock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_advisory_unlock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_try_advisory_xact_lock", 1, lambda _key: 1)
    except Exception:
        pass


import main  # noqa: E402  (env vars + lock-function fixture must be set up first)


def _unlock_calls(fake_conn):
    # str(call(...)) reprs each arg rather than compiling it, so a TextClause
    # shows up as "<sqlalchemy.sql.elements.TextClause object at 0x...>", not
    # its SQL text — inspect the actual first positional arg (the TextClause
    # itself) via str() directly, which does compile it, instead.
    matches = []
    for c in fake_conn.execute.call_args_list:
        args, _kwargs = c
        if args and "pg_advisory_unlock" in str(args[0]):
            matches.append(c)
    return matches


def test_poll_runs_when_lock_acquired():
    fake_conn = MagicMock()
    fake_conn.execute.return_value.scalar.return_value = True  # pg_try_advisory_lock succeeds

    with patch.object(main, "engine") as mock_engine, \
         patch("modules.govt_sync.poller.poll_all_pending") as mock_poll:
        mock_engine.connect.return_value = fake_conn
        main._run_govt_sync_poll()

    mock_poll.assert_called_once()
    assert len(_unlock_calls(fake_conn)) == 1
    fake_conn.close.assert_called_once()


def test_poll_skipped_when_lock_held_elsewhere():
    fake_conn = MagicMock()
    fake_conn.execute.return_value.scalar.return_value = False  # another process holds it

    with patch.object(main, "engine") as mock_engine, \
         patch("modules.govt_sync.poller.poll_all_pending") as mock_poll:
        mock_engine.connect.return_value = fake_conn
        main._run_govt_sync_poll()

    mock_poll.assert_not_called()
    # Must NOT attempt to unlock a lock this process never actually acquired.
    assert len(_unlock_calls(fake_conn)) == 0
    fake_conn.close.assert_called_once()


def test_poll_still_releases_lock_if_poll_all_pending_raises():
    fake_conn = MagicMock()
    fake_conn.execute.return_value.scalar.return_value = True

    with patch.object(main, "engine") as mock_engine, \
         patch("modules.govt_sync.poller.poll_all_pending", side_effect=RuntimeError("boom")):
        mock_engine.connect.return_value = fake_conn
        main._run_govt_sync_poll()  # must not raise — outer except catches it

    assert len(_unlock_calls(fake_conn)) == 1
    fake_conn.close.assert_called_once()


def test_poll_survives_connect_failure_without_raising():
    with patch.object(main, "engine") as mock_engine, \
         patch("modules.govt_sync.poller.poll_all_pending") as mock_poll:
        mock_engine.connect.side_effect = RuntimeError("db unreachable")
        main._run_govt_sync_poll()  # must not raise

    mock_poll.assert_not_called()


def test_poll_uses_dedicated_lock_key_distinct_from_migration_lock():
    assert main._GOVT_SYNC_POLL_LOCK_KEY == 77772030
    assert main._GOVT_SYNC_POLL_LOCK_KEY != 77772024
