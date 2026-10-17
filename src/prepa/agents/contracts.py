"""Small provider boundary; the shared llm/ client supplies this implementation."""

from typing import Any, Protocol


class StructuredLLM(Protocol):
    async def generate(
        self, *, system_prompt: str, user_prompt: str, response_schema: dict[str, Any]
    ) -> str | dict[str, Any]:
        """Return a JSON object or JSON string; never Markdown or a document template.

        The adapter handles credentials, model selection and provider errors. Pass the
        supplied JSON Schema as the provider's response format when supported.
        """
        ...
