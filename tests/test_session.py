"""Acceptance and unit tests for interactive and scripted comprehension quiz sessions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from rich.console import Console
from typer.testing import CliRunner

from emc.cli import app
from emc.questions.schema import Distractor, Question, QuestionType, RubricCriterion
from emc.session.runner import SessionRunner


@pytest.fixture
def sample_diff() -> str:
    """Sample unified diff fixture for testing."""
    diff_path = (
        Path(__file__).parent.parent
        / "fixtures"
        / "detectors"
        / "anchor_missing_signer_positive.diff"
    )
    return diff_path.read_text(encoding="utf-8")


@pytest.fixture
def quiz_questions() -> list[Question]:
    """Test suite of 3 diverse comprehension questions."""
    q1 = Question(
        id="q-1",
        type=QuestionType.PREDICT_OUTPUT,
        concept_id="anchor.missing_signer",
        hunk_rank=1,
        file_path="programs/vault/src/lib.rs",
        start_line=12,
        end_line=25,
        snippet="pub authority: AccountInfo<'info>,",
        stem="What vulnerability arises if authority is typed as AccountInfo?",
        choices=[
            Distractor(
                key="A",
                text="Any arbitrary caller can pass their own pubkey to authorize withdraw.",
                explanation="AccountInfo does not enforce signer validation.",
            ),
            Distractor(
                key="B",
                text="Anchor rejects the transaction with ConstraintSigner.",
                explanation="Anchor does not reject without Signer type.",
            ),
        ],
        answer_key="A",
        explanation="AccountInfo lacks signature checking, permitting unauthorized draining.",
        hint_ladder=[
            "Check the account validation type for authority.",
            "AccountInfo permits arbitrary unsigned pubkeys.",
        ],
    )
    q2 = Question(
        id="q-2",
        type=QuestionType.SPOT_THE_BUG,
        concept_id="math.unchecked_arith",
        hunk_rank=2,
        file_path="programs/vault/src/lib.rs",
        start_line=30,
        end_line=35,
        snippet="let total = balance + amount;",
        mutant_snippet="let total = balance + amount;",
        stem="Identify the bug in the mutated calculation snippet.",
        choices=[
            Distractor(
                key="A",
                text="Line 31: Unchecked raw addition without checked_add.",
                explanation="Can overflow.",
            ),
            Distractor(
                key="B",
                text="Line 33: Invalid variable name.",
                explanation="Naming is valid.",
            ),
        ],
        answer_key="A",
        explanation="Raw arithmetic on balances risks integer overflow/underflow.",
        hint_ladder=[
            "Look for raw arithmetic operators (+, -) instead of checked math.",
        ],
    )
    q3 = Question(
        id="q-3",
        type=QuestionType.EXPLAIN_BACK,
        concept_id="anchor.missing_signer",
        hunk_rank=3,
        file_path="programs/vault/src/lib.rs",
        start_line=12,
        end_line=25,
        snippet="pub authority: AccountInfo<'info>,",
        stem="Explain why authority must be typed as Signer<'info>.",
        choices=[],
        answer_key="Signer ensures Solana runtime validates cryptographic signature.",
        explanation=(
            "AccountInfo permits arbitrary pubkeys; Signer requires cryptographic signature."
        ),
        rubric=[
            RubricCriterion(
                name="Signature Verification",
                description="Mentions cryptographic signature check.",
                points=1,
                required_concepts=["signer", "signature"],
            )
        ],
        hint_ladder=["Consider how Solana validates transaction signers."],
    )
    return [q1, q2, q3]


def test_scripted_session_perfect_score(quiz_questions: list[Question]) -> None:
    """Scripted session with perfect answers achieves 100% score and passes."""
    scripted_inputs = [
        "A",
        "A",
        "The authority must be typed as Signer to ensure cryptographic signature check.",
    ]
    console = Console(record=True)
    runner = SessionRunner(
        questions=quiz_questions,
        console=console,
        input_stream=scripted_inputs,
        base_points=10.0,
        passing_threshold=70.0,
    )
    breakdown = runner.run()

    assert breakdown.total_questions == 3
    assert breakdown.correct_count == 3
    assert breakdown.skipped_count == 0
    assert breakdown.total_hints_used == 0
    assert breakdown.points_earned == 30.0
    assert breakdown.percentage == 100.0
    assert breakdown.passed is True

    output = console.export_text()
    assert "COMPREHENSION CHECK PASSED" in output
    assert "30.0 / 30.0" in output


def test_scripted_session_with_hint_ladder(quiz_questions: list[Question]) -> None:
    """Scripted session with hint ladder usage verifies point deductions."""
    scripted_inputs = [
        # Q1: 1 hint used (-25%) then correct answer A
        "H",
        "A",
        # Q2: 1 hint used (-25%) then correct answer A
        "hint",
        "A",
        # Q3: 0 hints, correct explanation
        "Signer enforces cryptographic signature validation.",
    ]
    console = Console(record=True)
    runner = SessionRunner(
        questions=quiz_questions,
        console=console,
        input_stream=scripted_inputs,
        base_points=10.0,
    )
    breakdown = runner.run()

    assert breakdown.total_questions == 3
    assert breakdown.correct_count == 3
    assert breakdown.total_hints_used == 2
    # Q1: 7.5 pts, Q2: 7.5 pts, Q3: 10.0 pts -> Total: 25.0 pts
    assert breakdown.points_earned == 25.0
    assert breakdown.points_possible == 30.0
    assert breakdown.percentage == round(25.0 / 30.0 * 100.0, 2)
    assert breakdown.passed is True

    output = console.export_text()
    assert "Hint 1 of 2 (-25% Point Penalty)" in output
    assert "Hint 1 of 1 (-25% Point Penalty)" in output


def test_scripted_session_hint_exhaustion(quiz_questions: list[Question]) -> None:
    """Requesting more hints than exist warns without crashing."""
    # Q1 only has 2 hints
    scripted_inputs = [
        "H",
        "H",
        "H",  # 3rd hint requested (exhausted)
        "A",
        "A",
        "Signer signature verification.",
    ]
    console = Console(record=True)
    runner = SessionRunner(
        questions=quiz_questions,
        console=console,
        input_stream=scripted_inputs,
        base_points=10.0,
    )
    breakdown = runner.run()

    assert breakdown.correct_count == 3
    # Only 2 hints actually existed on Q1
    assert breakdown.results[0].hints_used == 2
    output = console.export_text()
    assert "No more hints available" in output


def test_scripted_session_wrong_answers(quiz_questions: list[Question]) -> None:
    """Scripted session with incorrect answers fails comprehension check."""
    scripted_inputs = [
        "B",
        "B",
        "This code is completely fine and has no issues.",
    ]
    console = Console(record=True)
    runner = SessionRunner(
        questions=quiz_questions,
        console=console,
        input_stream=scripted_inputs,
        base_points=10.0,
    )
    breakdown = runner.run()

    assert breakdown.total_questions == 3
    assert breakdown.correct_count == 0
    assert breakdown.points_earned == 0.0
    assert breakdown.percentage == 0.0
    assert breakdown.passed is False

    output = console.export_text()
    assert "COMPREHENSION CHECK FAILED" in output


def test_scripted_session_skip_command(quiz_questions: list[Question]) -> None:
    """Scripted session using skip commands marks items skipped with zero score."""
    scripted_inputs = [
        "S",
        "skip",
        "S",
    ]
    console = Console(record=True)
    runner = SessionRunner(
        questions=quiz_questions,
        console=console,
        input_stream=scripted_inputs,
        base_points=10.0,
    )
    breakdown = runner.run()

    assert breakdown.total_questions == 3
    assert breakdown.skipped_count == 3
    assert breakdown.correct_count == 0
    assert breakdown.points_earned == 0.0
    assert breakdown.passed is False


def test_scripted_session_quit_abort(quiz_questions: list[Question]) -> None:
    """Scripted session using quit command aborts quiz cleanly."""
    scripted_inputs = [
        "A",  # Q1 answered correctly
        "Q",  # Q2 quits session
    ]
    console = Console(record=True)
    runner = SessionRunner(
        questions=quiz_questions,
        console=console,
        input_stream=scripted_inputs,
        base_points=10.0,
    )
    breakdown = runner.run()

    assert breakdown.total_questions == 3
    assert breakdown.correct_count == 1
    # Q2 and Q3 are skipped due to quit
    assert breakdown.results[0].is_correct is True
    assert breakdown.results[1].is_skipped is True
    assert breakdown.results[2].is_skipped is True

    output = console.export_text()
    assert "Comprehension quiz aborted by user" in output


def test_session_ci_non_interactive_no_input(
    quiz_questions: list[Question], monkeypatch: pytest.MonkeyPatch
) -> None:
    """In CI or non-TTY without scripted inputs, SessionRunner exits cleanly without hanging."""
    monkeypatch.setenv("CI", "true")
    console = Console(record=True)
    runner = SessionRunner(
        questions=quiz_questions,
        console=console,
        input_stream=None,
    )
    breakdown = runner.run()

    assert breakdown.total_questions == 0
    output = console.export_text()
    assert "Non-interactive terminal or CI environment detected" in output


def test_session_ci_with_scripted_input_executes(
    quiz_questions: list[Question], monkeypatch: pytest.MonkeyPatch
) -> None:
    """In CI, providing scripted inputs overrides CI bypass and executes session."""
    monkeypatch.setenv("CI", "true")
    console = Console(record=True)
    runner = SessionRunner(
        questions=quiz_questions,
        console=console,
        input_stream=["A", "A", "Signer cryptographic signature validation."],
        base_points=10.0,
    )
    breakdown = runner.run()

    assert breakdown.total_questions == 3
    assert breakdown.passed is True


def test_cli_quiz_end_to_end_scripted(cli_runner: CliRunner, sample_diff: str) -> None:
    """Verify CLI emc quiz executes end-to-end with --provider fake and --answers."""
    result = cli_runner.invoke(
        app,
        ["quiz", "--stdin", "--provider", "fake", "--answers", "A,A,A"],
        input=sample_diff,
    )
    assert result.exit_code == 0
    assert "COMPREHENSION CHECK" in result.stdout
    assert "Overall Score" in result.stdout


def test_cli_quiz_json_output(cli_runner: CliRunner, sample_diff: str) -> None:
    """Verify CLI emc quiz --json emits machine-readable ScoreBreakdown payload."""
    result = cli_runner.invoke(
        app,
        ["quiz", "--stdin", "--provider", "fake", "--answers", "A,A,A", "--json"],
        input=sample_diff,
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "total_questions" in data
    assert "percentage" in data
    assert "passed" in data
    assert "results" in data
    assert isinstance(data["results"], list)


def test_scripted_session_empty_questions() -> None:
    """Verify empty questions list exits gracefully with zero score breakdown."""
    console = Console(record=True)
    runner = SessionRunner(
        questions=[],
        console=console,
        input_stream=["A"],
    )
    breakdown = runner.run()
    assert breakdown.total_questions == 0
    assert breakdown.passed is False


def test_scripted_session_unexpected_eof(quiz_questions: list[Question]) -> None:
    """Verify truncated input stream aborts cleanly and marks unreached questions skipped."""
    console = Console(record=True)
    runner = SessionRunner(
        questions=quiz_questions,
        console=console,
        input_stream=["A"],  # Only provides answer for Q1, Q2/Q3 hit EOF
    )
    breakdown = runner.run()
    assert breakdown.total_questions == 3
    assert breakdown.correct_count == 1
    assert breakdown.results[1].is_skipped is True
    assert breakdown.results[2].is_skipped is True


def test_scripted_session_blank_inputs_skipped(quiz_questions: list[Question]) -> None:
    """Verify empty/whitespace lines in scripted stream are ignored until real answer."""
    console = Console(record=True)
    runner = SessionRunner(
        questions=quiz_questions,
        console=console,
        input_stream=["", "   ", "A", "A", "Signer signature verification."],
    )
    breakdown = runner.run()
    assert breakdown.total_questions == 3
    assert breakdown.correct_count == 3
