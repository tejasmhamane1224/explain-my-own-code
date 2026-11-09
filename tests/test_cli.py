"""Tests for emc CLI commands."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from emc import __version__
from emc.cli import app


def test_cli_help(cli_runner: CliRunner) -> None:
    """Verify emc --help displays help text and all required subcommands."""
    result = cli_runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "explain-my-own-code" in result.stdout
    assert "doctor" in result.stdout
    assert "config" in result.stdout
    assert "init" in result.stdout
    assert "hook" in result.stdout
    assert "quiz" in result.stdout
    assert "explain" in result.stdout
    assert "report" in result.stdout
    assert "review" in result.stdout
    assert "eval" in result.stdout


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


def test_cli_config_display_with_corrupt_file(
    cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify emc config alerts developer when .emc.toml is malformed."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".emc.toml").write_text("invalid = [toml\n", encoding="utf-8")
    result = cli_runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "Configuration Warning" in result.stdout


def test_cli_init_command(
    cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify emc init creates a valid .emc.toml and .emc/ directory."""
    monkeypatch.chdir(tmp_path)
    result = cli_runner.invoke(app, ["init"])
    assert result.exit_code == 0
    config_file = tmp_path / ".emc.toml"
    assert config_file.exists()
    assert (tmp_path / ".emc").is_dir()
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


def test_hook_install_and_uninstall(
    cli_runner: CliRunner, temp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify hook installation and uninstallation inside a git repo."""
    monkeypatch.chdir(temp_git_repo)

    # 1. Install
    result = cli_runner.invoke(app, ["hook", "install"])
    assert result.exit_code == 0
    hook_file = temp_git_repo / ".git" / "hooks" / "pre-commit"
    assert hook_file.exists()
    assert "emc quiz --staged" in hook_file.read_text(encoding="utf-8")

    # 2. Idempotent install
    result_dup = cli_runner.invoke(app, ["hook", "install"])
    assert result_dup.exit_code == 0
    assert "already installed" in result_dup.stdout

    # 3. Uninstall
    result_un = cli_runner.invoke(app, ["hook", "uninstall"])
    assert result_un.exit_code == 0
    assert not hook_file.exists()

    # 4. Uninstall when already gone
    result_un_again = cli_runner.invoke(app, ["hook", "uninstall"])
    assert result_un_again.exit_code == 0
    assert "No hook found" in result_un_again.stdout


def test_hook_foreign_hook_protection(
    cli_runner: CliRunner, temp_git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify hook commands protect foreign pre-commit hooks unless --force is used."""
    monkeypatch.chdir(temp_git_repo)
    hooks_dir = temp_git_repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    foreign_hook = hooks_dir / "pre-commit"
    foreign_hook.write_text("#!/bin/sh\necho custom_tool\n", encoding="utf-8")

    # Install without force should refuse to clobber
    res_install = cli_runner.invoke(app, ["hook", "install"])
    assert res_install.exit_code == 1
    assert "already exists" in res_install.stdout

    # Uninstall without force should refuse to remove foreign hook
    res_uninstall = cli_runner.invoke(app, ["hook", "uninstall"])
    assert res_uninstall.exit_code == 1
    assert "does not appear to belong to emc" in res_uninstall.stdout

    # Uninstall with force should succeed
    res_uninstall_force = cli_runner.invoke(app, ["hook", "uninstall", "--force"])
    assert res_uninstall_force.exit_code == 0
    assert not foreign_hook.exists()


def test_hook_install_outside_repo(
    cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify hook install outside a git repo fails gracefully."""
    not_repo = tmp_path / "not_repo"
    not_repo.mkdir()
    monkeypatch.chdir(not_repo)
    result = cli_runner.invoke(app, ["hook", "install"])
    assert result.exit_code == 1
    assert "Not inside a git repository root" in result.stdout


def test_cli_quiz_skip_and_ci(cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify quiz --skip and CI environments exit 0 without hanging."""
    # --skip flag
    res_skip = cli_runner.invoke(app, ["quiz", "--skip"])
    assert res_skip.exit_code == 0
    assert "skipped by developer" in res_skip.stdout

    # CI environment
    monkeypatch.setenv("CI", "true")
    res_ci = cli_runner.invoke(app, ["quiz"])
    assert res_ci.exit_code == 0
    assert "Skipping comprehension" in res_ci.stdout


def test_cli_future_stage_commands(cli_runner: CliRunner) -> None:
    """Verify future stage subcommands render roadmap status."""
    for cmd in ["explain"]:
        res = cli_runner.invoke(app, [cmd])
        assert res.exit_code == 0
        assert "scheduled for Stage" in res.stdout
