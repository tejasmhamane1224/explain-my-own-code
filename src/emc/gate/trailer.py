"""Commit trailer formatting and commit message injection for emc."""

from __future__ import annotations

from pathlib import Path

from emc.grade.models import ScoreBreakdown

DEFAULT_TRAILER_PREFIX = "Comprehension:"
TRAILER_FILE_NAME = "last_trailer"


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
) -> bool:
    """Append or update a commit trailer in a git commit message file.

    Follows git commit message formatting conventions:
      - Inserts trailer before any trailing comments (lines starting with '#').
      - If deduplicate=True and trailer prefix already exists, updates it.
      - Never appends to an empty commit message (aborted commit).

    Returns True if trailer was appended or updated, False otherwise.
    """
    if not commit_msg_path.is_file():
        return False

    content = commit_msg_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Separate non-comment content from trailing comments
    first_trailing_comment_idx = len(lines)
    while first_trailing_comment_idx > 0 and lines[
        first_trailing_comment_idx - 1
    ].strip().startswith("#"):
        first_trailing_comment_idx -= 1

    body_lines = lines[:first_trailing_comment_idx]
    comment_lines = lines[first_trailing_comment_idx:]

    # Check if there is any non-whitespace, non-comment text in the body
    has_content = any(line.strip() and not line.strip().startswith("#") for line in body_lines)
    if not has_content:
        # Aborted commit / empty message -> do not add trailer
        return False

    # Extract trailer prefix for deduplication (e.g. "Comprehension:")
    prefix = trailer.split(":")[0] if ":" in trailer else trailer.strip()

    # If deduplication requested, look for existing trailer line in body
    existing_idx = None
    if deduplicate:
        for idx, line in enumerate(body_lines):
            if line.strip().startswith(prefix):
                existing_idx = idx
                break

    if existing_idx is not None:
        # Replace existing trailer line in place
        body_lines[existing_idx] = trailer
    else:
        # Trim trailing blank lines from body
        while body_lines and not body_lines[-1].strip():
            body_lines.pop()

        # Append trailer with a preceding blank line if body exists
        body_lines.append("")
        body_lines.append(trailer)

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
    base = target_dir or Path(".emc")
    return base / TRAILER_FILE_NAME


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
