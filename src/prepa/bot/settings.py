"""Configuration without secrets in repr or validation messages."""

import os
from dataclasses import dataclass, field

from prepa.db.config import database_dsn


@dataclass(frozen=True)
class Settings:
    token: str = field(repr=False)
    teacher_ids: frozenset[int] | None
    database_url: str = field(default="", repr=False)

    preparation_mode: str = "off"
    source_corpus_path: str = ""
    source_provider: str = "reshai"

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise ValueError("Задайте TELEGRAM_BOT_TOKEN в .env")
        mode = os.environ.get("PREPARATION_MODE", "off").strip()
        if mode not in ("off", "demo", "real"):
            raise ValueError("PREPARATION_MODE: off, demo или real")
        provider = os.environ.get("SOURCE_PROVIDER", "reshai").strip()
        if provider not in ("reshai", "local"):
            raise ValueError("SOURCE_PROVIDER: reshai или local")
        allowed_ids = os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").strip()
        if allowed_ids == "*":
            return cls(
                token=token,
                teacher_ids=None,
                database_url=database_dsn(),
                preparation_mode=mode,
                source_corpus_path=os.environ.get("SOURCE_CORPUS_PATH", "").strip(),
                source_provider=provider,
            )
        try:
            ids = frozenset(int(value.strip()) for value in allowed_ids.split(","))
        except ValueError:
            raise ValueError(
                "Задайте TELEGRAM_ALLOWED_USER_IDS: числовые ID через запятую"
            ) from None
        if any(value <= 0 for value in ids):
            raise ValueError("TELEGRAM_ALLOWED_USER_IDS должны быть положительными")
        return cls(
            token=token,
            teacher_ids=ids,
            database_url=database_dsn(),
            preparation_mode=mode,
            source_corpus_path=os.environ.get("SOURCE_CORPUS_PATH", "").strip(),
            source_provider=provider,
        )
