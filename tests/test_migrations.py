"""Migration runner error paths, without connecting to PostgreSQL."""

from unittest.mock import MagicMock

import pytest

from prepa.db import migrate


def test_no_files(tmp_path):
    with pytest.raises(ValueError, match="No migration"):
        migrate.migrate("unused", tmp_path)


def test_apply_once_and_reject_future_version(tmp_path, monkeypatch):
    (tmp_path / "001_test.sql").write_text("-- test\nBEGIN;\nSELECT 1;\nCOMMIT;\n")
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = False
    cursor = conn.execute.return_value
    cursor.fetchone.return_value = (None,)
    monkeypatch.setattr(migrate.psycopg, "connect", MagicMock(return_value=conn))
    migrate.migrate("unused", tmp_path)
    executed = [c.args[0] for c in conn.execute.call_args_list]
    assert "-- test\nSELECT 1;\n" in executed
    conn.transaction.assert_called_once()
    conn.execute.reset_mock()
    cursor.fetchone.return_value = ("schema_migrations",)
    cursor.fetchall.return_value = [(1,)]
    migrate.migrate("unused", tmp_path)
    assert not any("SELECT 1;" in c.args[0] for c in conn.execute.call_args_list)
    cursor.fetchall.return_value = [(2,)]
    with pytest.raises(ValueError, match="newer"):
        migrate.migrate("unused", tmp_path)


def test_cli_does_not_print_dsn(monkeypatch):
    monkeypatch.setattr("sys.argv", ["migrate", "--directory", "migrations"])
    monkeypatch.setattr(migrate, "load_dotenv", MagicMock())
    monkeypatch.setattr(migrate, "database_dsn", lambda: "secret")
    apply = MagicMock()
    monkeypatch.setattr(migrate, "migrate", apply)
    migrate.main()
    apply.assert_called_once()
    apply.side_effect = RuntimeError("secret")
    with pytest.raises(SystemExit) as error:
        migrate.main()
    assert "secret" not in str(error.value)
