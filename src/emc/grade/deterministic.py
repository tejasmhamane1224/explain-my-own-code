"""Deterministic grading engine for multiple-choice and spot-the-bug."""

from __future__ import annotations

import re

from emc.grade.models import GradeResult
from emc.questions.schema import Question, QuestionType


def calculate_hint_penalty(
    hints_used: int,
    penalty_per_hint: float = 0.25,
    max_penalty: float = 0.75,
) -> float:
    """Calculate fractional point penalty for revealed hints.

    Default: 1st hint = -25%, 2nd hint = -50%, 3rd hint = -75% (capped).
    """
    if hints_used <= 0:
        return 0.0
    return min(hints_used * penalty_per_hint, max_penalty)


def normalize_input(raw: str) -> str:
    """Clean and normalize user answer input."""
    return raw.strip().strip("`'\"()[]{}.,:;").strip()


def match_choice_key(user_answer: str, question: Question) -> bool:
    """Check if user answer matches the question's answer key."""
    cleaned = normalize_input(user_answer).upper()
    expected_key = question.answer_key.strip().upper()

    # Exact key match (e.g. "A" == "A")
    if cleaned == expected_key:
        return True

    # "Option A" or "Choice A"
    match = re.match(r"^(?:OPTION|CHOICE)\s+([A-Z0-9]+)$", cleaned)
    if match and match.group(1) == expected_key:
        return True

    # Numeric selection matching (1 -> A, 2 -> B, etc.)
    if cleaned.isdigit():
        idx = int(cleaned) - 1
        if 0 <= idx < len(question.choices):
            if question.choices[idx].key.strip().upper() == expected_key:
                return True

    # Full text matching against correct choice text
    correct_choice = question.get_correct_choice()
    if correct_choice:
        normalized_choice_text = correct_choice.text.strip().lower()
        normalized_user = user_answer.strip().lower()
        if normalized_user == normalized_choice_text:
            return True
        # If user typed substantial portion of choice text (>= 15 chars)
        if len(normalized_user) >= 15 and normalized_user in normalized_choice_text:
            return True

    return False


def match_spot_the_bug(user_answer: str, question: Question) -> bool:
    """Match spot-the-bug answers against line numbers or mutant choice keys."""
    # First check standard choice matching
    if match_choice_key(user_answer, question):
        return True

    cleaned = normalize_input(user_answer).lower()
    expected_key = question.answer_key.strip().lower()

    # Extract digits (e.g. "line 42" -> ["42"])
    nums = re.findall(r"\b\d+\b", cleaned)
    expected_nums = re.findall(r"\b\d+\b", expected_key)

    if nums and expected_nums:
        if any(num in expected_nums for num in nums):
            return True

    # Check if choice text for correct choice mentions the line number
    correct_choice = question.get_correct_choice()
    if correct_choice and nums:
        choice_nums = re.findall(r"\b\d+\b", correct_choice.text)
        if any(num in choice_nums for num in nums):
            return True

    return False


def grade_deterministic(
    question: Question,
    user_answer: str,
    hints_used: int = 0,
    base_points: float = 10.0,
    penalty_per_hint: float = 0.25,
    max_hint_penalty: float = 0.75,
) -> GradeResult:
    """Deterministically grade multiple-choice and spot-the-bug questions."""
    raw = user_answer.strip()

    # Check for skip
    if raw.lower() in ("skip", "s", "--skip"):
        return GradeResult(
            question_id=question.id,
            question_type=question.type,
            concept_id=question.concept_id,
            user_answer=user_answer,
            is_correct=False,
            base_points=base_points,
            points_awarded=0.0,
            max_points=base_points,
            hints_used=hints_used,
            hint_penalty_percent=0.0,
            explanation=question.explanation,
            feedback="Question skipped.",
            is_skipped=True,
        )

    # Spot the bug or choice matching
    if question.type == QuestionType.SPOT_THE_BUG:
        is_correct = match_spot_the_bug(user_answer, question)
    else:
        is_correct = match_choice_key(user_answer, question)

    penalty = calculate_hint_penalty(hints_used, penalty_per_hint, max_hint_penalty)

    if is_correct:
        awarded = round(base_points * (1.0 - penalty), 2)
        penalty_desc = f" ({int(penalty * 100)}% hint penalty)" if penalty > 0 else ""
        feedback = f"Correct! Earned {awarded:.1f} / {base_points:.1f} pts{penalty_desc}."
    else:
        awarded = 0.0
        feedback = f"Incorrect. Correct answer was {question.answer_key}."

    return GradeResult(
        question_id=question.id,
        question_type=question.type,
        concept_id=question.concept_id,
        user_answer=user_answer,
        is_correct=is_correct,
        base_points=base_points,
        points_awarded=awarded,
        max_points=base_points,
        hints_used=hints_used,
        hint_penalty_percent=penalty,
        explanation=question.explanation,
        feedback=feedback,
        is_skipped=False,
    )
