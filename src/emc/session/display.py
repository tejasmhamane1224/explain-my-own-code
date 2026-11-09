"""Rich terminal display formatting for interactive comprehension quiz sessions."""

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from emc.grade.models import GradeResult, ScoreBreakdown
from emc.questions.schema import Question, QuestionType


def resolve_lexer(file_path: str) -> str:
    """Resolve pygments lexer name from file extension."""
    lower = file_path.lower()
    if lower.endswith(".rs"):
        return "rust"
    if lower.endswith((".ts", ".tsx")):
        return "typescript"
    if lower.endswith((".js", ".jsx")):
        return "javascript"
    if lower.endswith(".py"):
        return "python"
    if lower.endswith(".toml"):
        return "toml"
    if lower.endswith((".yaml", ".yml")):
        return "yaml"
    if lower.endswith(".json"):
        return "json"
    return "text"


def render_question_panel(
    question: Question,
    current_index: int,
    total_questions: int,
    hints_revealed: list[str] | None = None,
) -> Panel:
    """Render a comprehensive question panel with snippet syntax highlighting and choices."""
    revealed = hints_revealed or []
    lexer = resolve_lexer(question.file_path)

    elements: list[RenderableType] = []

    # 1. Target location
    loc_text = Text()
    loc_text.append("File: ", style="bold white")
    loc_text.append(
        f"{question.file_path}:{question.start_line}-{question.end_line}", style="yellow"
    )
    loc_text.append("  |  Concept: ", style="bold white")
    loc_text.append(question.concept_id, style="green")
    elements.append(loc_text)
    elements.append(Text(""))

    # 2. Code Snippet
    snippet_syntax = Syntax(
        question.snippet,
        lexer,
        line_numbers=True,
        start_line=question.start_line,
        theme="monokai",
        word_wrap=True,
    )
    elements.append(Panel(snippet_syntax, title="Diff Code Snippet", border_style="dim cyan"))

    # 3. Spot-the-bug mutant snippet (if applicable)
    if question.type == QuestionType.SPOT_THE_BUG and question.mutant_snippet:
        mutant_syntax = Syntax(
            question.mutant_snippet,
            lexer,
            line_numbers=True,
            start_line=question.start_line,
            theme="monokai",
            word_wrap=True,
        )
        elements.append(
            Panel(mutant_syntax, title="Mutated Code (Identify Bug/Flaw)", border_style="bold red")
        )

    # 4. Question Stem
    elements.append(Text(""))
    stem_text = Text(question.stem, style="bold white")
    elements.append(stem_text)
    elements.append(Text(""))

    # 5. Choices or Explain-back instructions
    if question.choices:
        choices_table = Table(show_header=False, box=None, padding=(0, 1))
        choices_table.add_column("Key", style="bold cyan", width=4)
        choices_table.add_column("Text", style="white")

        for choice in question.choices:
            choices_table.add_row(f"[{choice.key}]", choice.text)

        elements.append(choices_table)
    elif question.type == QuestionType.EXPLAIN_BACK:
        explain_note = Text(
            "Enter your free-text explanation below. Evaluated against safety rubric criteria.",
            style="italic cyan",
        )
        elements.append(explain_note)

    # 6. Hints status footer
    elements.append(Text(""))
    rem_hints = max(0, len(question.hint_ladder) - len(revealed))
    hint_footer = Text()
    if revealed:
        hint_footer.append(
            f"Hints used: {len(revealed)}/{len(question.hint_ladder)}  ", style="bold yellow"
        )
    hint_footer.append(
        f"Available hints: {rem_hints} (Revealing a hint applies a point penalty)", style="dim"
    )
    elements.append(hint_footer)

    title = f"Question {current_index} of {total_questions} [{question.type.value}]"
    return Panel(
        Group(*elements),
        title=f"[bold cyan]{title}[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    )


def render_hint_panel(
    hint_text: str,
    hint_index: int,
    total_hints: int,
    penalty_pct: float,
) -> Panel:
    """Render a revealed hint panel with penalty disclaimer."""
    penalty_int = int(penalty_pct * 100)
    title = f"Hint {hint_index} of {total_hints} (-{penalty_int}% Point Penalty)"
    return Panel(
        Text(hint_text, style="white"),
        title=f"[bold yellow]{title}[/bold yellow]",
        border_style="yellow",
        padding=(1, 2),
    )


def render_grade_result_panel(result: GradeResult) -> Panel:
    """Render immediate feedback panel following an answer."""
    elements: list[RenderableType] = []

    if result.is_skipped:
        status_text = Text("SKIPPED", style="bold yellow")
        border = "yellow"
    elif result.is_correct:
        status_text = Text(
            f"CORRECT! (+{result.points_awarded:.1f} / {result.max_points:.1f} pts)",
            style="bold green",
        )
        border = "green"
    else:
        status_text = Text(f"INCORRECT (0.0 / {result.max_points:.1f} pts)", style="bold red")
        border = "red"

    elements.append(status_text)
    elements.append(Text(""))

    if result.feedback:
        elements.append(Text(result.feedback, style="white"))
        elements.append(Text(""))

    if result.explanation:
        elements.append(Text("Explanation:", style="bold cyan"))
        elements.append(Text(result.explanation, style="dim white"))

    if result.rubric_evaluation and result.rubric_evaluation.criteria_results:
        elements.append(Text(""))
        rubric_table = Table(title="Rubric Criteria Evaluation", show_header=True)
        rubric_table.add_column("Criterion", style="cyan")
        rubric_table.add_column("Status", justify="center")
        rubric_table.add_column("Score", justify="right")
        rubric_table.add_column("Feedback", style="white")

        for crit in result.rubric_evaluation.criteria_results:
            st = "[bold green]PASS[/bold green]" if crit.passed else "[bold red]FAIL[/bold red]"
            rubric_table.add_row(
                crit.criterion_name,
                st,
                f"{crit.points_awarded:.1f}/{crit.max_points:.1f}",
                crit.feedback,
            )
        elements.append(rubric_table)

    return Panel(Group(*elements), title="Result", border_style=border, padding=(1, 2))


def render_session_summary_table(breakdown: ScoreBreakdown) -> Table:
    """Render table of all answered questions in the session."""
    table = Table(title="Comprehension Session Breakdown", show_header=True)
    table.add_column("#", justify="center", style="bold cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Concept", style="green")
    table.add_column("Result", justify="center", style="bold")
    table.add_column("Hints", justify="center", style="yellow")
    table.add_column("Points Earned", justify="right")

    for idx, r in enumerate(breakdown.results, start=1):
        if r.is_skipped:
            res_str = "[yellow]SKIPPED[/yellow]"
        elif r.is_correct:
            res_str = "[green]CORRECT[/green]"
        else:
            res_str = "[red]INCORRECT[/red]"

        table.add_row(
            str(idx),
            r.question_type.value,
            r.concept_id,
            res_str,
            str(r.hints_used),
            f"{r.points_awarded:.1f} / {r.max_points:.1f}",
        )

    return table


def render_verdict_panel(breakdown: ScoreBreakdown) -> Panel:
    """Render overall pass/fail session verdict panel."""
    elements: list[RenderableType] = []

    score_line = Text()
    score_line.append("Overall Score: ", style="bold white")
    score_style = "bold green" if breakdown.passed else "bold red"
    score_str = (
        f"{breakdown.points_earned:.1f} / {breakdown.points_possible:.1f} "
        f"({breakdown.percentage:.1f}%)"
    )
    score_line.append(score_str, style=score_style)
    score_line.append(f"  |  Passing Threshold: {breakdown.passing_threshold:.1f}%", style="dim")
    elements.append(score_line)
    elements.append(Text(""))

    stats_line = Text()
    stats_line.append(f"Questions: {breakdown.total_questions}  |  ", style="dim")
    stats_line.append(f"Correct: {breakdown.correct_count}  |  ", style="dim green")
    stats_line.append(f"Skipped: {breakdown.skipped_count}  |  ", style="dim yellow")
    stats_line.append(f"Total Hints: {breakdown.total_hints_used}", style="dim magenta")
    elements.append(stats_line)
    elements.append(Text(""))

    if breakdown.passed:
        verdict_text = Text(
            "COMPREHENSION CHECK PASSED: Code diff invariants and safety mechanisms understood.",
            style="bold green",
        )
        border = "green"
    else:
        verdict_text = Text(
            "COMPREHENSION CHECK FAILED: Insufficient understanding of diff safety risks.",
            style="bold red",
        )
        border = "red"

    elements.append(verdict_text)
    return Panel(
        Group(*elements), title="Comprehension Verdict", border_style=border, padding=(1, 2)
    )
