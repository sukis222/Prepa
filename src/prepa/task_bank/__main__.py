"""Console search: python -m prepa.task_bank --exam ege --topic 1.1.5 --limit 5"""

import argparse
import asyncio
import io
import sys
from collections.abc import Sequence

from . import AnswerKind, FipiClient, TaskSearch, TaskSourceError, UnknownTopicError
from .text import format_result


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        prog="python -m prepa.task_bank", description="Поиск задач в открытом банке ФИПИ"
    )
    cli.add_argument("--exam", choices=("ege", "oge"), default="ege")
    cli.add_argument(
        "--topic", action="append", default=[], help="код КЭС (1.1.5) или название темы"
    )
    cli.add_argument("--list-topics", nargs="?", const="", metavar="ПОИСК")
    cli.add_argument("--limit", type=int, default=5)
    cli.add_argument("--kind", action="append", default=[], choices=[k.value for k in AnswerKind])
    cli.add_argument("--no-images", action="store_true", help="только задачи без рисунков")
    cli.add_argument("--exclude", action="append", default=[], help="номер уже выданной задачи")
    cli.add_argument("--seed", type=int, help="случайная выборка вместо порядка банка")
    cli.add_argument("--json", action="store_true", help="вывести результат как JSON")
    return cli


async def run(args: argparse.Namespace) -> str:
    async with FipiClient() as client:
        search = TaskSearch(client)
        if args.list_topics is not None:
            topics = await search.topics(args.exam, args.list_topics or None)
            return "\n".join(f"{topic.code} {topic.title}" for topic in topics)
        result = await search.search(
            args.exam,
            args.topic,
            limit=args.limit,
            kinds=[AnswerKind(kind) for kind in args.kind],
            with_images=not args.no_images,
            exclude_ids=args.exclude,
            seed=args.seed,
        )
        return result.model_dump_json(indent=2) if args.json else format_result(result)


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.list_topics is None and not args.topic:
        parser().error("нужен --topic или --list-topics")
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    try:
        print(asyncio.run(run(args)))
    except (UnknownTopicError, TaskSourceError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
