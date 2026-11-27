"""Dispatch resolved requests to independently supplied agent handlers."""

from collections.abc import Awaitable, Callable, Mapping
from enum import StrEnum


class AgentAction(StrEnum):
    """Actions that the orchestrator can request from the agents."""

    CHECK_HOMEWORK = "check_homework"
    BUILD_LESSON = "build_lesson"
    BUILD_ASSESSMENT = "build_assessment"
    GIVE_HINT = "give_hint"
    SUMMARIZE_LESSON = "summarize_lesson"


class AgentRouter[RequestT, ResultT]:
    """Route each resolved action to its configured asynchronous handler."""

    def __init__(
        self, handlers: Mapping[AgentAction, Callable[[RequestT], Awaitable[ResultT]]]
    ) -> None:
        self._handlers = dict(handlers)

    async def dispatch(self, action: AgentAction, request: RequestT) -> ResultT:
        """Pass the request to the handler. Raise KeyError for an unconfigured action."""
        return await self._handlers[action](request)
