"""Local model provider stub (Ollama / llama.cpp / local server)."""

from __future__ import annotations

import json
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from emc.llm.base import LLMProvider
from emc.llm.models import (
    LLMResponse,
    ProviderError,
    TokenUsage,
)

T = TypeVar("T", bound=BaseModel)

DEFAULT_LOCAL_ENDPOINT = "http://localhost:11434/api/generate"


class LocalProvider(LLMProvider):
    """Local LLM provider stub supporting Ollama, llama.cpp, or local HTTP servers."""

    def __init__(
        self,
        endpoint_url: str = DEFAULT_LOCAL_ENDPOINT,
        model: str = "llama3",
        max_cost_dollars: float | None = None,
        token_budget: int | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        super().__init__(
            name="local",
            model=model,
            max_cost_dollars=max_cost_dollars,
            token_budget=token_budget,
        )
        self.endpoint_url = endpoint_url
        self.timeout_seconds = timeout_seconds

    def _estimate_tokens(self, prompt: str, completion: str) -> TokenUsage:
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
        """Send prompt to local model HTTP endpoint."""
        self.check_budget()

        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system or "",
            "stream": False,
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                res = client.post(self.endpoint_url, json=payload)
        except Exception as exc:
            raise ProviderError(
                f"Local LLM endpoint at {self.endpoint_url} is unreachable: {exc}. "
                "Ensure Ollama or local LLM server is running."
            ) from exc

        if res.status_code != 200:
            raise ProviderError(f"Local LLM returned HTTP {res.status_code}: {res.text}")

        data = res.json()
        response_text = data.get("response", "").strip()

        usage = self._estimate_tokens(prompt, response_text)
        cost = 0.0

        self.record_usage(usage, cost)

        return LLMResponse(
            content=response_text,
            structured=response_text,
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
        **kwargs: Any,
    ) -> LLMResponse[T]:
        """Generate structured response using JSON format constraint on local model."""
        self.check_budget()

        schema_json = schema.model_json_schema()
        instruction = (
            f"\nYou MUST respond ONLY with a valid JSON object strictly matching this schema:\n"
            f"{json.dumps(schema_json)}\n"
            f"Do not include markdown codeblocks or any additional commentary."
        )
        full_prompt = f"{prompt}\n{instruction}"

        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "system": system or "",
            "format": "json",
            "stream": False,
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                res = client.post(self.endpoint_url, json=payload)
        except Exception as exc:
            raise ProviderError(
                f"Local LLM endpoint at {self.endpoint_url} is unreachable: {exc}. "
                "Ensure Ollama or local LLM server is running."
            ) from exc

        if res.status_code != 200:
            raise ProviderError(f"Local LLM returned HTTP {res.status_code}: {res.text}")

        data = res.json()
        raw_text = data.get("response", "").strip()

        try:
            parsed = json.loads(raw_text)
            structured = schema.model_validate(parsed)
        except Exception as exc:
            raise ProviderError(
                f"Failed to parse local LLM response into schema {schema.__name__}: {exc}. "
                f"Raw output: {raw_text[:200]}"
            ) from exc

        usage = self._estimate_tokens(full_prompt, raw_text)
        cost = 0.0

        self.record_usage(usage, cost)

        return LLMResponse(
            content=raw_text,
            structured=structured,
            usage=usage,
            cost_usd=cost,
            model=self.model,
            cached=False,
            raw_response=data,
        )
