"""Commit trailer formatting and commit message injection for emc."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from emc.config import find_config_file
from emc.grade.models import ScoreBreakdown

DEFAULT_TRAILER_PREFIX = "Comprehension:"
TRAILER_FILE_NAME = "last_trailer"


def get_git_comment_char(start_path: Path | None = None) -> str:
    """Detect git commentChar from git config, defaulting to '#'."""
    cwd = (start_path or Path.cwd()).resolve()
    try:
        proc = subprocess.run(
            ["git", "config", "--get", "core.commentChar"],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
        val = proc.stdout.strip()
        if val and val != "auto":
            return val
    except Exception:
        pass
    return "#"


def format_commit_trailer(
    breakdown: ScoreBreakdown,
    style: str = "fraction",
    prefix: str = DEFAULT_TRAILER_PREFIX,
) -> str:
    """Format commit trailer string from quiz score breakdown.

    Styles:
      - 'fraction': "Comprehension: 4/5"
      - 'percentage': "Comprehension: 80%"
      - 'detailed': "Comprehension: 100% (anchor.signer_check: 2/2)"
    """
    if breakdown.total_questions == 0:
        return f"{prefix} N/A"

    if style == "percentage":
        return f"{prefix} {int(round(breakdown.percentage))}%"

    if style == "detailed":
        # Group question results by concept_id
        concepts: dict[str, list[int]] = {}  # concept_id -> [correct, total]
        for r in breakdown.results:
            cid = r.concept_id
            if cid not in concepts:
                concepts[cid] = [0, 0]
            concepts[cid][1] += 1
            if r.is_correct:
                concepts[cid][0] += 1

        if concepts:
            parts = [f"{cid}: {corr}/{tot}" for cid, (corr, tot) in sorted(concepts.items())]
            concept_str = ", ".join(parts)
            return f"{prefix} {int(round(breakdown.percentage))}% ({concept_str})"
        return f"{prefix} {int(round(breakdown.percentage))}%"

    # Default 'fraction' style
    return f"{prefix} {breakdown.correct_count}/{breakdown.total_questions}"


def append_commit_trailer(
    commit_msg_path: Path,
    trailer: str,
    deduplicate: bool = True,
    comment_char: str | None = None,
) -> bool:
    """Append or update a commit trailer in a git commit message file.

    Follows git commit message formatting conventions:
      - Inserts trailer before any trailing comments (using git core.commentChar).
      - If deduplicate=True and trailer prefix already exists, updates it and cleans duplicates.
      - Keeps git trailers contiguous if a previous trailer line already exists.
      - Never appends to an empty commit message (aborted commit).

    Returns True if trailer was appended or updated, False otherwise.
    """
    if not commit_msg_path.is_file():
        return False

    c_char = comment_char or get_git_comment_char(commit_msg_path.parent)

    content = commit_msg_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Separate non-comment content from trailing comments
    first_trailing_comment_idx = len(lines)
    while first_trailing_comment_idx > 0 and lines[
        first_trailing_comment_idx - 1
    ].strip().startswith(c_char):
        first_trailing_comment_idx -= 1

    body_lines = lines[:first_trailing_comment_idx]
    comment_lines = lines[first_trailing_comment_idx:]

    # Check if there is any non-whitespace, non-comment text in the body
    has_content = any(line.strip() and not line.strip().startswith(c_char) for line in body_lines)
    if not has_content:
        # Aborted commit / empty message -> do not add trailer
        return False

    # Extract trailer prefix for deduplication, ensuring trailing separator
    # e.g. "Comprehension: 4/5" -> prefix "Comprehension:"
    prefix = trailer.split(":", 1)[0].strip() + ":" if ":" in trailer else trailer.strip()

    # Trim trailing blank lines from body upfront
    while body_lines and not body_lines[-1].strip():
        body_lines.pop()

    # If deduplication requested, look for existing trailer line in body
    existing_idx = None
    if deduplicate:
        cleaned_body: list[str] = []
        for line in body_lines:
            if line.strip().startswith(prefix):
                if existing_idx is None:
                    existing_idx = len(cleaned_body)
                    cleaned_body.append(trailer)
                # Drop subsequent duplicate trailer lines
            else:
                cleaned_body.append(line)
        body_lines = cleaned_body

    if existing_idx is None:
        # Check if the last non-empty line is already a git trailer (e.g. Signed-off-by: ...)
        is_last_line_trailer = bool(
            body_lines and re.match(r"^[A-Za-z0-9_-]+:\s+.*$", body_lines[-1].strip())
        )
        if body_lines and not is_last_line_trailer:
            body_lines.append("")
        body_lines.append(trailer)

    # Trim trailing blank lines again to guarantee no empty line accumulation
    while body_lines and not body_lines[-1].strip():
        body_lines.pop()

    # Reconstruct message
    all_lines = list(body_lines)
    if comment_lines:
        all_lines.append("")
        all_lines.extend(comment_lines)

    new_content = "\n".join(all_lines) + "\n"
    commit_msg_path.write_text(new_content, encoding="utf-8")
    return True


def get_staged_trailer_file(target_dir: Path | None = None) -> Path:
    """Get path to the temporary staged trailer file."""
    if target_dir is not None:
        return target_dir / TRAILER_FILE_NAME

    # Check config file directory or git root
    cfg_file = find_config_file()
    if cfg_file is not None:
        return (cfg_file.parent / ".emc" / TRAILER_FILE_NAME).resolve()

    return (Path.cwd() / ".emc" / TRAILER_FILE_NAME).resolve()


def save_staged_trailer(trailer: str, target_dir: Path | None = None) -> Path:
    """Save trailer to temporary staging file in .emc directory."""
    path = get_staged_trailer_file(target_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(trailer, encoding="utf-8")
    return path


def load_staged_trailer(target_dir: Path | None = None, consume: bool = True) -> str | None:
    """Read staged trailer, optionally removing the staging file (consume=True)."""
    path = get_staged_trailer_file(target_dir)
    if not path.is_file():
        return None
    try:
        content = path.read_text(encoding="utf-8").strip()
        if consume:
            try:
                path.unlink()
            except OSError:
                pass
        return content if content else None
    except Exception:
        return None
