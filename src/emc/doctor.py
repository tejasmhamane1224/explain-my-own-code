"""Diagnostics and health checks for explain-my-own-code (emc)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from emc.config import load_config


class CheckStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass
class DoctorCheck:
    name: str
    status: CheckStatus
    summary: str
    details: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "summary": self.summary,
            "details": self.details,
        }


def mask_secret(secret: str | None) -> str:
    """Mask sensitive string leaving only small prefix and suffix visible."""
    if not secret:
        return "<not set>"
    if len(secret) <= 8:
        return "***"
    return f"{secret[:6]}...{secret[-4:]}"


def check_git_installed() -> DoctorCheck:
    """Check whether git executable is found in PATH and runnable."""
    git_path = shutil.which("git")
    if not git_path:
        return DoctorCheck(
            name="Git Installed",
            status=CheckStatus.FAIL,
            summary="git executable not found in PATH",
            details="Ensure Git is installed and available in your system PATH.",
        )
    try:
        proc = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
            shell=(sys.platform == "win32"),
        )
        version_str = proc.stdout.strip()
        return DoctorCheck(
            name="Git Installed",
            status=CheckStatus.PASS,
            summary=version_str,
            details=f"Binary location: {git_path}",
        )
    except Exception as exc:
        return DoctorCheck(
            name="Git Installed",
            status=CheckStatus.FAIL,
            summary="Error executing git --version",
            details=str(exc),
        )


def check_git_repo(cwd: Path) -> DoctorCheck:
    """Check if current working directory is inside a Git repository."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=5,
            shell=(sys.platform == "win32"),
        )
        if proc.returncode == 0 and proc.stdout.strip() == "true":
            # Check git root and current branch
            root_proc = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=5,
                shell=(sys.platform == "win32"),
            )
            root_dir = root_proc.stdout.strip()
            return DoctorCheck(
                name="Git Repository",
                status=CheckStatus.PASS,
                summary="Active git repository detected",
                details=f"Root: {root_dir}",
            )
        return DoctorCheck(
            name="Git Repository",
            status=CheckStatus.WARN,
            summary="Not inside a git repository",
            details=(
                f"Directory '{cwd}' is not managed by git. "
                "Diffs must be provided via stdin or file."
            ),
        )
    except Exception as exc:
        return DoctorCheck(
            name="Git Repository",
            status=CheckStatus.WARN,
            summary="Unable to probe git status",
            details=str(exc),
        )


