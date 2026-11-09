"""Commit gate evaluation and mode enforcement for explain-my-own-code (emc)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from emc.config import EMCMode
from emc.grade.models import ScoreBreakdown
from emc.ledger.models import LedgerEvent
from emc.ledger.storage import append_event, get_default_ledger_path


class GateResult(BaseModel):
    """Result of commit gate evaluation against active mode."""

    model_config = ConfigDict(extra="ignore")

    mode: EMCMode = Field(description="Active enforcement mode: off, warn, or gate")
    passed: bool = Field(description="Whether comprehension check met passing threshold")
    exit_code: int = Field(
        default=0,
        description="Process exit code: 0 for pass/warn/off, 1 for gate blocking",
    )
    message: str = Field(description="Human-readable gate evaluation summary")
    warning: bool = Field(default=False, description="Whether to display prominent warning banner")
    blocked: bool = Field(default=False, description="Whether commit is blocked")


def evaluate_gate(
    breakdown: ScoreBreakdown,
    mode: EMCMode = "warn",
) -> GateResult:
    """Evaluate quiz score breakdown against enforcement mode.

    Modes:
      - 'off': comprehension check disabled, exits 0.
      - 'warn': score below threshold displays prominent warning banner, exits 0.
      - 'gate': score below threshold blocks commit, exits 1.
    """
    if mode == "off":
        return GateResult(
            mode="off",
            passed=True,
            exit_code=0,
            message="Comprehension gate is disabled (mode: off). Commit permitted.",
            warning=False,
            blocked=False,
        )

    if breakdown.total_questions == 0:
        return GateResult(
            mode=mode,
            passed=True,
            exit_code=0,
            message="No comprehension questions evaluated. Commit permitted.",
            warning=False,
            blocked=False,
        )

    if breakdown.passed:
        return GateResult(
            mode=mode,
            passed=True,
            exit_code=0,
            message=(
                f"Comprehension check passed ({breakdown.percentage:.1f}% >= "
                f"{breakdown.passing_threshold:.1f}%). Commit permitted."
            ),
            warning=False,
            blocked=False,
        )

    # Score below threshold
    if mode == "gate":
        return GateResult(
            mode="gate",
            passed=False,
            exit_code=1,
            message=(
                f"Comprehension check failed ({breakdown.percentage:.1f}% < "
                f"{breakdown.passing_threshold:.1f}%). Commit blocked (mode: gate)."
            ),
            warning=False,
            blocked=True,
        )

    # mode == "warn" (default)
    return GateResult(
        mode="warn",
        passed=False,
        exit_code=0,
        message=(
            f"Comprehension check failed ({breakdown.percentage:.1f}% < "
            f"{breakdown.passing_threshold:.1f}%). "
            "Warning displayed, commit permitted (mode: warn)."
        ),
        warning=True,
        blocked=False,
    )


def log_skip_event(
    reason: str,
    ledger_path: Path | None = None,
    diff_hash: str = "",
) -> LedgerEvent:
    """Log a quiz skip event to the ledger."""
    resolved_ledger = ledger_path or get_default_ledger_path()
    session_id = f"skip_{uuid.uuid4().hex[:8]}"
    event = LedgerEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        session_id=session_id,
        diff_hash=diff_hash,
        concept_id="system.skipped",
        question_type="skip",
        user_answer="[skipped]",
        is_correct=False,
        hints_used=0,
        points_awarded=0.0,
        max_points=0.0,
        question_id="",
        is_skipped=True,
        metadata={"skip_reason": reason},
    )
    append_event(event, ledger_path=resolved_ledger)
    return event
