"""Deterministic FakeProvider for unit testing and offline development."""

from __future__ import annotations

from typing import Any, Callable, TypeVar

from pydantic import BaseModel

from emc.llm.base import LLMProvider
from emc.llm.models import (
    LLMResponse,
    ProviderError,
    TokenUsage,
    compute_cost,
)

T = TypeVar("T", bound=BaseModel)


class FakeProvider(LLMProvider):
    """Configurable deterministic provider for unit testing and offline development."""

    def __init__(
        self,
        model: str = "fake-claude-3-7-sonnet",
        max_cost_dollars: float | None = None,
        token_budget: int | None = None,
        canned_text: list[str] | None = None,
        canned_structured: list[Any] | None = None,
        simulated_errors: list[Exception] | None = None,
        response_handler: Callable[[str, type[Any] | None], Any] | None = None,
    ) -> None:
        super().__init__(
            name="fake",
            model=model,
            max_cost_dollars=max_cost_dollars,
            token_budget=token_budget,
        )
        self.canned_text: list[str] = list(canned_text or [])
        self.canned_structured: list[Any] = list(canned_structured or [])
        self.simulated_errors: list[Exception] = list(simulated_errors or [])
        self.response_handler = response_handler
        self.recorded_calls: list[dict[str, Any]] = []

    def enqueue_text(self, text: str) -> None:
        """Enqueue a canned text response."""
        self.canned_text.append(text)

    def enqueue_structured(self, obj: Any) -> None:
        """Enqueue a canned structured object or dict."""
        self.canned_structured.append(obj)

    def enqueue_error(self, exc: Exception) -> None:
        """Enqueue a simulated error to be raised on the next call."""
        self.simulated_errors.append(exc)

    def set_handler(self, handler: Callable[[str, type[Any] | None], Any] | None) -> None:
        """Set a dynamic scripted response handler."""
        self.response_handler = handler

    def reset(self) -> None:
        """Reset canned queues, recorded calls, and usage statistics."""
        self.canned_text.clear()
        self.canned_structured.clear()
        self.simulated_errors.clear()
        self.recorded_calls.clear()
        self.total_usage = TokenUsage()
        self.total_cost_usd = 0.0

    def _estimate_tokens(self, prompt: str, completion: str) -> TokenUsage:
        """Estimate token usage deterministically based on character count (~4 chars/token)."""
        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = max(1, len(completion) // 4)
        return TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

    def generate_text(
        self,
        prompt: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse[str]:
        """Generate canned or scripted text response."""
        call_record = {
            "method": "generate_text",
            "prompt": prompt,
            "system": system,
            "kwargs": kwargs,
        }
        self.recorded_calls.append(call_record)

        if self.simulated_errors:
            err = self.simulated_errors.pop(0)
            raise err

        if self.response_handler is not None:
            content = str(self.response_handler(prompt, None))
        elif self.canned_text:
            content = self.canned_text.pop(0)
        else:
            content = f"Deterministic response to: {prompt[:30]}..."

        usage = self._estimate_tokens(prompt, content)
        cost = compute_cost(self.model, usage.prompt_tokens, usage.completion_tokens)

        self.check_budget(projected_tokens=usage.total_tokens, projected_cost=cost)
        self.record_usage(usage, cost)

        return LLMResponse(
            content=content,
            structured=content,
            usage=usage,
            cost_usd=cost,
            model=self.model,
            cached=False,
            raw_response={"mock": True, "text": content},
        )

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        system: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse[T]:
        """Generate canned or scripted structured response validated against schema."""
        call_record = {
            "method": "generate_structured",
            "prompt": prompt,
            "schema": schema,
            "system": system,
            "kwargs": kwargs,
        }
        self.recorded_calls.append(call_record)

        if self.simulated_errors:
            err = self.simulated_errors.pop(0)
            raise err

        raw_obj: Any
        if self.response_handler is not None:
            raw_obj = self.response_handler(prompt, schema)
        elif self.canned_structured:
            raw_obj = self.canned_structured.pop(0)
        else:
            raise ProviderError(
                f"No canned structured response or handler available for schema {schema.__name__}"
            )

        structured: T
        if isinstance(raw_obj, schema):
            structured = raw_obj
        elif isinstance(raw_obj, dict):
            structured = schema.model_validate(raw_obj)
        elif isinstance(raw_obj, BaseModel):
            structured = schema.model_validate(raw_obj.model_dump())
        elif isinstance(raw_obj, str):
            structured = schema.model_validate_json(raw_obj)
        else:
            raise ProviderError(f"Cannot cast response {raw_obj!r} to schema {schema.__name__}")

        content_str = (
            structured.model_dump_json()
            if hasattr(structured, "model_dump_json")
            else str(structured)
        )
        usage = self._estimate_tokens(prompt, content_str)
        cost = compute_cost(self.model, usage.prompt_tokens, usage.completion_tokens)

        self.check_budget(projected_tokens=usage.total_tokens, projected_cost=cost)
        self.record_usage(usage, cost)

        return LLMResponse(
            content=content_str,
            structured=structured,
            usage=usage,
            cost_usd=cost,
            model=self.model,
            cached=False,
            raw_response={"mock": True, "structured": content_str},
        )
