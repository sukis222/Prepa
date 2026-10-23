"""Apply repository SQL migrations atomically, once, without printing credentials."""

import argparse
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from prepa.db.config import database_dsn


def migrate(dsn: str, directory: Path) -> None:
    files = sorted(directory.glob("[0-9][0-9][0-9]_*.sql"))
    if not files:
        raise ValueError("No migration files found")
    with psycopg.connect(dsn, connect_timeout=10, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(780723172)")
        row = conn.execute("SELECT to_regclass('public.schema_migrations')").fetchone()
        applied = (
            {r[0] for r in conn.execute("SELECT version FROM schema_migrations").fetchall()}
            if row and row[0]
            else set()
        )
        known = {int(path.name.split("_")[0]) for path in files}
        if applied - known:
            raise ValueError("Database schema is newer than this application")
        for path in files:
            version = int(path.name.split("_")[0])
            if version not in applied:
                # Files also work directly in psql; the runner owns the transaction here.
                sql = path.read_text().replace("\nBEGIN;\n", "\n").removesuffix("COMMIT;\n")
                with conn.transaction():
                    conn.execute(sql, prepare=False)
                print(f"Applied migration {version}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=Path("migrations"))
    args = parser.parse_args()
    load_dotenv()
    try:
        migrate(database_dsn(), args.directory)
    except Exception as error:
        raise SystemExit(
            f"Migration failed ({type(error).__name__}); check DB and SQL files"
        ) from None


if __name__ == "__main__":
    main()
