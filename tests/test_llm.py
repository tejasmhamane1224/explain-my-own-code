"""Unit tests for LLM providers, token usage, cost tracking, and budget enforcement."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from emc.llm import (
    AnthropicProvider,
    BudgetExceededError,
    FakeProvider,
    LocalProvider,
    ProviderError,
    TokenUsage,
    compute_cost,
)


class DummyOutput(BaseModel):
    summary: str
    score: int


def test_token_usage_arithmetic() -> None:
    """Verify TokenUsage addition and aggregation."""
    u1 = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    u2 = TokenUsage(prompt_tokens=200, completion_tokens=80, total_tokens=280)
    combined = u1.add(u2)
    assert combined.prompt_tokens == 300
    assert combined.completion_tokens == 130
    assert combined.total_tokens == 430


def test_compute_cost_pricing_tiers() -> None:
    """Verify compute_cost accurate rate calculation across models."""
    # Claude 3.7 Sonnet: $3 / MTok input, $15 / MTok output
    cost_sonnet = compute_cost("claude-3-7-sonnet-latest", 1_000_000, 1_000_000)
    assert cost_sonnet == 18.0

    # Claude 3.5 Haiku: $0.80 / MTok input, $4.00 / MTok output
    cost_haiku = compute_cost("claude-3-5-haiku-latest", 1_000_000, 1_000_000)
    assert cost_haiku == 4.8

    # Claude 3 Opus: $15.00 / MTok input, $75.00 / MTok output
    cost_opus = compute_cost("claude-3-opus-latest", 100_000, 100_000)
    assert cost_opus == 9.0


def test_fake_provider_text_and_structured() -> None:
    """Verify FakeProvider returns canned responses and tracks usage."""
    provider = FakeProvider(model="claude-3-7-sonnet-latest")
    provider.enqueue_text("Hello developer")
    provider.enqueue_structured({"summary": "Valid code", "score": 95})

    res_text = provider.generate_text("Say hello")
    assert res_text.content == "Hello developer"
    assert provider.total_usage.total_tokens > 0

    res_struct = provider.generate_structured("Score diff", schema=DummyOutput)
    assert res_struct.structured is not None
    assert res_struct.structured.summary == "Valid code"
    assert res_struct.structured.score == 95
    assert len(provider.recorded_calls) == 2


def test_fake_provider_simulated_errors() -> None:
    """Verify FakeProvider can simulate provider failures."""
    provider = FakeProvider()
    provider.enqueue_error(ProviderError("Rate limit reached"))

    with pytest.raises(ProviderError, match="Rate limit reached"):
        provider.generate_text("Prompt")


def test_fake_provider_budget_enforcement_tokens() -> None:
    """Verify BudgetExceededError when token budget is exceeded."""
    provider = FakeProvider(token_budget=50)

    # First call within budget
    provider.enqueue_text("Small answer")
    provider.generate_text("Short prompt")

    # Second call exceeds budget
    provider.enqueue_text("This is a very long response that will certainly exceed 50 tokens" * 5)
    with pytest.raises(BudgetExceededError, match="Token budget"):
        provider.generate_text("Another long prompt" * 5)


def test_fake_provider_budget_enforcement_cost() -> None:
    """Verify BudgetExceededError when max cost dollars is exceeded."""
    provider = FakeProvider(
        model="claude-3-opus-latest",
        max_cost_dollars=0.0001,
    )
    provider.enqueue_text("Extensive generated reasoning output" * 50)
    with pytest.raises(BudgetExceededError, match="Maximum cost budget"):
        provider.generate_text("Large diff analysis prompt" * 50)


def test_anthropic_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify AnthropicProvider raises helpful ProviderError when API key is missing."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    provider = AnthropicProvider(api_key=None)

    with pytest.raises(
        ProviderError, match="ANTHROPIC_API_KEY environment variable is not configured"
    ):
        provider.generate_text("Test prompt")


def test_local_provider_unreachable_error() -> None:
    """Verify LocalProvider handles unreachable local server gracefully."""
    provider = LocalProvider(
        endpoint_url="http://127.0.0.1:59999/unreachable",
        timeout_seconds=0.5,
    )
    with pytest.raises(ProviderError, match="unreachable"):
        provider.generate_text("Hello local")
