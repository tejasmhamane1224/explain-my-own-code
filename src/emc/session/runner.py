"""Interactive session runner for comprehension quiz with Rich UI and hint ladder."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator, Sequence
from typing import TextIO

from rich.console import Console

from emc.grade.deterministic import calculate_hint_penalty, grade_deterministic
from emc.grade.models import GradeResult, ScoreBreakdown
from emc.grade.rubric import grade_rubric
from emc.llm.base import LLMProvider
from emc.questions.schema import Question, QuestionType
from emc.session.display import (
    render_grade_result_panel,
    render_hint_panel,
    render_question_panel,
    render_session_summary_table,
    render_verdict_panel,
)


class SessionRunner:
    """Orchestrates an interactive or scripted comprehension quiz session."""

    def __init__(
        self,
        questions: list[Question],
        provider: LLMProvider | None = None,
        console: Console | None = None,
        input_stream: Iterator[str] | Sequence[str] | TextIO | None = None,
        base_points: float = 10.0,
        passing_threshold: float = 70.0,
        penalty_per_hint: float = 0.25,
        max_hint_penalty: float = 0.75,
    ) -> None:
        self.questions = questions
        self.provider = provider
        self.console = console or Console()
        self.input_stream = input_stream
        self.base_points = base_points
        self.passing_threshold = passing_threshold
        self.penalty_per_hint = penalty_per_hint
        self.max_hint_penalty = max_hint_penalty

    def _is_non_interactive(self) -> bool:
        """Check whether current runtime is non-interactive or CI without scripted input."""
        if self.input_stream is not None:
            return False

        is_ci = os.getenv("CI", "").lower() in ("true", "1")
        is_tty = sys.stdin.isatty() and getattr(self.console, "is_terminal", True)
        return is_ci or not is_tty

    def run(self) -> ScoreBreakdown:
        """Execute the comprehension quiz session to completion."""
        # 1. CI / non-TTY safety guard
        if self._is_non_interactive():
            self.console.print(
                "[dim]Non-interactive terminal or CI environment detected. "
                "Skipping comprehension quiz.[/dim]"
            )
            return ScoreBreakdown(passing_threshold=self.passing_threshold)

        if not self.questions:
            self.console.print("[yellow]No comprehension questions available for session.[/yellow]")
            return ScoreBreakdown(passing_threshold=self.passing_threshold)

        # 2. Prepare scripted or interactive input source
        inputs_iter: Iterator[str] | None = None
        if self.input_stream is not None:
            if isinstance(self.input_stream, (list, tuple)):
                inputs_iter = iter(self.input_stream)
            elif hasattr(self.input_stream, "readline"):
                inputs_iter = (line.rstrip("\r\n") for line in self.input_stream)
            else:
                inputs_iter = iter(self.input_stream)

        def _get_input(prompt_text: str) -> str | None:
            if inputs_iter is not None:
                try:
                    return next(inputs_iter)
                except StopIteration:
                    return None
            try:
                return self.console.input(prompt_text)
            except (EOFError, KeyboardInterrupt):
                return None

        results: list[GradeResult] = []
        total_questions = len(self.questions)
        session_aborted = False

        # 3. Question Presentation and Grading Loop
        for idx, question in enumerate(self.questions, start=1):
            if session_aborted:
                results.append(
                    GradeResult(
                        question_id=question.id,
                        question_type=question.type,
                        concept_id=question.concept_id,
                        user_answer="quit",
                        is_correct=False,
                        base_points=self.base_points,
                        points_awarded=0.0,
                        max_points=self.base_points,
                        hints_used=0,
                        hint_penalty_percent=0.0,
                        explanation=question.explanation,
                        feedback="Session aborted by user.",
                        is_skipped=True,
                    )
                )
                continue

            hints_revealed: list[str] = []
            self.console.print(
                render_question_panel(
                    question=question,
                    current_index=idx,
                    total_questions=total_questions,
                    hints_revealed=hints_revealed,
                )
            )

            # Interactive prompt loop for current question
            while True:
                if question.choices:
                    prompt_str = (
                        "[bold cyan]Your answer [A-D, (H)int, (S)kip, (Q)uit]: [/bold cyan]"
                    )
                elif question.type == QuestionType.EXPLAIN_BACK:
                    prompt_str = (
                        "[bold cyan]Your explanation [(H)int, (S)kip, (Q)uit]: [/bold cyan]"
                    )
                else:
                    prompt_str = "[bold cyan]Your answer [(H)int, (S)kip, (Q)uit]: [/bold cyan]"

                raw_input = _get_input(prompt_str)

                if raw_input is None:
                    # Premature EOF/stream termination
                    session_aborted = True
                    results.append(
                        GradeResult(
                            question_id=question.id,
                            question_type=question.type,
                            concept_id=question.concept_id,
                            user_answer="quit",
                            is_correct=False,
                            base_points=self.base_points,
                            points_awarded=0.0,
                            max_points=self.base_points,
                            hints_used=len(hints_revealed),
                            hint_penalty_percent=0.0,
                            explanation=question.explanation,
                            feedback="Session aborted (EOF).",
                            is_skipped=True,
                        )
                    )
                    break

                cleaned = raw_input.strip()
                if not cleaned:
                    continue

                lowered = cleaned.lower()

                # Action: Request Hint
                if lowered in ("h", "hint", "help"):
                    if len(hints_revealed) < len(question.hint_ladder):
                        next_hint = question.hint_ladder[len(hints_revealed)]
                        hints_revealed.append(next_hint)
                        penalty_pct = calculate_hint_penalty(
                            len(hints_revealed),
                            self.penalty_per_hint,
                            self.max_hint_penalty,
                        )
                        self.console.print(
                            render_hint_panel(
                                hint_text=next_hint,
                                hint_index=len(hints_revealed),
                                total_hints=len(question.hint_ladder),
                                penalty_pct=penalty_pct,
                            )
                        )
                    else:
                        self.console.print(
                            "[yellow]No more hints available for this question.[/yellow]"
                        )
                    continue

                # Action: Skip Question
                if lowered in ("s", "skip"):
                    grade_res = GradeResult(
                        question_id=question.id,
                        question_type=question.type,
                        concept_id=question.concept_id,
                        user_answer="skip",
                        is_correct=False,
                        base_points=self.base_points,
                        points_awarded=0.0,
                        max_points=self.base_points,
                        hints_used=len(hints_revealed),
                        hint_penalty_percent=0.0,
                        explanation=question.explanation,
                        feedback="Question skipped by user.",
                        is_skipped=True,
                    )
                    self.console.print(render_grade_result_panel(grade_res))
                    results.append(grade_res)
                    break

                # Action: Quit Session
                if lowered in ("q", "quit", "exit"):
                    session_aborted = True
                    self.console.print("[yellow]Comprehension quiz aborted by user.[/yellow]")
                    results.append(
                        GradeResult(
                            question_id=question.id,
                            question_type=question.type,
                            concept_id=question.concept_id,
                            user_answer="quit",
                            is_correct=False,
                            base_points=self.base_points,
                            points_awarded=0.0,
                            max_points=self.base_points,
                            hints_used=len(hints_revealed),
                            hint_penalty_percent=0.0,
                            explanation=question.explanation,
                            feedback="Session aborted by user.",
                            is_skipped=True,
                        )
                    )
                    break

                # Action: Answer Submitted
                if question.type == QuestionType.EXPLAIN_BACK:
                    grade_res = grade_rubric(
                        question=question,
                        user_answer=cleaned,
                        provider=self.provider,
                        hints_used=len(hints_revealed),
                        base_points=self.base_points,
                        penalty_per_hint=self.penalty_per_hint,
                        max_hint_penalty=self.max_hint_penalty,
                        passing_threshold=self.passing_threshold,
                    )
                else:
                    grade_res = grade_deterministic(
                        question=question,
                        user_answer=cleaned,
                        hints_used=len(hints_revealed),
                        base_points=self.base_points,
                        penalty_per_hint=self.penalty_per_hint,
                        max_hint_penalty=self.max_hint_penalty,
                    )

                self.console.print(render_grade_result_panel(grade_res))
                results.append(grade_res)
                break

        # 4. Generate Summary and Render Final Verdict
        breakdown = ScoreBreakdown.from_results(results, passing_threshold=self.passing_threshold)
        if results:
            self.console.print(render_session_summary_table(breakdown))
            self.console.print(render_verdict_panel(breakdown))

        return breakdown