def check_anthropic_api_key() -> DoctorCheck:
    """Check whether ANTHROPIC_API_KEY environment variable is configured."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if key and key.strip():
        masked = mask_secret(key.strip())
        return DoctorCheck(
            name="Anthropic API Key",
            status=CheckStatus.PASS,
            summary=f"Key detected ({masked})",
            details="ANTHROPIC_API_KEY is configured for LLM operations.",
        )
    return DoctorCheck(
        name="Anthropic API Key",
        status=CheckStatus.WARN,
        summary="ANTHROPIC_API_KEY is not set",
        details=(
            "Real LLM quiz generation requires ANTHROPIC_API_KEY. "
            "Test suite and fake provider do not require it."
        ),
    )


def check_model_config(config_model: str) -> DoctorCheck:
    """Check model configuration from environment or config."""
    env_model = os.getenv("EMC_MODEL")
    active_model = env_model or config_model
    source = "EMC_MODEL env" if env_model else "default/config"
    return DoctorCheck(
        name="EMC Model",
        status=CheckStatus.PASS,
        summary=f"{active_model} (via {source})",
        details="Model identifier configured for question planning and evaluation.",
    )


def check_emc_config(cwd: Path) -> DoctorCheck:
    """Check whether .emc.toml configuration file is present and valid."""
    config, path = load_config(cwd / ".emc.toml" if (cwd / ".emc.toml").is_file() else None)
    if path is not None:
        return DoctorCheck(
            name="EMC Configuration",
            status=CheckStatus.PASS,
            summary=f"Loaded from {path.name} (mode: {config.mode})",
            details=f"Path: {path}",
        )
    return DoctorCheck(
        name="EMC Configuration",
        status=CheckStatus.PASS,
        summary=f"Using defaults (mode: {config.mode}, skip_allowed: {config.skip_allowed})",
        details="No .emc.toml found; run 'emc init' or create .emc.toml to customize.",
    )


def check_python_runtime() -> DoctorCheck:
    """Verify running on Python 3.12 or newer."""
    major, minor, micro = sys.version_info[:3]
    version_str = f"Python {major}.{minor}.{micro}"
    if major > 3 or (major == 3 and minor >= 12):
        return DoctorCheck(
            name="Python Runtime",
            status=CheckStatus.PASS,
            summary=f"{version_str} (>= 3.12 requirement satisfied)",
            details=sys.executable,
        )
    return DoctorCheck(
        name="Python Runtime",
        status=CheckStatus.FAIL,
        summary=f"{version_str} is unsupported",
        details="emc requires Python 3.12 or newer.",
    )


def check_cache_and_ledger(cwd: Path) -> DoctorCheck:
    """Check .emc directory permissions and state."""
    emc_dir = cwd / ".emc"
    if emc_dir.exists():
        if emc_dir.is_dir():
            ledger = emc_dir / "ledger.jsonl"
            ledger_info = (
                f"ledger exists ({ledger.stat().st_size} bytes)"
                if ledger.exists()
                else "ledger not initialized"
            )
            return DoctorCheck(
                name="EMC Local State",
                status=CheckStatus.PASS,
                summary=f"Found .emc/ directory ({ledger_info})",
                details=str(emc_dir),
            )
        return DoctorCheck(
            name="EMC Local State",
            status=CheckStatus.WARN,
            summary=".emc exists but is not a directory",
            details=str(emc_dir),
        )
    return DoctorCheck(
        name="EMC Local State",
        status=CheckStatus.PASS,
        summary=".emc directory will be created on first quiz run",
        details="Local ledger and response cache initialized lazily.",
    )


def run_doctor_checks(cwd: Path | None = None) -> list[DoctorCheck]:
    """Execute all system and environment diagnostic checks."""
    base_dir = cwd or Path.cwd()
    config, _ = load_config()

    return [
        check_python_runtime(),
        check_git_installed(),
        check_git_repo(base_dir),
        check_anthropic_api_key(),
        check_model_config(config.model),
        check_emc_config(base_dir),
        check_cache_and_ledger(base_dir),
    ]


def render_doctor_report(
    checks: list[DoctorCheck],
    console: Console | None = None,
    verbose: bool = False,
) -> int:
    """Render diagnostics using Rich and return exit code (0 = success, 1 = fatal check failed)."""
    con = console or Console()

    table = Table(
        title="explain-my-own-code (emc) System Doctor",
        title_style="bold cyan",
        show_header=True,
        header_style="bold magenta",
        expand=True,
    )
    table.add_column("Status", width=10, justify="center")
    table.add_column("Component", width=22, style="bold")
    table.add_column("Details", style="dim")

    has_fail = False
    has_warn = False

    for c in checks:
        if c.status == CheckStatus.PASS:
            status_text = "[bold green]PASS[/bold green]"
        elif c.status == CheckStatus.WARN:
            status_text = "[bold yellow]WARN[/bold yellow]"
            has_warn = True
        else:
            status_text = "[bold red]FAIL[/bold red]"
            has_fail = True

        detail_text = c.summary
        if verbose and c.details:
            detail_text += f"\n[italic]{c.details}[/italic]"

        table.add_row(status_text, c.name, detail_text)

    con.print()
    con.print(table)
    con.print()

    if has_fail:
        con.print(
            Panel(
                "[bold red]One or more critical checks failed.[/bold red]\n"
                "Please fix the reported errors before running emc.",
                border_style="red",
            )
        )
        return 1

    if has_warn:
        warning_msg = (
            "[bold yellow]All required dependencies are satisfied, "
            "with some warnings.[/bold yellow]\n"
            "emc is ready for local offline testing. Configure missing keys for live model quizzes."
        )
        con.print(Panel(warning_msg, border_style="yellow"))
        return 0

    con.print(
        Panel(
            "[bold green]All systems operational![/bold green]\n"
            "emc is fully configured and ready to analyze diffs.",
            border_style="green",
        )
    )
    return 0
