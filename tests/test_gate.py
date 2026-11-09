"""Acceptance tests for Stage 6 operational modes, commit gate, and trailers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from emc.cli import app
from emc.gate import (
    append_commit_trailer,
    evaluate_gate,
    format_commit_trailer,
    load_staged_trailer,
    log_skip_event,
    save_staged_trailer,
)
from emc.grade.models import GradeResult, ScoreBreakdown
from emc.ledger.storage import read_events
from emc.questions.schema import QuestionType

SAMPLE_DIFF = """diff --git a/programs/vault/src/lib.rs b/programs/vault/src/lib.rs
index 1111111..2222222 100644
--- a/programs/vault/src/lib.rs
+++ b/programs/vault/src/lib.rs
@@ -10,6 +10,8 @@ pub mod vault {
     pub fn withdraw(ctx: Context<Withdraw>, amount: u64) -> Result<()> {
-        let authority = &ctx.accounts.authority;
+        let authority = &ctx.accounts.authority;
+        ctx.accounts.vault.amount -= amount;
         Ok(())
     }
 }
"""


def _make_breakdown(
    points_earned: float,
    points_possible: float,
    passing_threshold: float = 70.0,
    results: list[GradeResult] | None = None,
) -> ScoreBreakdown:
    pct = (points_earned / points_possible * 100.0) if points_possible > 0 else 0.0
    return ScoreBreakdown(
        total_questions=len(results) if results else (1 if points_possible > 0 else 0),
        correct_count=int(points_earned / 10.0) if points_earned > 0 else 0,
        skipped_count=0,
        total_hints_used=0,
        points_earned=points_earned,
        points_possible=points_possible,
        percentage=pct,
        passing_threshold=passing_threshold,
        passed=pct >= passing_threshold,
        results=results or [],
    )


def test_evaluate_gate_unit() -> None:
    """Unit test gate evaluation across off, warn, and gate modes."""
    pass_bd = _make_breakdown(10.0, 10.0)  # 100%
    fail_bd = _make_breakdown(0.0, 10.0)  # 0%

    # off mode: always passes, exit 0
    res_off_pass = evaluate_gate(pass_bd, mode="off")
    assert res_off_pass.exit_code == 0
    assert res_off_pass.passed is True
    assert res_off_pass.blocked is False
    assert res_off_pass.warning is False

    res_off_fail = evaluate_gate(fail_bd, mode="off")
    assert res_off_fail.exit_code == 0
    assert res_off_fail.passed is True
    assert res_off_fail.blocked is False
    assert res_off_fail.warning is False

    # warn mode: passing exits 0, failing exits 0 with warning=True
    res_warn_pass = evaluate_gate(pass_bd, mode="warn")
    assert res_warn_pass.exit_code == 0
    assert res_warn_pass.passed is True
    assert res_warn_pass.warning is False
    assert res_warn_pass.blocked is False

    res_warn_fail = evaluate_gate(fail_bd, mode="warn")
    assert res_warn_fail.exit_code == 0
    assert res_warn_fail.passed is False
    assert res_warn_fail.warning is True
    assert res_warn_fail.blocked is False

    # gate mode: passing exits 0, failing exits 1 with blocked=True
    res_gate_pass = evaluate_gate(pass_bd, mode="gate")
    assert res_gate_pass.exit_code == 0
    assert res_gate_pass.passed is True
    assert res_gate_pass.warning is False
    assert res_gate_pass.blocked is False

    res_gate_fail = evaluate_gate(fail_bd, mode="gate")
    assert res_gate_fail.exit_code == 1
    assert res_gate_fail.passed is False
    assert res_gate_fail.warning is False
    assert res_gate_fail.blocked is True


def test_cli_quiz_mode_off(
    cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify mode='off' skips quiz execution, logs skip event, and exits 0."""
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / ".emc.toml"
    config_file.write_text('[emc]\nmode = "off"\n', encoding="utf-8")

    # Normal text execution
    result = cli_runner.invoke(app, ["quiz", "--stdin"], input=SAMPLE_DIFF)
    assert result.exit_code == 0
    assert "disabled (mode: off)" in result.stdout

    # Verify skip event recorded in ledger
    events = read_events(tmp_path / ".emc" / "ledger.jsonl")
    assert len(events) >= 1
    assert events[-1].concept_id == "system.skipped"
    assert events[-1].is_skipped is True
    assert events[-1].metadata.get("skip_reason") == "mode_off"

    # JSON execution
    res_json = cli_runner.invoke(app, ["quiz", "--stdin", "--json"], input=SAMPLE_DIFF)
    assert res_json.exit_code == 0
    data = json.loads(res_json.stdout)
    assert data["status"] == "skipped"
    assert data["mode"] == "off"
    assert data["passed"] is True


