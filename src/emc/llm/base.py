"""Abstract base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel

from emc.llm.models import (
    BudgetExceededError,
    LLMResponse,
    TokenUsage,
)

T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    """Abstract interface for LLM providers supporting structured outputs and cost tracking."""

    def __init__(
        self,
        name: str,
        model: str,
        max_cost_dollars: float | None = None,
        token_budget: int | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self.max_cost_dollars = max_cost_dollars
        self.token_budget = token_budget
        self.total_usage = TokenUsage()
        self.total_cost_usd = 0.0

    def check_budget(self, projected_tokens: int = 0, projected_cost: float = 0.0) -> None:
        """Check if projected or current usage exceeds token or cost limits.

        Raises BudgetExceededError if budget exceeded.
        """
        new_tokens = self.total_usage.total_tokens + projected_tokens
        new_cost = self.total_cost_usd + projected_cost

        if self.token_budget is not None and new_tokens > self.token_budget:
            raise BudgetExceededError(
                f"Token budget of {self.token_budget} exceeded (projected: {new_tokens})",
                current_cost=self.total_cost_usd,
                max_cost=self.max_cost_dollars,
                current_tokens=new_tokens,
                token_budget=self.token_budget,
            )

        if self.max_cost_dollars is not None and new_cost > self.max_cost_dollars:
            raise BudgetExceededError(
                f"Maximum cost budget of ${self.max_cost_dollars:.2f} exceeded "
                f"(projected: ${new_cost:.4f})",
                current_cost=new_cost,
                max_cost=self.max_cost_dollars,
                current_tokens=new_tokens,
                token_budget=self.token_budget,
            )

    def record_usage(self, usage: TokenUsage, cost_usd: float) -> None:
        """Record token consumption and cost for a completed call."""
        self.total_usage = self.total_usage.add(usage)
        self.total_cost_usd = round(self.total_cost_usd + cost_usd, 6)
        self.check_budget()

    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        system: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse[str]:
        """Generate freeform text completion."""
        ...

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        system: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse[T]:
        """Generate response conforming to Pydantic schema."""
        ...
