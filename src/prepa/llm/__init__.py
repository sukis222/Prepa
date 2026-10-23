"""Shared provider adapter."""

from .openrouter import LLMError, OpenRouterLLM, OpenRouterSettings

__all__ = ["LLMError", "OpenRouterLLM", "OpenRouterSettings"]
