"""Reporting engine for rendering Leitner box mastery in Rich tables and JSON."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from emc.ledger.models import ConceptMastery, MasteryLevel
from emc.ledger.tracker import MasteryTracker


def _get_box_style_and_markup(mastery: ConceptMastery) -> tuple[str, str]:
    """Return colored visual bar and status badge for a concept's Leitner box."""
    box = mastery.box
    vis = escape(mastery.box_visual)
    if box == 1:
        if mastery.attempts > 0:
            return "bold red", f"[bold red]{vis}[/bold red]"
        return "dim", f"[dim]{vis}[/dim]"
    elif box == 2:
        return "bold yellow", f"[bold yellow]{vis}[/bold yellow]"
    elif box == 3:
        return "cyan", f"[cyan]{vis}[/cyan]"
    elif box == 4:
        return "blue", f"[blue]{vis}[/blue]"
    else:  # box == 5
        return "bold green", f"[bold green]{vis}[/bold green]"


def _get_status_markup(mastery: ConceptMastery) -> str:
    """Format status badge based on mastery level and attempt count."""
    level = mastery.mastery_level
    if level == MasteryLevel.WEAK:
        if mastery.attempts == 0:
            return "[dim]Unreviewed[/dim]"
        return "[bold red]Weak (Action Needed)[/bold red]"
    elif level == MasteryLevel.DEVELOPING:
        return "[yellow]Developing[/yellow]"
    elif level == MasteryLevel.COMPETENT:
        return "[cyan]Competent[/cyan]"
    elif level == MasteryLevel.PROFICIENT:
        return "[blue]Proficient[/blue]"
    elif level == MasteryLevel.MASTERED:
        return "[bold green]Mastered[/bold green]"
    return str(level.value)


def generate_report_dict(
    tracker: MasteryTracker,
    weak_only: bool = False,
    category: str | None = None,
) -> dict[str, Any]:
    """Generate machine-readable summary dictionary for JSON output."""
    summary = tracker.summary()
    masteries = tracker.get_all_masteries(sort_by="box_asc")

    filtered: list[ConceptMastery] = []
    for m in masteries:
        if weak_only and not m.is_weak:
            continue
        if category and m.category.lower() != category.lower():
            continue
        filtered.append(m)

    concepts_data = [
        {
            "concept_id": m.concept_id,
            "name": m.name,
            "category": m.category,
            "box": m.box,
            "attempts": m.attempts,
            "correct_count": m.correct_count,
            "streak": m.streak,
            "pass_rate_percent": m.pass_rate,
            "mastery_level": m.mastery_level.value,
            "last_reviewed": m.last_reviewed,
            "is_weak": m.is_weak,
        }
        for m in filtered
    ]

    return {
        "summary": {
            "total_questions": summary.total_questions,
            "total_correct": summary.total_correct,
            "overall_accuracy_percent": summary.accuracy_percent,
            "mastered_concepts": summary.mastered_count,
            "proficient_concepts": summary.proficient_count,
            "competent_concepts": summary.competent_count,
            "developing_concepts": summary.developing_count,
            "weak_concepts": summary.weak_count,
            "active_concepts": summary.active_concepts,
            "total_concepts": summary.total_concepts,
        },
        "concepts": concepts_data,
    }


