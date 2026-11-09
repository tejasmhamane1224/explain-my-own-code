"""Git hook management (pre-commit and commit-msg) for explain-my-own-code (emc)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from emc.gate.trailer import append_commit_trailer, load_staged_trailer

PRE_COMMIT_MARKER = "# explain-my-own-code pre-commit hook"
COMMIT_MSG_MARKER = "# explain-my-own-code commit-msg hook"

PRE_COMMIT_SCRIPT = f"#!/usr/bin/env sh\n{PRE_COMMIT_MARKER}\nemc quiz --staged\n"

COMMIT_MSG_SCRIPT = f'#!/usr/bin/env sh\n{COMMIT_MSG_MARKER}\nemc hook commit-msg "$1"\n'


class HookError(Exception):
    """Base error for git hook operations."""

    pass


class ForeignHookError(HookError):
    """Raised when an existing foreign hook would be overwritten without --force."""

    pass


@dataclass
class HookInstallResult:
    """Result of hook installation."""

    pre_commit_installed: bool
    pre_commit_status: str  # "installed", "already_installed", "overwritten"
    commit_msg_installed: bool
    commit_msg_status: str  # "installed", "already_installed", "overwritten", "skipped"
    hooks_dir: Path
    message: str


@dataclass
class HookUninstallResult:
    """Result of hook uninstallation."""

    pre_commit_removed: bool
    pre_commit_restored: bool
    commit_msg_removed: bool
    commit_msg_restored: bool
    hooks_dir: Path | None
    message: str


def get_git_hooks_dir(start_path: Path | None = None) -> Path | None:
    """Resolve git hooks directory using git rev-parse --git-path hooks.

    Supports standard repositories, git worktrees, submodules, and subdirectories.
    Falls back to searching parent directories for .git/hooks.
    """
    cwd = (start_path or Path.cwd()).resolve()
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--git-path", "hooks"],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            shell=False,
        )
        raw_output = proc.stdout.strip()
        if raw_output:
            hook_path = Path(raw_output)
            if not hook_path.is_absolute():
                hook_path = (cwd / hook_path).resolve()
            return hook_path
    except Exception:
        pass

    # Fallback: traverse up to find .git directory or file
    current = cwd
    for d in [current, *current.parents]:
        git_target = d / ".git"
        if git_target.is_dir():
            return (git_target / "hooks").resolve()
        elif git_target.is_file():
            try:
                content = git_target.read_text(encoding="utf-8").strip()
                if content.startswith("gitdir:"):
                    gitdir_path = Path(content.split("gitdir:", 1)[1].strip())
                    if not gitdir_path.is_absolute():
                        gitdir_path = (d / gitdir_path).resolve()
                    return (gitdir_path / "hooks").resolve()
            except Exception:
                pass

    return None


def install_hooks(
    hooks_dir: Path | None = None,
    force: bool = False,
    install_commit_msg: bool = True,
    start_path: Path | None = None,
) -> HookInstallResult:
    """Install emc pre-commit and optional commit-msg git hooks.

    Guarantees:
      - Idempotent: Does not duplicate or modify already-installed emc hooks.
      - Foreign hook protection: Refuses to overwrite foreign hooks without force=True.
      - Backs up foreign hooks to .emc.bak when force=True is specified.
    """
    target_hooks_dir = hooks_dir or get_git_hooks_dir(start_path=start_path)
    if not target_hooks_dir or not (target_hooks_dir.parent.exists() or target_hooks_dir.exists()):
        raise HookError("Not inside a git repository root.")

    target_hooks_dir.mkdir(parents=True, exist_ok=True)

    pre_commit_file = target_hooks_dir / "pre-commit"
    commit_msg_file = target_hooks_dir / "commit-msg"

    # Upfront foreign hook validation before modifying any files
    if not force:
        if pre_commit_file.exists():
            c = pre_commit_file.read_text(encoding="utf-8")
            if "emc quiz" not in c:
                raise ForeignHookError(
                    "A pre-commit hook already exists. Use --force to overwrite, "
                    "or append 'emc quiz --staged' manually."
                )
        if install_commit_msg and commit_msg_file.exists():
            cm = commit_msg_file.read_text(encoding="utf-8")
            if "emc hook commit-msg" not in cm:
                raise ForeignHookError(
                    "A commit-msg hook already exists. Use --force to overwrite, "
                    "or append 'emc hook commit-msg \"$1\"' manually."
                )

    # 1. pre-commit hook
    pre_commit_status = "installed"
    if pre_commit_file.exists():
        content = pre_commit_file.read_text(encoding="utf-8")
        if "emc quiz" in content:
            pre_commit_status = "already_installed"
        else:
            # Back up foreign hook
            bak_file = target_hooks_dir / "pre-commit.emc.bak"
            bak_file.write_text(content, encoding="utf-8")
            pre_commit_status = "overwritten"

    if pre_commit_status != "already_installed":
        pre_commit_file.write_text(PRE_COMMIT_SCRIPT, encoding="utf-8")
        try:
            pre_commit_file.chmod(0o755)
        except Exception:
            pass

    # 2. commit-msg hook (optional)
    commit_msg_status = "skipped"
    if install_commit_msg:
        commit_msg_status = "installed"
        if commit_msg_file.exists():
            cm_content = commit_msg_file.read_text(encoding="utf-8")
            if "emc hook commit-msg" in cm_content:
                commit_msg_status = "already_installed"
            else:
                # Back up foreign commit-msg hook
                cm_bak = target_hooks_dir / "commit-msg.emc.bak"
                cm_bak.write_text(cm_content, encoding="utf-8")
                commit_msg_status = "overwritten"

        if commit_msg_status != "already_installed":
            commit_msg_file.write_text(COMMIT_MSG_SCRIPT, encoding="utf-8")
            try:
                commit_msg_file.chmod(0o755)
            except Exception:
                pass

    msg = f"Hooks installed to {target_hooks_dir}"
    return HookInstallResult(
        pre_commit_installed=True,
        pre_commit_status=pre_commit_status,
        commit_msg_installed=install_commit_msg,
        commit_msg_status=commit_msg_status,
        hooks_dir=target_hooks_dir,
        message=msg,
    )


def uninstall_hooks(
    hooks_dir: Path | None = None,
    force: bool = False,
    start_path: Path | None = None,
) -> HookUninstallResult:
    """Uninstall emc hooks, restoring backed-up original hooks if present."""
    target_hooks_dir = hooks_dir or get_git_hooks_dir(start_path=start_path)
    if not target_hooks_dir or not target_hooks_dir.exists():
        return HookUninstallResult(
            pre_commit_removed=False,
            pre_commit_restored=False,
            commit_msg_removed=False,
            commit_msg_restored=False,
            hooks_dir=target_hooks_dir,
            message="No hooks directory found.",
        )

    pre_commit_file = target_hooks_dir / "pre-commit"
    commit_msg_file = target_hooks_dir / "commit-msg"

    # Upfront foreign hook validation before modifying any files
    if not force:
        if pre_commit_file.exists() and "emc" not in pre_commit_file.read_text(encoding="utf-8"):
            raise ForeignHookError(
                "Existing pre-commit hook does not appear to belong to emc. "
                "Use --force to remove anyway."
            )
        if commit_msg_file.exists() and "emc" not in commit_msg_file.read_text(encoding="utf-8"):
            raise ForeignHookError(
                "Existing commit-msg hook does not appear to belong to emc. "
                "Use --force to remove anyway."
            )

    pre_commit_removed = False
    pre_commit_restored = False
    commit_msg_removed = False
    commit_msg_restored = False

    if pre_commit_file.exists():
        pre_commit_file.unlink()
        pre_commit_removed = True

        # Check if backup exists to restore
        bak = target_hooks_dir / "pre-commit.emc.bak"
        if bak.exists():
            bak_content = bak.read_text(encoding="utf-8")
            pre_commit_file.write_text(bak_content, encoding="utf-8")
            try:
                pre_commit_file.chmod(0o755)
            except Exception:
                pass
            bak.unlink()
            pre_commit_restored = True

    if commit_msg_file.exists():
        commit_msg_file.unlink()
        commit_msg_removed = True

        cm_bak = target_hooks_dir / "commit-msg.emc.bak"
        if cm_bak.exists():
            cm_bak_content = cm_bak.read_text(encoding="utf-8")
            commit_msg_file.write_text(cm_bak_content, encoding="utf-8")
            try:
                commit_msg_file.chmod(0o755)
            except Exception:
                pass
            cm_bak.unlink()
            commit_msg_restored = True

    return HookUninstallResult(
        pre_commit_removed=pre_commit_removed,
        pre_commit_restored=pre_commit_restored,
        commit_msg_removed=commit_msg_removed,
        commit_msg_restored=commit_msg_restored,
        hooks_dir=target_hooks_dir,
        message="Hook uninstallation complete.",
    )


def handle_commit_msg_hook(
    msg_path: Path,
    trailer: str | None = None,
    repo_root: Path | None = None,
) -> bool:
    """Process git commit-msg hook to append comprehension trailer."""
    trailer_str = trailer
    if not trailer_str:
        trailer_str = load_staged_trailer(target_dir=repo_root, consume=True)

    if not trailer_str:
        # No trailer found (e.g. no quiz ran or commit had no diff); clean no-op
        return True

    return append_commit_trailer(msg_path, trailer_str)
