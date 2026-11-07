"""Command Line Interface for explain-my-own-code (emc)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from emc import __version__
from emc.config import load_config
from emc.doctor import render_doctor_report, run_doctor_checks

app = typer.Typer(
    name="emc",
    help=(
        "explain-my-own-code (emc) — "
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
    config, path = load_config()
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
    console.print(f"[bold green]Successfully initialized {target.resolve()}[/bold green]")


@hook_app.command(name="install")
def hook_install() -> None:
    """Install emc git pre-commit hook into current repository."""
    git_dir = Path(".git")
    if not git_dir.is_dir():
        console.print("[bold red]Not inside a git repository root.[/bold red]")
        raise typer.Exit(code=1)

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    pre_commit_file = hooks_dir / "pre-commit"

    script = "#!/usr/bin/env sh\n# explain-my-own-code pre-commit hook\nemc quiz --staged\n"
    pre_commit_file.write_text(script, encoding="utf-8")
    try:
        pre_commit_file.chmod(0o755)
    except Exception:
        pass
    console.print("[bold green]Installed emc pre-commit hook to .git/hooks/pre-commit[/bold green]")


@hook_app.command(name="uninstall")
def hook_uninstall() -> None:
    """Uninstall emc git pre-commit hook."""
    pre_commit_file = Path(".git/hooks/pre-commit")
    if pre_commit_file.exists():
        pre_commit_file.unlink()
        console.print("[bold green]Removed .git/hooks/pre-commit[/bold green]")
    else:
        console.print("[yellow]No hook found at .git/hooks/pre-commit[/yellow]")


if __name__ == "__main__":
    app()
