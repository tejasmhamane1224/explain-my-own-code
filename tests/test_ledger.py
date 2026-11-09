"""Acceptance tests for ledger, Leitner box mastery, report, and review workflows."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
from typer.testing import CliRunner

from emc.cli import app
from emc.detect import get_taxonomy
from emc.ledger import (
    LedgerEvent,
    MasteryLevel,
    MasteryTracker,
    append_event,
    read_events,
    read_events_with_stats,
)


@pytest.fixture
def temp_ledger(tmp_path: Path) -> Path:
    """Fixture providing an isolated temporary ledger path."""
    ledger_path = tmp_path / "test_ledger.jsonl"
    return ledger_path


def test_ledger_append_and_read_records(temp_ledger: Path) -> None:
    """Verify ledger appends and reads records accurately."""
    ev1 = LedgerEvent(
        session_id="session_1",
        diff_hash="hash_abc",
        concept_id="anchor.signer_check",
        question_type="predict-output",
        user_answer="A",
        is_correct=True,
        hints_used=1,
        points_awarded=7.5,
        max_points=10.0,
    )
    ev2 = LedgerEvent(
        session_id="session_1",
        diff_hash="hash_abc",
        concept_id="math.checked_arith",
        question_type="what-breaks-if",
        user_answer="B",
        is_correct=False,
        hints_used=0,
        points_awarded=0.0,
        max_points=10.0,
    )

    append_event(ev1, ledger_path=temp_ledger)
    append_event(ev2, ledger_path=temp_ledger)

    events = read_events(ledger_path=temp_ledger)
    assert len(events) == 2
    assert events[0].concept_id == "anchor.signer_check"
    assert events[0].is_correct is True
    assert events[0].points_awarded == 7.5
    assert events[1].concept_id == "math.checked_arith"
    assert events[1].is_correct is False


def test_ledger_missing_file_handled_gracefully(tmp_path: Path) -> None:
    """Verify reading a non-existent ledger returns an empty list without error."""
    non_existent = tmp_path / "missing.jsonl"
    events = read_events(ledger_path=non_existent)
    assert events == []
    events_stats, corrupt = read_events_with_stats(ledger_path=non_existent)
    assert events_stats == []
    assert corrupt == 0


def test_ledger_corrupted_lines_skipped_resiliently(temp_ledger: Path) -> None:
    """Verify corrupted JSON lines are safely skipped while preserving valid events."""
    ev1 = LedgerEvent(
        session_id="session_1",
        concept_id="anchor.signer_check",
        question_type="consequence",
        user_answer="A",
        is_correct=True,
    )
    ev2 = LedgerEvent(
        session_id="session_2",
        concept_id="ts.lamport_units",
        question_type="spot-the-bug",
        user_answer="B",
        is_correct=True,
    )

    # Write valid, then corrupted, then valid lines
    temp_ledger.parent.mkdir(parents=True, exist_ok=True)
    with temp_ledger.open("w", encoding="utf-8") as f:
        f.write(ev1.model_dump_json() + "\n")
        f.write("corrupted { invalid json\n")
        f.write("\n")  # Blank line
        f.write('{"missing": "required_fields"}\n')
        f.write(ev2.model_dump_json() + "\n")

    events, corrupt_count = read_events_with_stats(ledger_path=temp_ledger)
    assert corrupt_count == 2
    assert len(events) == 2
    assert events[0].concept_id == "anchor.signer_check"
    assert events[1].concept_id == "ts.lamport_units"


def test_ledger_thread_safety_concurrent_appends(temp_ledger: Path) -> None:
    """Verify concurrent appends across threads do not corrupt ledger file."""
    num_threads = 10
    events_per_thread = 5

    def worker(worker_id: int) -> None:
        for i in range(events_per_thread):
            ev = LedgerEvent(
                session_id=f"worker_{worker_id}",
                concept_id="anchor.signer_check",
                question_type="predict-output",
                user_answer="A",
                is_correct=True,
            )
            append_event(ev, ledger_path=temp_ledger)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    events, corrupt = read_events_with_stats(ledger_path=temp_ledger)
    assert corrupt == 0
    assert len(events) == num_threads * events_per_thread


def test_leitner_box_advancement_on_correct() -> None:
    """Verify consecutive correct answers advance concept through boxes 1 -> 5."""
    tracker = MasteryTracker()
    cid = "anchor.signer_check"

    # Initial state
    initial = tracker.get_mastery(cid)
    assert initial.box == 1
    assert initial.attempts == 0
    assert initial.mastery_level == MasteryLevel.WEAK

    # 1. First correct -> Box 2 (Developing)
    m1 = tracker.process_event(
        LedgerEvent(
            session_id="s1", concept_id=cid, question_type="q", user_answer="A", is_correct=True
        )
    )
    assert m1.box == 2
    assert m1.attempts == 1
    assert m1.correct_count == 1
    assert m1.streak == 1
    assert m1.pass_rate == 100.0
    assert m1.mastery_level == MasteryLevel.DEVELOPING

    # 2. Second correct -> Box 3 (Competent)
    m2 = tracker.process_event(
        LedgerEvent(
            session_id="s2", concept_id=cid, question_type="q", user_answer="A", is_correct=True
        )
    )
    assert m2.box == 3
    assert m2.streak == 2
    assert m2.mastery_level == MasteryLevel.COMPETENT

    # 3. Third correct -> Box 4 (Proficient)
    m3 = tracker.process_event(
        LedgerEvent(
            session_id="s3", concept_id=cid, question_type="q", user_answer="A", is_correct=True
        )
    )
    assert m3.box == 4
    assert m3.streak == 3
    assert m3.mastery_level == MasteryLevel.PROFICIENT

    # 4. Fourth correct -> Box 5 (Mastered)
    m4 = tracker.process_event(
        LedgerEvent(
            session_id="s4", concept_id=cid, question_type="q", user_answer="A", is_correct=True
        )
    )
    assert m4.box == 5
    assert m4.streak == 4
    assert m4.mastery_level == MasteryLevel.MASTERED

    # 5. Fifth correct -> Capped at Box 5
    m5 = tracker.process_event(
        LedgerEvent(
            session_id="s5", concept_id=cid, question_type="q", user_answer="A", is_correct=True
        )
    )
    assert m5.box == 5
    assert m5.streak == 5
    assert m5.attempts == 5
    assert m5.mastery_level == MasteryLevel.MASTERED


def test_leitner_box_demotion_on_incorrect() -> None:
    """Verify incorrect answer resets concept back to Box 1 and clears streak."""
    tracker = MasteryTracker(demote_to_box_1=True)
    cid = "anchor.pda_seeds"

    # Advance to Box 3
    for s in ["s1", "s2"]:
        tracker.process_event(
            LedgerEvent(
                session_id=s, concept_id=cid, question_type="q", user_answer="A", is_correct=True
            )
        )
    assert tracker.get_mastery(cid).box == 3
    assert tracker.get_mastery(cid).streak == 2

    # Fail attempt -> Demote to Box 1, streak reset to 0
    m_fail = tracker.process_event(
        LedgerEvent(
            session_id="s3", concept_id=cid, question_type="q", user_answer="B", is_correct=False
        )
    )
    assert m_fail.box == 1
    assert m_fail.streak == 0
    assert m_fail.attempts == 3
    assert m_fail.correct_count == 2
    assert m_fail.pass_rate == 66.67
    assert m_fail.mastery_level == MasteryLevel.WEAK


def test_leitner_box_gradual_demotion_option() -> None:
    """Verify demote_to_box_1=False decrements box by 1 rather than resetting to 1."""
    tracker = MasteryTracker(demote_to_box_1=False)
    cid = "ts.lamport_units"

    # Advance to Box 4
    for s in ["s1", "s2", "s3"]:
        tracker.process_event(
            LedgerEvent(
                session_id=s, concept_id=cid, question_type="q", user_answer="A", is_correct=True
            )
        )
    assert tracker.get_mastery(cid).box == 4

    # Fail once -> Demote from Box 4 to Box 3
    m_down = tracker.process_event(
        LedgerEvent(
            session_id="s4", concept_id=cid, question_type="q", user_answer="X", is_correct=False
        )
    )
    assert m_down.box == 3
    assert m_down.streak == 0


def test_mastery_tracker_statistics_and_summary() -> None:
    """Verify summary metrics compute aggregate accuracy, counts, and active concepts."""
    tracker = MasteryTracker()
    taxonomy = get_taxonomy()
    assert len(tracker.get_all_masteries()) == len(taxonomy.all_concepts())

    # Add 2 correct for anchor.signer_check and 1 incorrect for generic.bypass_flags
    tracker.process_event(
        LedgerEvent(
            session_id="s1",
            concept_id="anchor.signer_check",
            question_type="q",
            user_answer="A",
            is_correct=True,
        )
    )
    tracker.process_event(
        LedgerEvent(
            session_id="s2",
            concept_id="anchor.signer_check",
            question_type="q",
            user_answer="A",
            is_correct=True,
        )
    )
    tracker.process_event(
        LedgerEvent(
            session_id="s3",
            concept_id="generic.bypass_flags",
            question_type="q",
            user_answer="B",
            is_correct=False,
        )
    )

    summary = tracker.summary()
    assert summary.total_questions == 3
    assert summary.total_correct == 2
    assert summary.accuracy_percent == 66.67
    assert summary.active_concepts == 2
    assert summary.developing_count == 0
    assert summary.competent_count == 1  # Box 1 -> Box 2 -> Box 3


def test_mastery_tracker_weak_concepts_prioritization() -> None:
    """Verify weak concepts prioritization orders failed attempts first, then developing."""
    tracker = MasteryTracker()

    # Concept A has a failed attempt (Box 1, attempts=1, pass_rate=0%)
    tracker.process_event(
        LedgerEvent(
            session_id="s1",
            concept_id="anchor.signer_check",
            question_type="q",
            user_answer="B",
            is_correct=False,
        )
    )
    # Concept B has 1 correct attempt (Box 2, attempts=1, pass_rate=100%)
    tracker.process_event(
        LedgerEvent(
            session_id="s2",
            concept_id="anchor.account_types",
            question_type="q",
            user_answer="A",
            is_correct=True,
        )
    )

    weak = tracker.get_weak_concepts(max_box=2, limit=2)
    assert len(weak) == 2
    # Concept A (failed) must be prioritized ahead of Concept B (developing)
    assert weak[0].concept_id == "anchor.signer_check"
    assert weak[1].concept_id == "anchor.account_types"


def test_cli_report_rich_table_empty_ledger(cli_runner: CliRunner, temp_ledger: Path) -> None:
    """Verify emc report displays friendly initial baseline when ledger is empty."""
    res = cli_runner.invoke(app, ["report", "--ledger", str(temp_ledger)])
    assert res.exit_code == 0
    assert "No comprehension quiz events recorded" in res.stdout
    assert "Concept Leitner Mastery Status" in res.stdout


def test_cli_report_json_output(cli_runner: CliRunner, temp_ledger: Path) -> None:
    """Verify emc report --json outputs valid schema with summary and concept array."""
    ev = LedgerEvent(
        session_id="s1",
        concept_id="anchor.signer_check",
        question_type="predict-output",
        user_answer="A",
        is_correct=True,
    )
    append_event(ev, ledger_path=temp_ledger)

    res = cli_runner.invoke(app, ["report", "--ledger", str(temp_ledger), "--json"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert "summary" in data
    assert "concepts" in data
    assert data["summary"]["total_questions"] == 1
    assert data["summary"]["total_correct"] == 1
    assert data["summary"]["overall_accuracy_percent"] == 100.0

    signer_entry = next(c for c in data["concepts"] if c["concept_id"] == "anchor.signer_check")
    assert signer_entry["box"] == 2
    assert signer_entry["attempts"] == 1
    assert signer_entry["pass_rate_percent"] == 100.0
    assert signer_entry["mastery_level"] == "Developing"


def test_cli_report_weak_only_and_category_filter(cli_runner: CliRunner, temp_ledger: Path) -> None:
    """Verify emc report --weak-only and --category filters properly."""
    # Add events to advance anchor.signer_check to Box 4 (not weak)
    for s in ["s1", "s2", "s3"]:
        append_event(
            LedgerEvent(
                session_id=s,
                concept_id="anchor.signer_check",
                question_type="q",
                user_answer="A",
                is_correct=True,
            ),
            ledger_path=temp_ledger,
        )

    res_weak = cli_runner.invoke(
        app, ["report", "--ledger", str(temp_ledger), "--weak-only", "--json"]
    )
    assert res_weak.exit_code == 0
    data_weak = json.loads(res_weak.stdout)
    # anchor.signer_check (Box 4) should NOT be present in weak-only report
    assert not any(c["concept_id"] == "anchor.signer_check" for c in data_weak["concepts"])

    res_cat = cli_runner.invoke(
        app, ["report", "--ledger", str(temp_ledger), "--category", "rust_anchor", "--json"]
    )
    assert res_cat.exit_code == 0
    data_cat = json.loads(res_cat.stdout)
    assert all(c["category"] == "rust_anchor" for c in data_cat["concepts"])


def test_cli_review_scripted_session_updates_ledger(
    cli_runner: CliRunner, temp_ledger: Path
) -> None:
    """Verify emc review tests a weak concept and advances its Leitner box in the ledger."""
    # Target anchor.signer_check with correct answer 'A'
    res = cli_runner.invoke(
        app,
        [
            "review",
            "--concept",
            "anchor.signer_check",
            "--answers",
            "A",
            "--ledger",
            str(temp_ledger),
        ],
    )
    assert res.exit_code == 0
    assert "Updated Concept Leitner Mastery Post-Review" in res.stdout
    assert "anchor.signer_check" in res.stdout

    # Verify event was recorded in ledger
    events = read_events(ledger_path=temp_ledger)
    assert len(events) == 1
    assert events[0].concept_id == "anchor.signer_check"
    assert events[0].is_correct is True

    # Tracker loaded from ledger should now reflect Box 2
    tracker = MasteryTracker.from_ledger(ledger_path=temp_ledger)
    assert tracker.get_mastery("anchor.signer_check").box == 2


def test_cli_review_json_output(cli_runner: CliRunner, temp_ledger: Path) -> None:
    """Verify emc review --json emits machine-readable results with updated mastery."""
    res = cli_runner.invoke(
        app,
        [
            "review",
            "--concept",
            "math.checked_arith",
            "--answers",
            "A",
            "--ledger",
            str(temp_ledger),
            "--json",
        ],
    )
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert data["status"] == "completed"
    assert "score" in data
    assert "updated_mastery" in data
    assert len(data["updated_mastery"]) == 1
    assert data["updated_mastery"][0]["concept_id"] == "math.checked_arith"
    assert data["updated_mastery"][0]["box"] == 2


def test_cli_review_invalid_concept_rejected(cli_runner: CliRunner) -> None:
    """Verify emc review rejects non-existent concept IDs with exit code 1."""
    res = cli_runner.invoke(app, ["review", "--concept", "unknown_bogus_concept"])
    assert res.exit_code == 1
    assert "Unknown concept ID" in res.stdout or "Error" in res.stdout


def test_cli_review_ci_non_interactive_bypass(
    cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch, temp_ledger: Path
) -> None:
    """Verify emc review skips safely in unscripted CI environments."""
    monkeypatch.setenv("CI", "true")
    res = cli_runner.invoke(app, ["review", "--ledger", str(temp_ledger)])
    assert res.exit_code == 0
    assert "Skipping review session" in res.stdout


def test_end_to_end_quiz_to_report_to_review_integration(
    cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Full lifecycle: emc quiz records -> emc report reflects -> emc review advances box."""
    monkeypatch.chdir(tmp_path)
    custom_ledger = tmp_path / ".emc" / "ledger.jsonl"

    # Step 1: Run scripted comprehension quiz on Anchor fixture diff
    fixture_path = (
        Path(__file__).resolve().parent.parent
        / "fixtures"
        / "detectors"
        / "anchor_missing_signer_positive.diff"
    )
    assert fixture_path.is_file()
    diff_content = fixture_path.read_text(encoding="utf-8")

    res_quiz = cli_runner.invoke(
        app,
        ["quiz", "--stdin", "--provider", "fake", "--answers", "A,A,A"],
        input=diff_content,
    )
    assert res_quiz.exit_code == 0

    # Verify ledger exists and recorded events
    assert custom_ledger.is_file()
    events = read_events(ledger_path=custom_ledger)
    assert len(events) >= 1

    # Step 2: Run emc report and verify concept shows active attempts
    res_report = cli_runner.invoke(app, ["report", "--json"])
    assert res_report.exit_code == 0
    report_data = json.loads(res_report.stdout)
    assert report_data["summary"]["total_questions"] >= 1
    assert report_data["summary"]["active_concepts"] >= 1

    # Step 3: Run review targeting a weak concept
    res_review = cli_runner.invoke(
        app,
        ["review", "--concept", "ts.lamport_units", "--answers", "A", "--json"],
    )
    assert res_review.exit_code == 0
    review_data = json.loads(res_review.stdout)
    assert review_data["status"] == "completed"
    assert review_data["updated_mastery"][0]["concept_id"] == "ts.lamport_units"
    assert review_data["updated_mastery"][0]["box"] == 2

    # Step 4: Run report again and confirm ts.lamport_units has advanced
    res_report2 = cli_runner.invoke(app, ["report", "--json"])
    assert res_report2.exit_code == 0
    report2_data = json.loads(res_report2.stdout)
    lamport_entry = next(
        c for c in report2_data["concepts"] if c["concept_id"] == "ts.lamport_units"
    )
    assert lamport_entry["box"] == 2
    assert lamport_entry["attempts"] == 1
    assert lamport_entry["pass_rate_percent"] == 100.0
