"""Command Line Interface for explain-my-own-code (emc)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from emc import __version__
from emc.config import load_config
from emc.detect import run_detector_pipeline
from emc.doctor import render_doctor_report, run_doctor_checks
from emc.ingest import (
    GitError,
    encapsulate_diff,
    ingest_diff,
    scan_for_injection_markers,
)
from emc.llm import (
    AnthropicProvider,
    CachedLLMProvider,
    DiskCache,
    FakeProvider,
    LLMProvider,
    LocalProvider,
)
from emc.plan import create_question_plans
from emc.questions import QuestionGenerator
from emc.redact import Redactor

app = typer.Typer(
    name="emc",
    help=(
        "explain-my-own-code (emc) -- "
        "Verifies whether a developer actually understands their code diff."
    ),
    no_args_is_help=True,
    add_completion=False,
)

hook_app = typer.Typer(
    name="hook",
    help="Manage git pre-commit / post-commit comprehension hooks.",
    no_args_is_help=True,
)
app.add_typer(hook_app, name="hook")

console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"[bold cyan]emc[/bold cyan] version [bold green]{__version__}[/bold green]")
        raise typer.Exit()


def _get_git_hooks_dir() -> Path | None:
    """Resolve git hooks directory using git rev-parse or fallback to .git/hooks."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--git-path", "hooks"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            shell=False,
        )
        resolved = Path(proc.stdout.strip())
        return resolved if resolved.is_absolute() else Path.cwd() / resolved
    except Exception:
        fallback = Path.cwd() / ".git" / "hooks"
        return fallback if fallback.parent.is_dir() else None


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            "-v",
            help="Show emc version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """explain-my-own-code (emc) root command."""
    pass


@app.command(name="doctor")
def doctor_cmd(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-V", help="Display verbose diagnostic troubleshooting details."),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Output diagnostic check results as machine-readable JSON."),
    ] = False,
) -> None:
    """Check git setup, environment variables, Anthropic key, and local configuration."""
    checks = run_doctor_checks()

    if as_json:
        data = [c.to_dict() for c in checks]
        typer.echo(json.dumps(data, indent=2))
        has_fail = any(c.status.value == "FAIL" for c in checks)
        raise typer.Exit(code=1 if has_fail else 0)

    exit_code = render_doctor_report(checks, console=console, verbose=verbose)
    raise typer.Exit(code=exit_code)


@app.command(name="config")
def config_cmd() -> None:
    """Display active configuration settings and resolved file location."""
    result = load_config()
    config = result.config
    path = result.path

    if result.error:
        console.print(
            f"[bold red]Configuration Warning:[/bold red] {result.error} (using fallback defaults)"
        )

    console.print(f"[bold cyan]Configuration File:[/bold cyan] {path or '<defaults>'}")
    console.print(f"[bold cyan]Mode:[/bold cyan] {config.mode}")
    console.print(f"[bold cyan]Model:[/bold cyan] {config.model}")
    budget_info = f"${config.max_cost_dollars:.2f} ({config.token_budget:,} tokens)"
    console.print(f"[bold cyan]Budget:[/bold cyan] {budget_info}")
    console.print(f"[bold cyan]Skip Allowed:[/bold cyan] {config.skip_allowed}")
    console.print(f"[bold cyan]Commit Trailer:[/bold cyan] {config.commit_trailer}")


@app.command(name="init")
def init_cmd(
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite existing .emc.toml")
    ] = False,
) -> None:
    """Initialize a default .emc.toml configuration file in the current directory."""
    target = Path(".emc.toml")
    if target.exists() and not force:
        console.print("[yellow].emc.toml already exists. Use --force to overwrite.[/yellow]")
        raise typer.Exit(code=1)

    default_content = (
        "# explain-my-own-code (emc) configuration\n\n"
        "[emc]\n"
        '# Enforcement mode: "off" (disabled), "warn" (alert only), "gate" (block commit)\n'
        'mode = "warn"\n\n'
        "# Default model identifier\n"
        'model = "claude-3-7-sonnet-latest"\n\n'
        "# Per-session budget in USD and max tokens\n"
        "max_cost_dollars = 0.50\n"
        "token_budget = 50000\n\n"
        "# Allow developers to pass --skip during git commit\n"
        "skip_allowed = true\n\n"
        "# Add Comprehension trailer to git commit message\n"
        "commit_trailer = true\n"
    )
    target.write_text(default_content, encoding="utf-8")

    # Lazily ensure .emc directory exists
    emc_dir = Path(".emc")
    emc_dir.mkdir(exist_ok=True)

    console.print(f"[bold green]Successfully initialized {target.resolve()}[/bold green]")


@app.command(name="quiz")
def quiz_cmd(
    staged: Annotated[bool, typer.Option("--staged", help="Analyze staged git changes.")] = False,
    commit: Annotated[
        Optional[str],
        typer.Option("--commit", help="Analyze specific commit or range (e.g. HEAD~1)."),
    ] = None,
    stdin: Annotated[bool, typer.Option("--stdin", help="Read diff from standard input.")] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Redact secrets and display without network call.")
    ] = False,
    generate: Annotated[
        bool,
        typer.Option(
            "--generate",
            help="Generate and validate questions through quality gate during dry run.",
        ),
    ] = False,
    skip: Annotated[
        bool, typer.Option("--skip", help="Skip comprehension quiz (logged to ledger).")
    ] = False,
) -> None:
    """Start an interactive comprehension quiz on a diff."""
    if skip:
        console.print("[dim]Comprehension quiz skipped by developer (--skip).[/dim]")
        raise typer.Exit(code=0)

    if dry_run:
        try:
            ingest_result = ingest_diff(staged=staged, commit=commit, use_stdin=stdin)
        except GitError as exc:
            console.print(f"[bold red]Git Error:[/bold red] {exc}")
            raise typer.Exit(code=1)

        if ingest_result.is_empty and not ingest_result.raw_diff.strip():
            console.print("[yellow]No diff changes found to analyze.[/yellow]")
            raise typer.Exit(code=0)

        redactor = Redactor()
        redacted_ingest, findings = redactor.redact_ingest_result(ingest_result)

        detector_report = run_detector_pipeline(redacted_ingest)

        summary_table = Table(title="Diff Ingestion & Redaction Summary", show_header=True)
        summary_table.add_column("Property", style="cyan")
        summary_table.add_column("Value", style="green")

        summary_table.add_row("Source", ingest_result.source)
        summary_table.add_row("Files Analyzed", str(ingest_result.total_files))
        summary_table.add_row("Total Hunks", str(ingest_result.total_hunks))
        summary_table.add_row(
            "Additions / Deletions",
            f"+{ingest_result.total_additions} / -{ingest_result.total_deletions}",
        )
        summary_table.add_row("Ignored Files", str(len(ingest_result.ignored_files)))
        summary_table.add_row(
            "Truncated",
            (
                f"[bold yellow]Yes ({ingest_result.truncation_reason})[/bold yellow]"
                if ingest_result.truncated
                else "No"
            ),
        )
        summary_table.add_row(
            "Secrets Redacted",
            f"[bold red]{len(findings)}[/bold red]" if findings else "0",
        )
        summary_table.add_row(
            "Risks Detected",
            (
                f"[bold red]{detector_report.total_findings}[/bold red]"
                if detector_report.total_findings
                else "0"
            ),
        )

        console.print(summary_table)

        if ingest_result.ignored_files:
            console.print(f"[dim]Ignored files: {', '.join(ingest_result.ignored_files)}[/dim]")

        if findings:
            secrets_table = Table(title="Detected & Redacted Secrets", show_header=True)
            secrets_table.add_column("Category", style="magenta")
            secrets_table.add_column("Description", style="white")
            secrets_table.add_column("Masked Preview", style="yellow")
            secrets_table.add_column("Replacement Token", style="red")

            for f in findings:
                secrets_table.add_row(
                    f.category,
                    f.description,
                    f.masked_text,
                    f.replacement,
                )
            console.print(secrets_table)

        if detector_report.findings:
            risk_table = Table(title="Detected Static Risk Findings", show_header=True)
            risk_table.add_column("Severity", style="bold")
            risk_table.add_column("Rule ID", style="cyan")
            risk_table.add_column("Concept", style="magenta")
            risk_table.add_column("Location", style="yellow")
            risk_table.add_column("Description", style="white")

            for rf in detector_report.findings:
                sev_color = (
                    "bold red" if rf.severity.value in ("CRITICAL", "HIGH") else "bold yellow"
                )
                loc = f"{rf.file_path}:{rf.line_number}" if rf.line_number else rf.file_path
                risk_table.add_row(
                    f"[{sev_color}]{rf.severity.value}[/{sev_color}]",
                    rf.rule_id,
                    rf.concept_id,
                    loc,
                    rf.title,
                )
            console.print(risk_table)

        if detector_report.ranked_hunks:
            hunk_table = Table(title="Ranked Diff Hunks by Risk Score", show_header=True)
            hunk_table.add_column("Rank", justify="center", style="bold cyan")
            hunk_table.add_column("File", style="white")
            hunk_table.add_column("Range", style="yellow")
            hunk_table.add_column("Risk Score", justify="right")
            hunk_table.add_column("Triggered Rules", style="magenta")

            for rh in detector_report.ranked_hunks:
                rules_display = (
                    ", ".join(rh.triggered_rule_ids) if rh.triggered_rule_ids else "[dim]none[/dim]"
                )
                score_color = (
                    "bold red"
                    if rh.risk_score >= 10.0
                    else ("bold yellow" if rh.risk_score >= 5.0 else "green")
                )
                hunk_table.add_row(
                    str(rh.rank),
                    rh.file_path,
                    rh.line_range,
                    f"[{score_color}]{rh.risk_score:.2f}[/{score_color}]",
                    rules_display,
                )
            console.print(hunk_table)

        question_plans = create_question_plans(detector_report, max_questions=3)
        if question_plans:
            plan_table = Table(
                title="Planned Comprehension Questions (Stage 3 Planning)",
                show_header=True,
            )
            plan_table.add_column("Rank", justify="center", style="bold cyan")
            plan_table.add_column("Type", style="magenta")
            plan_table.add_column("Concept", style="green")
            plan_table.add_column("Target Range", style="yellow")
            plan_table.add_column("Strategy", style="blue")
            plan_table.add_column("Stem Template", style="white")

            for p in question_plans:
                loc = f"{p.file_path}:{p.start_line}-{p.end_line}"
                stem_prev = (
                    p.stem_template[:50] + "..." if len(p.stem_template) > 50 else p.stem_template
                )
                plan_table.add_row(
                    str(p.hunk.rank),
                    p.recommended_type.value,
                    p.target_concept,
                    loc,
                    p.strategy,
                    stem_prev,
                )
            console.print(plan_table)

        if generate and question_plans:
            config, _ = load_config()
            diff_hash = DiskCache.compute_hash(redacted_ingest.raw_diff)
            provider: LLMProvider
            if os.getenv("ANTHROPIC_API_KEY"):
                provider = AnthropicProvider(
                    model=config.model,
                    max_cost_dollars=config.max_cost_dollars,
                    token_budget=config.token_budget,
                )
            else:
                provider = FakeProvider(
                    model=config.model,
                    max_cost_dollars=config.max_cost_dollars,
                    token_budget=config.token_budget,
                )
                for plan in question_plans:
                    provider.enqueue_structured(
                        {
                            "type": plan.recommended_type.value,
                            "concept_id": plan.target_concept,
                            "hunk_rank": plan.hunk.rank,
                            "file_path": plan.file_path,
                            "start_line": plan.start_line,
                            "end_line": plan.end_line,
                            "snippet": plan.snippet,
                            "stem": f"Comprehension check: {plan.stem_template}",
                            "choices": [
                                {
                                    "key": "A",
                                    "text": "Correct expected behavior matching diff",
                                    "explanation": "Matches implementation",
                                },
                                {
                                    "key": "B",
                                    "text": "Incorrect alternative behavior",
                                    "explanation": "Does not match diff",
                                },
                            ],
                            "answer_key": "A",
                            "explanation": f"Explanation for {plan.target_concept}",
                        }
                    )
                    provider.enqueue_structured(
                        {"selected_key": "A", "confidence": 1.0, "reasoning": "Matches diff"}
                    )
                    provider.enqueue_structured(
                        {"is_ambiguous": False, "defensible_choices": ["A"], "reasoning": "Clear"}
                    )

            cached_provider = CachedLLMProvider(
                provider,
                cache_dir=config.cache_dir,
                diff_hash=diff_hash,
            )
            generator_inst = QuestionGenerator(cached_provider)
            accepted_qs, rejections_list = generator_inst.generate_quiz(
                question_plans, redacted_ingest
            )

            gen_table = Table(
                title="Generated Questions & Quality Gate Results",
                show_header=True,
            )
            gen_table.add_column("#", justify="center", style="bold cyan")
            gen_table.add_column("Type", style="magenta")
            gen_table.add_column("Concept", style="green")
            gen_table.add_column("Stem Preview", style="white")
            gen_table.add_column("Answer Key", justify="center", style="bold yellow")
            gen_table.add_column("Quality Gate Status", style="bold")

            for idx, q in enumerate(accepted_qs, start=1):
                gen_table.add_row(
                    str(idx),
                    q.type.value,
                    q.concept_id,
                    q.stem[:50] + "..." if len(q.stem) > 50 else q.stem,
                    q.answer_key,
                    "[bold green]PASSED[/bold green]",
                )
            for idx, r in enumerate(rejections_list, start=len(accepted_qs) + 1):
                gen_table.add_row(
                    str(idx),
                    "-",
                    "-",
                    f"[dim]{r.reason[:50]}...[/dim]",
                    "-",
                    f"[bold red]REJECTED ({r.step})[/bold red]",
                )
            console.print(gen_table)

        injection_warnings = scan_for_injection_markers(redacted_ingest.raw_diff)
        if injection_warnings:
            injection_table = Table(
                title="Potential Prompt Injection Markers Detected",
                show_header=True,
            )
            injection_table.add_column("Warning", style="bold yellow")
            for w in injection_warnings:
                injection_table.add_row(w)
            console.print(injection_table)

        encapsulated_payload = encapsulate_diff(redacted_ingest.raw_diff)
        console.print(
            Panel(
                encapsulated_payload,
                title="Redacted Diff Payload (LLM Encapsulated)",
                border_style="cyan",
            )
        )
        console.print(
            "[bold green]Dry-run complete. "
            "All secrets redacted locally prior to any network call.[/bold green]"
        )
        raise typer.Exit(code=0)

    # Safe CI / non-TTY detection: never hang, exit 0 with notice
    is_ci = os.getenv("CI", "").lower() in ("true", "1")
    if not sys.stdin.isatty() or is_ci:
        console.print(
            "[dim]Non-interactive terminal or CI environment detected. "
            "Skipping comprehension quiz.[/dim]"
        )
        raise typer.Exit(code=0)

    console.print(
        "[yellow]Interactive quiz pipeline is scheduled for Stage 4 (Session + Grading). "
        "Run 'emc doctor' to verify system readiness.[/yellow]"
    )
    raise typer.Exit(code=0)


@app.command(name="detect")
def detect_cmd(
    staged: Annotated[bool, typer.Option("--staged", help="Analyze staged git changes.")] = False,
    commit: Annotated[
        Optional[str],
        typer.Option("--commit", help="Analyze specific commit or range (e.g. HEAD~1)."),
    ] = None,
    stdin: Annotated[bool, typer.Option("--stdin", help="Read diff from standard input.")] = False,
    as_json: Annotated[
        bool, typer.Option("--json", help="Output risk report as machine-readable JSON.")
    ] = False,
) -> None:
    """Run deterministic static risk detectors and output findings and ranked hunks."""
    try:
        ingest_result = ingest_diff(staged=staged, commit=commit, use_stdin=stdin)
    except GitError as exc:
        console.print(f"[bold red]Git Error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    if ingest_result.is_empty and not ingest_result.raw_diff.strip():
        console.print("[yellow]No diff changes found to analyze.[/yellow]")
        raise typer.Exit(code=0)

    redactor = Redactor()
    redacted_ingest, _ = redactor.redact_ingest_result(ingest_result)
    detector_report = run_detector_pipeline(redacted_ingest)

    if as_json:
        data = {
            "total_findings": detector_report.total_findings,
            "critical_count": detector_report.critical_count,
            "high_count": detector_report.high_count,
            "medium_count": detector_report.medium_count,
            "low_count": detector_report.low_count,
            "highest_risk_score": detector_report.highest_risk_score,
            "findings": [f.to_dict() for f in detector_report.findings],
            "ranked_hunks": [
                {
                    "rank": rh.rank,
                    "file_path": rh.file_path,
                    "line_range": rh.line_range,
                    "risk_score": rh.risk_score,
                    "rules": rh.triggered_rule_ids,
                    "primary_concept": rh.primary_concept,
                }
                for rh in detector_report.ranked_hunks
            ],
        }
        typer.echo(json.dumps(data, indent=2))
        raise typer.Exit(code=0)

    summary_table = Table(title="Diff Detection & Ranking Summary", show_header=True)
    summary_table.add_column("Property", style="cyan")
    summary_table.add_column("Value", style="green")

    summary_table.add_row("Files Analyzed", str(ingest_result.total_files))
    summary_table.add_row("Total Hunks", str(ingest_result.total_hunks))
    summary_table.add_row(
        "Additions / Deletions",
        f"+{ingest_result.total_additions} / -{ingest_result.total_deletions}",
    )
    summary_table.add_row(
        "Risks Detected",
        (
            f"[bold red]{detector_report.total_findings}[/bold red]"
            if detector_report.total_findings
            else "0"
        ),
    )
    if detector_report.ranked_hunks:
        summary_table.add_row(
            "Highest Hunk Risk",
            f"{detector_report.highest_risk_score:.2f}",
        )
    console.print(summary_table)

    if detector_report.findings:
        risk_table = Table(title="Detected Static Risk Findings", show_header=True)
        risk_table.add_column("Severity", style="bold")
        risk_table.add_column("Rule ID", style="cyan")
        risk_table.add_column("Concept", style="magenta")
        risk_table.add_column("Location", style="yellow")
        risk_table.add_column("Description", style="white")

        for rf in detector_report.findings:
            sev_color = "bold red" if rf.severity.value in ("CRITICAL", "HIGH") else "bold yellow"
            loc = f"{rf.file_path}:{rf.line_number}" if rf.line_number else rf.file_path
            risk_table.add_row(
                f"[{sev_color}]{rf.severity.value}[/{sev_color}]",
                rf.rule_id,
                rf.concept_id,
                loc,
                rf.title,
            )
        console.print(risk_table)

    if detector_report.ranked_hunks:
        hunk_table = Table(title="Ranked Diff Hunks by Risk Score", show_header=True)
        hunk_table.add_column("Rank", justify="center", style="bold cyan")
        hunk_table.add_column("File", style="white")
        hunk_table.add_column("Range", style="yellow")
        hunk_table.add_column("Risk Score", justify="right")
        hunk_table.add_column("Triggered Rules", style="magenta")

        for rh in detector_report.ranked_hunks:
            rules_display = (
                ", ".join(rh.triggered_rule_ids) if rh.triggered_rule_ids else "[dim]none[/dim]"
            )
            score_color = (
                "bold red"
                if rh.risk_score >= 10.0
                else ("bold yellow" if rh.risk_score >= 5.0 else "green")
            )
            hunk_table.add_row(
                str(rh.rank),
                rh.file_path,
                rh.line_range,
                f"[{score_color}]{rh.risk_score:.2f}[/{score_color}]",
                rules_display,
            )
        console.print(hunk_table)
    raise typer.Exit(code=0)


@app.command(name="generate")
def generate_cmd(
    staged: Annotated[bool, typer.Option("--staged", help="Analyze staged git changes.")] = False,
    commit: Annotated[
        Optional[str],
        typer.Option("--commit", help="Analyze specific commit or range (e.g. HEAD~1)."),
    ] = None,
    stdin: Annotated[bool, typer.Option("--stdin", help="Read diff from standard input.")] = False,
    provider_name: Annotated[
        str,
        typer.Option("--provider", "-p", help="Provider to use: 'fake', 'anthropic', or 'local'."),
    ] = "fake",
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Output generated questions and quality gate results as JSON."),
    ] = False,
    max_questions: Annotated[
        int, typer.Option("--max-questions", "-n", help="Maximum questions to generate.")
    ] = 3,
) -> None:
    """Generate comprehension questions with 4-step quality gate validation."""
    try:
        ingest_result = ingest_diff(staged=staged, commit=commit, use_stdin=stdin)
    except GitError as exc:
        console.print(f"[bold red]Git Error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    if ingest_result.is_empty and not ingest_result.raw_diff.strip():
        if as_json:
            typer.echo(
                json.dumps(
                    {
                        "questions": [],
                        "rejections": [],
                        "summary": "No diff changes found",
                    }
                )
            )
        else:
            console.print("[yellow]No diff changes found to analyze.[/yellow]")
        raise typer.Exit(code=0)

    redactor = Redactor()
    redacted_ingest, findings = redactor.redact_ingest_result(ingest_result)
    detector_report = run_detector_pipeline(redacted_ingest)
    plans = create_question_plans(detector_report, max_questions=max_questions)

    if not plans:
        if as_json:
            typer.echo(
                json.dumps(
                    {
                        "questions": [],
                        "rejections": [],
                        "summary": "No hunks available for planning",
                    }
                )
            )
        else:
            console.print("[yellow]No hunks available for question generation.[/yellow]")
        raise typer.Exit(code=0)

    config, _ = load_config()
    diff_hash = DiskCache.compute_hash(redacted_ingest.raw_diff)

    provider: LLMProvider
    if provider_name.lower() == "anthropic":
        provider = AnthropicProvider(
            model=config.model,
            max_cost_dollars=config.max_cost_dollars,
            token_budget=config.token_budget,
        )
    elif provider_name.lower() == "local":
        provider = LocalProvider(
            model=config.model,
            max_cost_dollars=config.max_cost_dollars,
            token_budget=config.token_budget,
        )
    else:
        fake_p = FakeProvider(
            model=config.model,
            max_cost_dollars=config.max_cost_dollars,
            token_budget=config.token_budget,
        )
        for plan in plans:
            fake_p.enqueue_structured(
                {
                    "type": plan.recommended_type.value,
                    "concept_id": plan.target_concept,
                    "hunk_rank": plan.hunk.rank,
                    "file_path": plan.file_path,
                    "start_line": plan.start_line,
                    "end_line": plan.end_line,
                    "snippet": plan.snippet,
                    "stem": f"Comprehension check: {plan.stem_template}",
                    "choices": [
                        {
                            "key": "A",
                            "text": "Correct expected behavior matching diff",
                            "explanation": "Matches implementation",
                        },
                        {
                            "key": "B",
                            "text": "Incorrect alternative behavior",
                            "explanation": "Does not match diff",
                        },
                    ],
                    "answer_key": "A",
                    "explanation": f"Explanation for {plan.target_concept}",
                }
            )
            fake_p.enqueue_structured(
                {
                    "selected_key": "A",
                    "confidence": 1.0,
                    "reasoning": "Matches diff",
                }
            )
            fake_p.enqueue_structured(
                {
                    "is_ambiguous": False,
                    "defensible_choices": ["A"],
                    "reasoning": "Clear",
                }
            )
        provider = fake_p

    cached_provider = CachedLLMProvider(
        provider,
        cache_dir=config.cache_dir,
        diff_hash=diff_hash,
    )
    generator_inst = QuestionGenerator(cached_provider)
    questions, rejections = generator_inst.generate_quiz(plans, redacted_ingest)

    if as_json:
        output_payload = {
            "questions": [q.model_dump() for q in questions],
            "rejections": [r.model_dump() for r in rejections],
            "total_generated": len(questions),
            "total_rejected": len(rejections),
            "usage": cached_provider.total_usage.model_dump(),
            "cost_usd": cached_provider.total_cost_usd,
        }
        typer.echo(json.dumps(output_payload, indent=2))
        raise typer.Exit(code=0)

    table = Table(title="Generated Comprehension Questions", show_header=True)
    table.add_column("#", justify="center", style="bold cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Concept", style="green")
    table.add_column("Stem", style="white")
    table.add_column("Key", justify="center", style="bold yellow")
    table.add_column("Quality Gate", style="bold")

    for idx, q in enumerate(questions, start=1):
        table.add_row(
            str(idx),
            q.type.value,
            q.concept_id,
            q.stem[:50] + "..." if len(q.stem) > 50 else q.stem,
            q.answer_key,
            "[bold green]PASSED[/bold green]",
        )
    for idx, r in enumerate(rejections, start=len(questions) + 1):
        table.add_row(
            str(idx),
            "-",
            "-",
            f"[dim]{r.reason[:50]}...[/dim]",
            "-",
            f"[bold red]REJECTED ({r.step})[/bold red]",
        )
    console.print(table)
    raise typer.Exit(code=0)


@app.command(name="explain")
def explain_cmd(
    staged: Annotated[bool, typer.Option("--staged", help="Explain staged git changes.")] = False,
    commit: Annotated[
        Optional[str],
        typer.Option("--commit", help="Explain specific commit or range."),
    ] = None,
) -> None:
    """Walkthrough and explain code diff without interactive quiz."""
    console.print(
        "[yellow]Diff walkthrough explanation is scheduled for Stage 4. "
        "Run 'emc doctor' to verify system readiness.[/yellow]"
    )
    raise typer.Exit(code=0)


@app.command(name="report")
def report_cmd() -> None:
    """Display comprehension mastery report across concept Leitner boxes."""
    console.print(
        "[yellow]Mastery reporting is scheduled for Stage 5 (Ledger + Mastery). "
        "Run 'emc doctor' to check local state.[/yellow]"
    )
    raise typer.Exit(code=0)


@app.command(name="review")
def review_cmd() -> None:
    """Replay questions targeting previously missed or weak concepts."""
    console.print(
        "[yellow]Concept review session is scheduled for Stage 5 (Ledger + Mastery). "
        "Run 'emc doctor' to check local state.[/yellow]"
    )
    raise typer.Exit(code=0)


@app.command(name="eval")
def eval_cmd(
    baseline: Annotated[
        bool,
        typer.Option("--baseline", help="Run ablation against naive single-prompt baseline."),
    ] = False,
) -> None:
    """Run benchmark evaluation suite across seeded bug diffs."""
    console.print(
        "[yellow]Evaluation suite is scheduled for Stage 7 (Eval). "
        "Run 'emc doctor' to verify test readiness.[/yellow]"
    )
    raise typer.Exit(code=0)


@hook_app.command(name="install")
def hook_install(
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite existing pre-commit hook")
    ] = False,
) -> None:
    """Install emc git pre-commit hook into current repository."""
    hooks_dir = _get_git_hooks_dir()
    if not hooks_dir or not hooks_dir.parent.exists():
        console.print("[bold red]Not inside a git repository root.[/bold red]")
        raise typer.Exit(code=1)

    hooks_dir.mkdir(parents=True, exist_ok=True)
    pre_commit_file = hooks_dir / "pre-commit"

    if pre_commit_file.exists():
        content = pre_commit_file.read_text(encoding="utf-8")
        if "emc quiz" in content:
            console.print("[bold green]emc pre-commit hook is already installed.[/bold green]")
            return
        if not force:
            console.print(
                "[yellow]A pre-commit hook already exists. "
                "Use --force to overwrite, or append 'emc quiz --staged' manually.[/yellow]"
            )
            raise typer.Exit(code=1)

    script = "#!/usr/bin/env sh\n# explain-my-own-code pre-commit hook\nemc quiz --staged\n"
    pre_commit_file.write_text(script, encoding="utf-8")
    try:
        pre_commit_file.chmod(0o755)
    except Exception:
        pass
    console.print(f"[bold green]Installed emc pre-commit hook to {pre_commit_file}[/bold green]")


@hook_app.command(name="uninstall")
def hook_uninstall(
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f", help="Remove hook even if it does not contain emc identifier"
        ),
    ] = False,
) -> None:
    """Uninstall emc git pre-commit hook."""
    hooks_dir = _get_git_hooks_dir()
    pre_commit_file = (hooks_dir / "pre-commit") if hooks_dir else Path(".git/hooks/pre-commit")

    if not pre_commit_file.exists():
        console.print(f"[yellow]No hook found at {pre_commit_file}[/yellow]")
        return

    content = pre_commit_file.read_text(encoding="utf-8")
    if "emc" not in content and not force:
        console.print(
            "[yellow]Existing pre-commit hook does not appear to belong to emc. "
            "Use --force to remove anyway.[/yellow]"
        )
        raise typer.Exit(code=1)

    pre_commit_file.unlink()
    console.print(f"[bold green]Removed {pre_commit_file}[/bold green]")


if __name__ == "__main__":
    app()