def render_report(
    tracker: MasteryTracker,
    console: Console,
    weak_only: bool = False,
    category: str | None = None,
) -> None:
    """Render comprehension mastery report to terminal using Rich tables and panels."""
    summary = tracker.summary()
    masteries = tracker.get_all_masteries(sort_by="box_asc")

    filtered: list[ConceptMastery] = []
    for m in masteries:
        if weak_only and not m.is_weak:
            continue
        if category and m.category.lower() != category.lower():
            continue
        filtered.append(m)

    # 1. Header and Summary Metrics
    if summary.total_questions == 0:
        console.print(
            Panel(
                "[yellow]No comprehension quiz events recorded in ledger yet.[/yellow]\n"
                "Run [bold cyan]emc quiz[/bold cyan] on a code diff to evaluate your code "
                "understanding and advance through the Leitner mastery boxes.",
                title="Comprehension Ledger Status",
                border_style="yellow",
            )
        )
    else:
        # Metrics Overview Table
        summary_table = Table(
            title="Developer Comprehension Mastery Overview",
            show_header=True,
            header_style="bold magenta",
        )
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", justify="right", style="bold")

        summary_table.add_row("Total Questions Answered", str(summary.total_questions))
        summary_table.add_row(
            "Overall Accuracy",
            (
                f"[bold green]{summary.accuracy_percent:.1f}%[/bold green]"
                if summary.accuracy_percent >= 70.0
                else f"[bold yellow]{summary.accuracy_percent:.1f}%[/bold yellow]"
            ),
        )
        summary_table.add_row(
            "Mastered Concepts (Box 5)",
            f"[bold green]{summary.mastered_count}[/bold green] / {summary.total_concepts}",
        )
        summary_table.add_row(
            "Proficient Concepts (Box 4)",
            f"[blue]{summary.proficient_count}[/blue]",
        )
        summary_table.add_row(
            "Competent Concepts (Box 3)",
            f"[cyan]{summary.competent_count}[/cyan]",
        )
        summary_table.add_row(
            "Developing Concepts (Box 2)",
            f"[yellow]{summary.developing_count}[/yellow]",
        )
        summary_table.add_row(
            "Weak Concepts (Box 1)",
            (
                f"[bold red]{summary.weak_count}[/bold red]"
                if summary.weak_count > 0
                else f"[green]{summary.weak_count}[/green]"
            ),
        )
        summary_table.add_row(
            "Active Evaluated Concepts",
            f"{summary.active_concepts} / {summary.total_concepts}",
        )
        console.print(summary_table)

    # 2. Per-concept Mastery Table
    table_title = (
        "Weak Concepts for Review (Box 1 & 2)" if weak_only else "Concept Leitner Mastery Status"
    )
    if category:
        table_title += f" [Category: {category}]"

    concept_table = Table(title=table_title, show_header=True, header_style="bold cyan")
    concept_table.add_column("Concept ID", style="cyan")
    concept_table.add_column("Category", style="magenta")
    concept_table.add_column("Concept Name", style="white")
    concept_table.add_column("Leitner Box", justify="center")
    concept_table.add_column("Attempts", justify="right")
    concept_table.add_column("Pass Rate", justify="right")
    concept_table.add_column("Streak", justify="right")
    concept_table.add_column("Status", justify="left")

    for m in filtered:
        _, box_markup = _get_box_style_and_markup(m)
        status_markup = _get_status_markup(m)

        if m.attempts > 0:
            if m.pass_rate >= 80.0:
                rate_style = "bold green"
            elif m.pass_rate >= 50.0:
                rate_style = "yellow"
            else:
                rate_style = "bold red"
            rate_display = f"[{rate_style}]{m.pass_rate:.1f}%[/{rate_style}]"
        else:
            rate_display = "[dim]-[/dim]"

        streak_display = str(m.streak) if m.streak > 0 else "[dim]0[/dim]"
        attempts_display = str(m.attempts) if m.attempts > 0 else "[dim]0[/dim]"

        concept_table.add_row(
            m.concept_id,
            m.category,
            m.name,
            box_markup,
            attempts_display,
            rate_display,
            streak_display,
            status_markup,
        )

    console.print(concept_table)

    # 3. Actionable recommendation banner
    if not filtered and weak_only:
        console.print(
            Panel(
                "[bold green]No weak concepts found for review! "
                "All concepts are in Box 3 or higher.[/bold green]",
                border_style="green",
            )
        )
    else:
        weak_reviewed = [m for m in filtered if m.box <= 2 and m.attempts > 0]
        if weak_reviewed:
            console.print(
                Panel(
                    f"[bold red]Found {len(weak_reviewed)} weak concept(s) "
                    "requiring reinforcement.[/bold red]\n"
                    "Run [bold cyan]emc review[/bold cyan] to replay targeted questions "
                    "and advance your mastery.",
                    border_style="red",
                )
            )
