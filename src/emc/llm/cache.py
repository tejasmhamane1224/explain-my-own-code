"""Disk-backed caching for LLM completions keyed by diff hash, prompt hash, and model."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from emc.llm.base import LLMProvider
from emc.llm.models import (
    LLMResponse,
    TokenUsage,
)

T = TypeVar("T", bound=BaseModel)


class DiskCache:
    """Persistent filesystem cache storing LLM responses under .emc/cache/."""

    def __init__(self, cache_dir: Path | str = ".emc/cache") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def compute_hash(text: str) -> str:
        """Compute SHA256 hex digest for arbitrary string."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def compute_key(self, diff_hash: str, prompt: str, model: str) -> str:
        """Derive deterministic cache key from diff hash, prompt content, and model."""
        prompt_hash = self.compute_hash(prompt)
        combined = f"{diff_hash}:{model.strip().lower()}:{prompt_hash}"
        return self.compute_hash(combined)

    def _get_entry_path(self, diff_hash: str, prompt: str, model: str) -> Path:
        key = self.compute_key(diff_hash, prompt, model)
        return self.cache_dir / f"{key}.json"

    def has(self, diff_hash: str, prompt: str, model: str) -> bool:
        """Check if an uncorrupted cache entry exists."""
        entry_path = self._get_entry_path(diff_hash, prompt, model)
        return entry_path.is_file()

    def get(self, diff_hash: str, prompt: str, model: str) -> dict[str, Any] | None:
        """Retrieve cached entry dict or None if absent or corrupt."""
        entry_path = self._get_entry_path(diff_hash, prompt, model)
        if not entry_path.is_file():
            return None
        try:
            with entry_path.open("r", encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
                return data
        except Exception:
            return None

    def set(
        self,
        diff_hash: str,
        prompt: str,
        model: str,
        content: str,
        structured_data: Any | None = None,
        usage: TokenUsage | None = None,
        cost_usd: float = 0.0,
    ) -> Path:
        """Write entry to disk cache."""
        entry_path = self._get_entry_path(diff_hash, prompt, model)
        payload = {
            "key": entry_path.stem,
            "diff_hash": diff_hash,
            "model": model,
            "prompt_hash": self.compute_hash(prompt),
            "content": content,
            "structured": structured_data,
            "usage": (usage or TokenUsage()).model_dump(),
            "cost_usd": cost_usd,
            "cached_at": time.time(),
        }
        entry_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return entry_path

    def clear(self) -> int:
        """Delete all cached entries, returning number of files deleted."""
        count = 0
        if self.cache_dir.exists():
            for item in self.cache_dir.glob("*.json"):
                try:
                    item.unlink()
                    count += 1
                except Exception:
                    pass
        return count


class CachedLLMProvider(LLMProvider):
    """Decorator/wrapper adding disk caching and budget enforcement around an LLMProvider."""

    def __init__(
        self,
        provider: LLMProvider,
        cache: DiskCache | None = None,
        cache_dir: Path | str = ".emc/cache",
        diff_hash: str = "default_diff",
    ) -> None:
        super().__init__(
            name=f"cached-{provider.name}",
            model=provider.model,
            max_cost_dollars=provider.max_cost_dollars,
            token_budget=provider.token_budget,
        )
        self.provider = provider
        self.cache = cache or DiskCache(cache_dir=cache_dir)
        self.diff_hash = diff_hash

    def set_diff_hash(self, diff_hash: str) -> None:
        """Set current diff hash context for cache keys."""
        self.diff_hash = diff_hash

    def generate_text(
        self,
        prompt: str,
        system: str | None = None,
        diff_hash: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse[str]:
        """Generate text with disk cache lookup."""
        active_diff_hash = diff_hash or self.diff_hash

        cached_entry = self.cache.get(active_diff_hash, prompt, self.model)
        if cached_entry is not None:
            usage_data = cached_entry.get("usage", {})
            return LLMResponse(
                content=cached_entry.get("content", ""),
                structured=cached_entry.get("content", ""),
                usage=TokenUsage(**usage_data),
                cost_usd=0.0,
                model=self.model,
                cached=True,
                raw_response=cached_entry,
            )

        self.check_budget()
        response = self.provider.generate_text(prompt, system=system, **kwargs)

        self.cache.set(
            diff_hash=active_diff_hash,
            prompt=prompt,
            model=self.model,
            content=response.content,
            structured_data=response.content,
            usage=response.usage,
            cost_usd=response.cost_usd,
        )

        self.record_usage(response.usage, response.cost_usd)
        return response

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        system: str | None = None,
        diff_hash: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse[T]:
        """Generate structured data with disk cache lookup."""
        active_diff_hash = diff_hash or self.diff_hash

        cached_entry = self.cache.get(active_diff_hash, prompt, self.model)
        if cached_entry is not None and cached_entry.get("structured") is not None:
            raw_struct = cached_entry["structured"]
            structured_obj: T | None = None
            try:
                if isinstance(raw_struct, schema):
                    structured_obj = raw_struct
                elif isinstance(raw_struct, str):
                    structured_obj = schema.model_validate_json(raw_struct)
                else:
                    structured_obj = schema.model_validate(raw_struct)
            except Exception:
                structured_obj = None

            if structured_obj is not None:
                usage_data = cached_entry.get("usage", {})
                return LLMResponse(
                    content=cached_entry.get("content", ""),
                    structured=structured_obj,
                    usage=TokenUsage(**usage_data),
                    cost_usd=0.0,
                    model=self.model,
                    cached=True,
                    raw_response=cached_entry,
                )

        self.check_budget()
        response = self.provider.generate_structured(prompt, schema=schema, system=system, **kwargs)

        struct_dump = (
            response.structured.model_dump()
            if isinstance(response.structured, BaseModel)
            else response.structured
        )

        self.cache.set(
            diff_hash=active_diff_hash,
            prompt=prompt,
            model=self.model,
            content=response.content,
            structured_data=struct_dump,
            usage=response.usage,
            cost_usd=response.cost_usd,
        )

        self.record_usage(response.usage, response.cost_usd)
        return response
