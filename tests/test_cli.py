"""Tests for emc CLI commands."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from emc import __version__
from emc.cli import app


def test_cli_help(cli_runner: CliRunner) -> None:
    """Verify emc --help displays help text and subcommands."""
    result = cli_runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "explain-my-own-code" in result.stdout
    assert "doctor" in result.stdout
    assert "config" in result.stdout
    assert "init" in result.stdout
    assert "hook" in result.stdout


def test_cli_version(cli_runner: CliRunner) -> None:
    """Verify emc --version displays correct version string."""
    result = cli_runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_cli_config_display(cli_runner: CliRunner) -> None:
    """Verify emc config displays active settings."""
    result = cli_runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "Configuration File:" in result.stdout
    assert "Mode:" in result.stdout
    assert "Model:" in result.stdout


def test_cli_init_command(
    cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify emc init creates a valid .emc.toml configuration file."""
    monkeypatch.chdir(tmp_path)
    result = cli_runner.invoke(app, ["init"])
    assert result.exit_code == 0
    config_file = tmp_path / ".emc.toml"
    assert config_file.exists()
    content = config_file.read_text(encoding="utf-8")
    assert "[emc]" in content
    assert 'mode = "warn"' in content

    # Calling init again without --force should warn
    result_second = cli_runner.invoke(app, ["init"])
    assert result_second.exit_code == 1
    assert "already exists" in result_second.stdout

    # With --force it should succeed
    result_force = cli_runner.invoke(app, ["init", "--force"])
    assert result_force.exit_code == 0


def test_hook_help(cli_runner: CliRunner) -> None:
    """Verify emc hook --help shows install and uninstall options."""
    result = cli_runner.invoke(app, ["hook", "--help"])
    assert result.exit_code == 0
    assert "install" in result.stdout
    assert "uninstall" in result.stdout
