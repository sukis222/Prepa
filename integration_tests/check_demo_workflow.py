"""Opt-in smoke check: PGDATABASE must start with prepa_test; never uses Telegram/LLM.

Run inside the bot image with its PG* environment and an isolated test database.
"""

import asyncio
import hashlib
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.conninfo import conninfo_to_dict

from prepa.bot.service import DialogService
from prepa.db.config import database_dsn
from prepa.db.migrate import migrate
from prepa.db.repository import PostgresRepository
from prepa.documents.delivery import DemoDocuments
from prepa.preparation.demo import DemoBackend
from prepa.preparation.jobs import JobQueue
from prepa.preparation.worker import process_one


def main():
    dsn = database_dsn()
    if not conninfo_to_dict(dsn).get("dbname", "").startswith("prepa_test"):
        raise SystemExit("Requires an isolated prepa_test* database")
    migrate(dsn, Path("migrations"))
    migrate(dsn, Path("migrations"))
    teacher = uuid4().int % (2**50) + 1
    repo = PostgresRepository(dsn)
    queue = JobQueue(dsn, "demo")

    async def say(text, user=teacher):
        return await DialogService(None, repository=repo, job_mode="demo").respond(user, text)

    async def deliver(user, reply):
        assert user == teacher
        assert "ДЕМО" in reply.text
        assert len(reply.attachments) == 2

    async def scenario():
        await repo.check()
        for text in (
            "/add_student",
            "Synthetic demo pupil",
            "9 ОГЭ 1",
            "-",
            "/lesson",
            "1",
            "Кинематика",
            "60 1 4 2 20",
            "-",
        ):
            await say(text)
        assert await queue.claim() is None
        assert "очередь" in (await say("/confirm")).text
        assert "Нет запроса" in (await say("/confirm")).text
        assert "Сначала" in (await say("/result", teacher + 1)).text
        # Simulate death after claim: a different worker must reclaim after lease expiry.
        abandoned = await queue.claim()
        assert abandoned is not None and await queue.claim() is None
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "UPDATE preparation_jobs SET lease_until=now()-interval '1 second' "
                "WHERE teacher_id=%s",
                (teacher,),
            )
        assert await process_one(
            JobQueue(dsn, "demo"), DemoBackend(), DemoDocuments(), deliver, None
        )
        assert not await queue.finish(abandoned, error="late stale worker")
        reply = await say("/result")
        assert len(reply.attachments) == 2
        digests = [hashlib.sha256(f.content).hexdigest() for f in reply.attachments]
        assert digests == [
            hashlib.sha256(f.content).hexdigest() for f in (await say("/result 1")).attachments
        ]
        for text in ("/edit", "Динамика", "60 1 4 0 0", "-", "/confirm"):
            await say(text)
        job = await queue.claim()
        assert job.brief.version == 2
        await queue.finish(job, error="synthetic_failure")
        assert "не удалась" in (await say("/result")).text
        assert "очередь" in (await say("/retry")).text
        assert await process_one(queue, DemoBackend(), DemoDocuments(), deliver, None)
        assert "v2" in (await say("/result")).text
        assert digests == [
            hashlib.sha256(f.content).hexdigest() for f in (await say("/result 1")).attachments
        ]
        # Bound automatic recovery; explicit /retry is still available.
        for text in ("/edit", "Динамика", "60 1 4 0 0", "-", "/confirm"):
            await say(text)
        assert await queue.claim() is not None
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "UPDATE preparation_jobs SET attempts=3, "
                "lease_until=now()-interval '1 second' "
                "WHERE teacher_id=%s AND status='running'",
                (teacher,),
            )
        assert await queue.claim() is None
        assert "не удалась" in (await say("/result")).text
        print(
            "PASS: confirmation, queue, lease recovery, fencing, files, isolation, versions, retry"
        )

    asyncio.run(scenario())


if __name__ == "__main__":
    main()
