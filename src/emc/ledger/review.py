"""Review replay session generator and runner targeting weak Leitner concepts."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from emc.detect.taxonomy import ConceptDefinition, get_taxonomy
from emc.grade.models import ScoreBreakdown
from emc.ingest import parse_unified_diff
from emc.ledger.models import ConceptMastery, LedgerEvent
from emc.ledger.storage import append_events, get_default_ledger_path
from emc.ledger.tracker import MasteryTracker
from emc.llm.base import LLMProvider
from emc.questions.schema import Distractor, Question, QuestionType
from emc.session.runner import SessionRunner

logger = logging.getLogger(__name__)


def find_fixtures_dir() -> Path | None:
    """Locate the fixtures/detectors directory."""
    candidates = [
        Path.cwd() / "fixtures" / "detectors",
        Path(__file__).resolve().parents[3] / "fixtures" / "detectors",
        Path(__file__).resolve().parents[2] / "fixtures" / "detectors",
    ]
    for c in candidates:
        if c.is_dir() and (c / "manifest.json").is_file():
            return c
    return None


def get_concept_fixture_map() -> dict[str, str]:
    """Map canonical concept IDs to positive fixture file paths."""
    fixtures_dir = find_fixtures_dir()
    if not fixtures_dir:
        return {}

    manifest_file = fixtures_dir / "manifest.json"
    if not manifest_file.is_file():
        return {}

    try:
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        fixtures = data.get("fixtures", [])
        mapping: dict[str, str] = {}
        for f in fixtures:
            if f.get("fixture_type") == "positive":
                c_id = f.get("concept_id")
                name = f.get("name")
                if c_id and name:
                    mapping[c_id] = str(fixtures_dir / name)
        return mapping
    except Exception as exc:
        logger.warning("Could not read fixtures manifest: %s", exc)
        return {}


def build_review_question(concept_def: ConceptDefinition) -> Question:
    """Build a deterministic, grounded review question for a concept using its fixture."""
    fixture_map = get_concept_fixture_map()
    fixture_path_str = fixture_map.get(concept_def.id)

    file_path = f"programs/{concept_def.id.replace('.', '_')}/src/lib.rs"
    start_line = 1
    end_line = 10
    snippet = f"// Code pattern for {concept_def.name}\n// Concept: {concept_def.id}"

    if fixture_path_str:
        fixture_path = Path(fixture_path_str)
        if fixture_path.is_file():
            try:
                raw_diff = fixture_path.read_text(encoding="utf-8")
                parsed = parse_unified_diff(raw_diff)
                if parsed and parsed[0].hunks:
                    hunk = parsed[0].hunks[0]
                    resolved_path = parsed[0].new_path or parsed[0].old_path
                    if resolved_path:
                        file_path = resolved_path
                    start_line = hunk.new_start
                    end_line = hunk.new_start + len(hunk.lines) - 1
                    snippet = hunk.content.strip()
            except Exception as exc:
                logger.warning("Failed parsing fixture %s for review: %s", fixture_path, exc)

    stem = (
        f"Review comprehension check for '{concept_def.name}':\n\n"
        f"In the context of {concept_def.category}, which of the following best describes "
        f"the safety rule or potential vulnerability addressed by this code?"
    )

    correct_text = (
        concept_def.remediation
        if concept_def.remediation
        else f"Enforce required validation for {concept_def.name}."
    )
    distractor_b = "No additional validation is required because runtime checks are automatic."
    distractor_c = (
        "This pattern only applies to unit tests and has no security impact in production."
    )

    choices = [
        Distractor(
            key="A",
            text=correct_text,
            explanation=f"Matches required security remediation for {concept_def.id}.",
        ),
        Distractor(
            key="B",
            text=distractor_b,
            explanation="Incorrect; failing to enforce this check leaves vulnerabilities.",
        ),
        Distractor(
            key="C",
            text=distractor_c,
            explanation="Incorrect; this is a critical on-chain / runtime safety rule.",
        ),
    ]

    return Question(
        id=str(uuid.uuid4()),
        type=QuestionType.CONSEQUENCE,
        concept_id=concept_def.id,
        hunk_rank=1,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        snippet=snippet,
        stem=stem,
        choices=choices,
        answer_key="A",
        explanation=concept_def.description or f"Proper remediation: {concept_def.remediation}",
        hint_ladder=[
            f"Review the primary concept: {concept_def.name}.",
            f"Focus on safety guidelines for {concept_def.category}.",
        ],
    )


def select_review_concepts(
    tracker: MasteryTracker,
    target_concept_id: str | None = None,
    limit: int = 3,
) -> list[ConceptMastery]:
    """Identify candidate concepts for a review session.

    If target_concept_id is provided, checks and returns that single concept.
    Otherwise, returns up to limit weak concepts (Box 1 or 2, lowest pass rate).
    """
    if target_concept_id:
        try:
            return [tracker.get_mastery(target_concept_id)]
        except KeyError:
            taxonomy = get_taxonomy()
            concept_def = taxonomy.get(target_concept_id)
            if not concept_def:
                raise ValueError(
                    f"Unknown concept ID '{target_concept_id}'. "
                    f"Registered concepts: {[c.id for c in taxonomy.all_concepts()]}"
                )
            return [
                ConceptMastery(
                    concept_id=concept_def.id,
                    name=concept_def.name,
                    category=concept_def.category,
                    box=1,
                    attempts=0,
                    correct_count=0,
                    streak=0,
                    pass_rate=0.0,
                    last_reviewed=None,
                )
            ]

    # Target weak concepts (Box <= 2)
    weak = tracker.get_weak_concepts(max_box=2, limit=limit, only_attempted=False)
    if weak:
        return weak

    # If no weak concepts exist (all Box >= 3), return concepts with lowest boxes
    all_masteries = tracker.get_all_masteries(sort_by="box_asc")
    return all_masteries[:limit]


def run_review_session(
    target_concept_id: str | None = None,
    limit: int = 3,
    provider: LLMProvider | None = None,
    scripted_inputs: list[str] | None = None,
    console: Console | None = None,
    ledger_path: Path | None = None,
    as_json: bool = False,
) -> tuple[ScoreBreakdown, list[ConceptMastery]]:
    """Execute a complete spaced repetition review session and update ledger.

    Returns (breakdown, updated_masteries).
    """
    actual_console = Console(quiet=True) if as_json else (console or Console())
    resolved_ledger = ledger_path or get_default_ledger_path()
    taxonomy = get_taxonomy()
    tracker = MasteryTracker.from_ledger(ledger_path=resolved_ledger, taxonomy=taxonomy)

    candidate_masteries = select_review_concepts(
        tracker=tracker,
        target_concept_id=target_concept_id,
        limit=limit,
    )

    if not candidate_masteries:
        if not as_json:
            actual_console.print(
                "[bold green]No weak concepts found for review! "
                "All concepts are mastered or competent.[/bold green]"
            )
        return ScoreBreakdown(passing_threshold=70.0), []

    # Build review questions
    questions: list[Question] = []
    for m in candidate_masteries:
        concept_def = taxonomy.get(m.concept_id)
        if not concept_def:
            concept_def = ConceptDefinition(
                id=m.concept_id,
                name=m.name,
                category=m.category,
                description="",
                remediation="",
            )
        q = build_review_question(concept_def)
        questions.append(q)

    if not as_json:
        actual_console.print(
            Panel(
                f"[bold cyan]Starting Concept Review Session[/bold cyan]\n"
                f"Targeting [bold yellow]{len(questions)}[/bold yellow] "
                "weak or unmastered concept(s). "
                "Answers will update your Leitner boxes in `.emc/ledger.jsonl`.",
                title="EMC Spaced Repetition Review",
                border_style="cyan",
            )
        )

    runner = SessionRunner(
        questions=questions,
        provider=provider,
        console=actual_console,
        input_stream=scripted_inputs,
    )
    breakdown = runner.run()

    # Record outcomes to ledger
    session_id = f"review_{uuid.uuid4().hex[:8]}"
    new_events: list[LedgerEvent] = []
    updated_masteries: list[ConceptMastery] = []

    for res in breakdown.results:
        ev = LedgerEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_id=session_id,
            diff_hash=f"review_{res.concept_id}",
            concept_id=res.concept_id,
            question_type=res.question_type.value,
            user_answer=res.user_answer,
            is_correct=res.is_correct,
            hints_used=res.hints_used,
            points_awarded=res.points_awarded,
            max_points=res.max_points,
            question_id=res.question_id,
            is_skipped=res.is_skipped,
        )
        new_events.append(ev)
        updated_m = tracker.process_event(ev)
        updated_masteries.append(updated_m)

    if new_events:
        append_events(new_events, ledger_path=resolved_ledger)

    if not as_json and updated_masteries:
        update_table = Table(
            title="Updated Concept Leitner Mastery Post-Review",
            show_header=True,
            header_style="bold green",
        )
        update_table.add_column("Concept ID", style="cyan")
        update_table.add_column("Concept Name", style="white")
        update_table.add_column("New Leitner Box", justify="center")
        update_table.add_column("Attempts", justify="right")
        update_table.add_column("Pass Rate", justify="right")
        update_table.add_column("Status", justify="left")

        for um in updated_masteries:
            update_table.add_row(
                um.concept_id,
                um.name,
                um.box_visual,
                str(um.attempts),
                f"{um.pass_rate:.1f}%",
                um.mastery_level.value,
            )
        actual_console.print(update_table)

    return breakdown, updated_masteries
