# tests/test_migrations.py — Slice 4 increment 6: alembic chain integrity.
from alembic.config import Config
from alembic.script import ScriptDirectory


def _script():
    import os
    cfg = Config()
    cfg.set_main_option("script_location", os.path.join(
        os.path.dirname(__file__), "..", "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_migration_chain_is_linear_and_complete():
    script = _script()
    revisions = list(script.walk_revisions())
    assert [r.revision for r in revisions] == [
        "0003_users", "0002_qr_seen", "0001_initial"]  # walk is newest-first
    heads = script.get_heads()
    assert len(heads) == 1 and heads[0] == "0003_users"


def test_upgrade_downgrade_cycle_on_scratch_sqlite(tmp_path, monkeypatch):
    from alembic.config import Config as AlembicConfig
    from alembic import command
    import os
    import app.config as config_module
    db = tmp_path / "migcycle.db"
    # alembic/env.py reads the global settings object: point it at scratch.
    monkeypatch.setattr(config_module.settings, "DATABASE_URL", f"sqlite:///{db}")
    cfg = AlembicConfig()
    cfg.set_main_option("script_location", os.path.join(
        os.path.dirname(__file__), "..", "alembic"))
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    import sqlite3
    tables = sorted(r[0] for r in sqlite3.connect(db).execute(
        "SELECT name FROM sqlite_master WHERE type='table'"))
    for expected in ("scans", "audit_log", "qr_seen", "users", "sessions"):
        assert expected in tables, tables
