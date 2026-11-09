"""Anthropic Messages API provider implementation with structured tool-use."""

from __future__ import annotations

import json
import os
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from emc.llm.base import LLMProvider
from emc.llm.models import (
    LLMResponse,
    ProviderError,
    TokenUsage,
    compute_cost,
)

T = TypeVar("T", bound=BaseModel)

DEFAULT_ANTHROPIC_MODEL = "claude-3-7-sonnet-latest"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"


class AnthropicProvider(LLMProvider):
    """Anthropic Messages API client supporting tool-use structured output and cost tracking."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_cost_dollars: float | None = None,
        token_budget: int | None = None,
        timeout_seconds: float = 60.0,
        base_url: str = ANTHROPIC_API_URL,
    ) -> None:
        resolved_model = (model or os.getenv("EMC_MODEL") or DEFAULT_ANTHROPIC_MODEL).strip()
        super().__init__(
            name="anthropic",
            model=resolved_model,
            max_cost_dollars=max_cost_dollars,
            token_budget=token_budget,
        )
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.timeout_seconds = timeout_seconds
        self.base_url = base_url

    def _get_api_key(self) -> str:
        """Retrieve and validate the configured Anthropic API key."""
        key = self.api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key or not key.strip():
            raise ProviderError(
                "ANTHROPIC_API_KEY environment variable is not configured. "
                "Set ANTHROPIC_API_KEY or use FakeProvider for offline development."
            )
        return key.strip()

    def _get_headers(self) -> dict[str, str]:
        """Construct Anthropic API request headers."""
        return {
            "x-api-key": self._get_api_key(),
            "anthropic-version": ANTHROPIC_API_VERSION,
            "content-type": "application/json",
        }

    def generate_text(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> LLMResponse[str]:
        """Generate freeform text completion from Anthropic Messages API."""
        self.check_budget()

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        if system:
            payload["system"] = system

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                res = client.post(
                    self.base_url,
                    headers=self._get_headers(),
                    json=payload,
                )
        except Exception as exc:
            raise ProviderError(f"Network error calling Anthropic API: {exc}") from exc

        if res.status_code != 200:
            raise ProviderError(f"Anthropic API error (status {res.status_code}): {res.text}")

        data = res.json()
        content_blocks = data.get("content", [])
        text_parts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
        completion_text = "".join(text_parts).strip()

        usage_data = data.get("usage", {})
        prompt_tokens = int(usage_data.get("input_tokens", 0))
        completion_tokens = int(usage_data.get("output_tokens", 0))
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
        cost = compute_cost(self.model, usage.prompt_tokens, usage.completion_tokens)

        self.record_usage(usage, cost)

        return LLMResponse(
            content=completion_text,
            structured=completion_text,
            usage=usage,
            cost_usd=cost,
            model=self.model,
            cached=False,
            raw_response=data,
        )

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> LLMResponse[T]:
        """Generate structured response validated against schema using Anthropic Tool-Use."""
        self.check_budget()

        tool_name = f"record_{schema.__name__.lower()}"
        tool_schema = schema.model_json_schema()

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "tools": [
                {
                    "name": tool_name,
                    "description": f"Structured output conforming to {schema.__name__}",
                    "input_schema": tool_schema,
                }
            ],
            "tool_choice": {"type": "tool", "name": tool_name},
        }
        if system:
            payload["system"] = system

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                res = client.post(
                    self.base_url,
                    headers=self._get_headers(),
                    json=payload,
                )
        except Exception as exc:
            raise ProviderError(f"Network error calling Anthropic API: {exc}") from exc

        if res.status_code != 200:
            raise ProviderError(f"Anthropic API error (status {res.status_code}): {res.text}")

        data = res.json()
        content_blocks = data.get("content", [])
        tool_input: dict[str, Any] | None = None

        for block in content_blocks:
            if block.get("type") == "tool_use" and block.get("name") == tool_name:
                tool_input = block.get("input")
                break

        if tool_input is None:
            text_blocks = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
            raw_text = "".join(text_blocks).strip()
            try:
                tool_input = json.loads(raw_text)
            except Exception:
                raise ProviderError(
                    f"Anthropic API did not return tool_use block for {tool_name}: {data}"
                )

        try:
            structured = schema.model_validate(tool_input)
        except Exception as exc:
            raise ProviderError(
                f"Failed to validate response against {schema.__name__}: {exc}"
            ) from exc

        usage_data = data.get("usage", {})
        prompt_tokens = int(usage_data.get("input_tokens", 0))
        completion_tokens = int(usage_data.get("output_tokens", 0))
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
        cost = compute_cost(self.model, usage.prompt_tokens, usage.completion_tokens)

        self.record_usage(usage, cost)

        content_str = structured.model_dump_json()

        return LLMResponse(
            content=content_str,
            structured=structured,
            usage=usage,
            cost_usd=cost,
            model=self.model,
            cached=False,
            raw_response=data,
        )
