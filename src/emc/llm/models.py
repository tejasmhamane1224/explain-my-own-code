"""Data models, token usage, and pricing structures for LLM providers."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

# Pricing in USD per 1,000,000 tokens (prompt_cost, completion_cost)
# Based on standard Anthropic published pricing
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # Claude 3.7 Sonnet
    "claude-3-7-sonnet-latest": (3.00, 15.00),
    "claude-3-7-sonnet-20250219": (3.00, 15.00),
    # Claude 3.5 Sonnet
    "claude-3-5-sonnet-latest": (3.00, 15.00),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-5-sonnet-20240620": (3.00, 15.00),
    # Claude 3.5 Haiku
    "claude-3-5-haiku-latest": (0.80, 4.00),
    "claude-3-5-haiku-20241022": (0.80, 4.00),
    # Claude 3 Opus
    "claude-3-opus-latest": (15.00, 75.00),
    "claude-3-opus-20240229": (15.00, 75.00),
    # Claude 3 Haiku
    "claude-3-haiku-20240307": (0.25, 1.25),
}

DEFAULT_PRICING: tuple[float, float] = (3.00, 15.00)


def compute_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Compute estimated USD cost for a given model and token usage.

    Returns cost rounded to 6 decimal places.
    """
    input_rate, output_rate = MODEL_PRICING.get(model.lower(), DEFAULT_PRICING)
    cost = (prompt_tokens / 1_000_000.0 * input_rate) + (
        completion_tokens / 1_000_000.0 * output_rate
    )
    return round(cost, 6)


class TokenUsage(BaseModel):
    """Token consumption record for an LLM call or accumulated session."""

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)

    def add(self, other: TokenUsage) -> TokenUsage:
        """Return new TokenUsage with combined token counts."""
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


class LLMResponse(BaseModel, Generic[T]):
    """Standardized response from an LLM provider."""

    content: str
    structured: T | None = None
    usage: TokenUsage = Field(default_factory=TokenUsage)
    cost_usd: float = Field(default=0.0, ge=0.0)
    model: str
    cached: bool = False
    raw_response: dict[str, Any] | None = None


class ProviderError(Exception):
    """Base exception for LLM provider errors."""


class BudgetExceededError(ProviderError):
    """Raised when an LLM call would exceed the configured cost or token budget."""

    def __init__(
        self,
        message: str,
        current_cost: float,
        max_cost: float | None = None,
        current_tokens: int = 0,
        token_budget: int | None = None,
    ) -> None:
        super().__init__(message)
        self.current_cost = current_cost
        self.max_cost = max_cost
        self.current_tokens = current_tokens
        self.token_budget = token_budget
