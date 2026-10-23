"""Database configuration shared by the bot and migration command."""

import os

from psycopg.conninfo import make_conninfo


def database_dsn() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url
    if os.environ.get("PGHOST"):
        return make_conninfo(
            host=os.environ["PGHOST"],
            port=os.environ.get("PGPORT", "5432"),
            dbname=os.environ.get("PGDATABASE", "prepa"),
            user=os.environ.get("PGUSER", "prepa"),
            password=os.environ.get("PGPASSWORD", ""),
        )
    raise ValueError("Задайте DATABASE_URL или параметры PGHOST/PGDATABASE/PGUSER/PGPASSWORD")