def test_cli_quiz_mode_warn_failing_score(
    cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify mode='warn' with failing score displays prominent warning banner but exits 0."""
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / ".emc.toml"
    config_file.write_text('[emc]\nmode = "warn"\n', encoding="utf-8")

    # Scripted wrong answers ('B' when answer key is 'A')
    result = cli_runner.invoke(
        app,
        ["quiz", "--stdin", "--answers", "B,B,B"],
        input=SAMPLE_DIFF,
    )
    assert result.exit_code == 0  # Does NOT block commit
    assert "WARNING" in result.stdout
    assert "mode: warn" in result.stdout


def test_cli_quiz_mode_warn_passing_score(
    cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify mode='warn' with passing score exits 0 without warning."""
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / ".emc.toml"
    config_file.write_text('[emc]\nmode = "warn"\n', encoding="utf-8")

    # Scripted correct answers
    result = cli_runner.invoke(
        app,
        ["quiz", "--stdin", "--answers", "A,A,A"],
        input=SAMPLE_DIFF,
    )
    assert result.exit_code == 0
    assert "COMPREHENSION CHECK PASSED" in result.stdout
    assert "WARNING:" not in result.stdout


def test_cli_quiz_mode_gate_failing_score_blocks(
    cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify mode='gate' with failing score displays blocked banner and exits 1."""
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / ".emc.toml"
    config_file.write_text('[emc]\nmode = "gate"\n', encoding="utf-8")

    # Failing answers -> should block commit with exit 1
    result = cli_runner.invoke(
        app,
        ["quiz", "--stdin", "--answers", "B,B,B"],
        input=SAMPLE_DIFF,
    )
    assert result.exit_code == 1
    assert "BLOCKED" in result.stdout
    assert "mode: gate" in result.stdout

    # In JSON mode
    res_json = cli_runner.invoke(
        app,
        ["quiz", "--stdin", "--answers", "B,B,B", "--json"],
        input=SAMPLE_DIFF,
    )
    assert res_json.exit_code == 1
    data = json.loads(res_json.stdout)
    assert data["passed"] is False
    assert data["gate"]["blocked"] is True
    assert data["gate"]["exit_code"] == 1


def test_cli_quiz_mode_gate_passing_score(
    cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify mode='gate' with passing score permits commit with exit 0."""
    monkeypatch.chdir(tmp_path)
    config_file = tmp_path / ".emc.toml"
    config_file.write_text('[emc]\nmode = "gate"\n', encoding="utf-8")

    result = cli_runner.invoke(
        app,
        ["quiz", "--stdin", "--answers", "A,A,A"],
        input=SAMPLE_DIFF,
    )
    assert result.exit_code == 0
    assert "COMPREHENSION CHECK PASSED" in result.stdout


def test_cli_quiz_skip_flag_enforcement_and_ledger(
    cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify --skip logs skip event to ledger when allowed, and errors when disallowed."""
    monkeypatch.chdir(tmp_path)

    # 1. Allowed (default)
    config_file = tmp_path / ".emc.toml"
    config_file.write_text("[emc]\nskip_allowed = true\n", encoding="utf-8")

    res_allowed = cli_runner.invoke(app, ["quiz", "--skip"])
    assert res_allowed.exit_code == 0
    assert "skipped by developer" in res_allowed.stdout

    events = read_events(tmp_path / ".emc" / "ledger.jsonl")
    assert len(events) >= 1
    assert events[-1].is_skipped is True
    assert events[-1].metadata.get("skip_reason") == "flag_skip"

    # 2. Disallowed
    config_file.write_text("[emc]\nskip_allowed = false\n", encoding="utf-8")
    res_disallowed = cli_runner.invoke(app, ["quiz", "--skip"])
    assert res_disallowed.exit_code == 1
    assert "skip_allowed = false" in res_disallowed.stdout

    # With --json
    res_disallowed_json = cli_runner.invoke(app, ["quiz", "--skip", "--json"])
    assert res_disallowed_json.exit_code == 1
    data = json.loads(res_disallowed_json.stdout)
    assert data["error"] == "skip_not_allowed"


def test_ci_non_tty_behavior_across_modes(
    cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify non-interactive / CI environment skips cleanly with exit 0 across all modes."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CI", "true")

    for test_mode in ["off", "warn", "gate"]:
        config_file = tmp_path / ".emc.toml"
        config_file.write_text(f'[emc]\nmode = "{test_mode}"\n', encoding="utf-8")

        result = cli_runner.invoke(app, ["quiz", "--stdin"], input=SAMPLE_DIFF)
        assert result.exit_code == 0
        assert (
            "Non-interactive terminal or CI environment detected" in result.stdout
            or "disabled (mode: off)" in result.stdout
        )


def test_ci_scripted_answers_honors_gate_mode(
    cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify in CI environment, providing scripted answers runs the quiz and respects gate mode."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CI", "true")
    config_file = tmp_path / ".emc.toml"
    config_file.write_text('[emc]\nmode = "gate"\n', encoding="utf-8")

    # Scripted passing answers
    res_pass = cli_runner.invoke(
        app,
        ["quiz", "--stdin", "--answers", "A,A,A"],
        input=SAMPLE_DIFF,
    )
    assert res_pass.exit_code == 0

    # Scripted failing answers in gate mode -> exit 1
    res_fail = cli_runner.invoke(
        app,
        ["quiz", "--stdin", "--answers", "B,B,B"],
        input=SAMPLE_DIFF,
    )
    assert res_fail.exit_code == 1
    assert "BLOCKED" in res_fail.stdout


def test_format_commit_trailer() -> None:
    """Verify commit trailer formatting across styles and breakdown statistics."""
    gr1 = GradeResult(
        question_id="q1",
        concept_id="anchor.signer_check",
        question_type=QuestionType.PREDICT_OUTPUT,
        user_answer="A",
        is_correct=True,
        hints_used=0,
        points_awarded=10.0,
        max_points=10.0,
        feedback="Correct",
    )
    gr2 = GradeResult(
        question_id="q2",
        concept_id="anchor.signer_check",
        question_type=QuestionType.WHAT_BREAKS_IF,
        user_answer="A",
        is_correct=True,
        hints_used=0,
        points_awarded=10.0,
        max_points=10.0,
        feedback="Correct",
    )
    gr3 = GradeResult(
        question_id="q3",
        concept_id="math.checked_arith",
        question_type=QuestionType.CONSEQUENCE,
        user_answer="B",
        is_correct=False,
        hints_used=0,
        points_awarded=0.0,
        max_points=10.0,
        feedback="Incorrect",
    )

    bd = ScoreBreakdown(
        total_questions=3,
        correct_count=2,
        skipped_count=0,
        total_hints_used=0,
        points_earned=20.0,
        points_possible=30.0,
        percentage=66.67,
        passing_threshold=70.0,
        passed=False,
        results=[gr1, gr2, gr3],
    )

    # 1. Fraction style (default)
    trailer_frac = format_commit_trailer(bd, style="fraction")
    assert trailer_frac == "Comprehension: 2/3"

    # 2. Percentage style
    trailer_pct = format_commit_trailer(bd, style="percentage")
    assert trailer_pct == "Comprehension: 67%"

    # 3. Detailed style
    trailer_det = format_commit_trailer(bd, style="detailed")
    assert "Comprehension: 67%" in trailer_det
    assert "anchor.signer_check: 2/2" in trailer_det
    assert "math.checked_arith: 0/1" in trailer_det

    # 4. Empty breakdown
    empty_bd = ScoreBreakdown(total_questions=0, points_possible=0.0)
    assert format_commit_trailer(empty_bd) == "Comprehension: N/A"


def test_append_commit_trailer(tmp_path: Path) -> None:
    """Verify appending and updating trailers in commit message files."""
    msg_file = tmp_path / "COMMIT_EDITMSG"

    # 1. Clean commit message
    msg_file.write_text("feat(core): implement vault instruction\n", encoding="utf-8")
    appended = append_commit_trailer(msg_file, "Comprehension: 3/3")
    assert appended is True
    content = msg_file.read_text(encoding="utf-8")
    assert "Comprehension: 3/3" in content
    assert content.startswith("feat(core): implement vault instruction\n\nComprehension: 3/3\n")

    # 2. Deduplicate existing trailer
    appended_dup = append_commit_trailer(msg_file, "Comprehension: 2/3", deduplicate=True)
    assert appended_dup is True
    content_dup = msg_file.read_text(encoding="utf-8")
    assert "Comprehension: 2/3" in content_dup
    assert "Comprehension: 3/3" not in content_dup

    # 3. Message with trailing git comments
    msg_with_comments = tmp_path / "COMMIT_COMMENTS"
    msg_with_comments.write_text(
        "fix(anchor): check signer\n\n"
        "# Please enter the commit message for your changes.\n"
        "# Lines starting with '#' will be ignored.\n",
        encoding="utf-8",
    )
    append_commit_trailer(msg_with_comments, "Comprehension: 4/4")
    c_comments = msg_with_comments.read_text(encoding="utf-8")
    lines = c_comments.splitlines()
    trailer_idx = lines.index("Comprehension: 4/4")
    comment_idx = lines.index("# Please enter the commit message for your changes.")
    # Trailer MUST precede trailing git comments
    assert trailer_idx < comment_idx

    # 4. Empty commit message (aborted commit) -> do not add trailer
    empty_msg = tmp_path / "EMPTY_MSG"
    empty_msg.write_text("\n# All lines are comments\n", encoding="utf-8")
    assert append_commit_trailer(empty_msg, "Comprehension: 1/1") is False


def test_staged_trailer_save_and_load(tmp_path: Path) -> None:
    """Verify saving, loading, and consuming staged trailer file."""
    trailer = "Comprehension: 100% (anchor.signer_check: 2/2)"
    saved_path = save_staged_trailer(trailer, target_dir=tmp_path)
    assert saved_path.is_file()

    # Load with consume=False
    loaded = load_staged_trailer(target_dir=tmp_path, consume=False)
    assert loaded == trailer
    assert saved_path.is_file()

    # Load with consume=True
    loaded_consumed = load_staged_trailer(target_dir=tmp_path, consume=True)
    assert loaded_consumed == trailer
    assert not saved_path.exists()

    # Subsequent load returns None
    assert load_staged_trailer(target_dir=tmp_path) is None


def test_log_skip_event_direct(tmp_path: Path) -> None:
    """Verify log_skip_event writes event to ledger accurately."""
    ledger_file = tmp_path / "ledger.jsonl"
    ev = log_skip_event("custom_test_skip", ledger_path=ledger_file, diff_hash="abc1234")
    assert ev.is_skipped is True
    assert ev.concept_id == "system.skipped"
    assert ev.diff_hash == "abc1234"
    assert ev.metadata["skip_reason"] == "custom_test_skip"

    records = read_events(ledger_file)
    assert len(records) == 1
    assert records[0].session_id == ev.session_id
