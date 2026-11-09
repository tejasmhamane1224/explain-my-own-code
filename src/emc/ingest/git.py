"""Git diff retrieval and orchestrator for staged, commit-range, and stdin diffs."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from emc.ingest.caps import (
    DEFAULT_MAX_DIFF_BYTES,
    DEFAULT_MAX_FILE_BYTES,
    DEFAULT_MAX_TOTAL_HUNKS,
    apply_caps,
)
from emc.ingest.ignore import filter_ignored_files
from emc.ingest.models import IngestResult
from emc.ingest.parser import parse_unified_diff


class GitError(Exception):
    """Base exception for git execution errors."""


class GitExecutionError(GitError):
    """Raised when a git command returns a non-zero exit code."""


def _run_git_command(args: list[str], cwd: Path | None = None) -> str:
    """Execute git CLI command safely and return stdout."""
    target_dir = cwd or Path.cwd()
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=target_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            shell=False,
        )
        return proc.stdout
    except subprocess.CalledProcessError as exc:
        err_msg = exc.stderr.strip() or str(exc)
        raise GitExecutionError(f"Git command failed: git {' '.join(args)}: {err_msg}") from exc
    except FileNotFoundError as exc:
        raise GitError("git executable not found on system PATH.") from exc


def get_staged_diff(cwd: Path | None = None) -> str:
    """Retrieve staged git diff (git diff --cached)."""
    return _run_git_command(["diff", "--cached", "--no-color", "-U3"], cwd=cwd)


def get_unstaged_diff(cwd: Path | None = None) -> str:
    """Retrieve unstaged working tree diff (git diff)."""
    return _run_git_command(["diff", "--no-color", "-U3"], cwd=cwd)


def get_commit_diff(revision: str, cwd: Path | None = None) -> str:
    """Retrieve diff for a commit revision or range (e.g. HEAD~1, HEAD~2..HEAD, or commit hash)."""
    rev = revision.strip()
    if ".." in rev:
        args = ["diff", "--no-color", "-U3", rev]
    else:
        # Single revision: git show handles both regular commits and root/initial commits cleanly
        args = ["show", "--no-color", "-U3", "--pretty=", rev]
    return _run_git_command(args, cwd=cwd)


def ingest_diff(
    staged: bool = False,
    commit: str | None = None,
    use_stdin: bool = False,
    stdin_content: str | None = None,
    cwd: Path | None = None,
    max_diff_bytes: int = DEFAULT_MAX_DIFF_BYTES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_total_hunks: int = DEFAULT_MAX_TOTAL_HUNKS,
    ignore_file: Path | None = None,
) -> IngestResult:
    """Ingest diff from staged changes, commit range, or stdin.

    Applies .emcignore path filtering and file/diff size caps.
    """
    raw_diff = ""
    source = "staged"

    if stdin_content is not None:
        raw_diff = stdin_content
        source = "stdin"
    elif use_stdin:
        try:
            if hasattr(sys.stdin, "buffer"):
                raw_diff = sys.stdin.buffer.read().decode("utf-8", errors="replace")
            else:
                raw_diff = sys.stdin.read()
        except Exception:
            raw_diff = ""
        source = "stdin"
    elif commit:
        raw_diff = get_commit_diff(commit, cwd=cwd)
        source = f"commit:{commit}"
    elif staged:
        raw_diff = get_staged_diff(cwd=cwd)
        source = "staged"
    else:
        # Default to staged diff; if empty, inspect unstaged diff
        raw_diff = get_staged_diff(cwd=cwd)
        source = "staged"
        if not raw_diff.strip():
            unstaged = get_unstaged_diff(cwd=cwd)
            if unstaged.strip():
                raw_diff = unstaged
                source = "unstaged"

    parsed_files = parse_unified_diff(raw_diff)
    kept_files, ignored_files = filter_ignored_files(parsed_files, ignore_file=ignore_file, cwd=cwd)
    capped_files, is_truncated, truncation_reason = apply_caps(
        kept_files,
        max_file_bytes=max_file_bytes,
        max_diff_bytes=max_diff_bytes,
        max_total_hunks=max_total_hunks,
    )

    return IngestResult(
        files=capped_files,
        raw_diff=raw_diff,
        source=source,
        ignored_files=ignored_files,
        truncated=is_truncated,
        truncation_reason=truncation_reason,
    )
