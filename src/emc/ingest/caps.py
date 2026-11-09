"""Diff and file size capping to prevent context overflow or excessive latency."""

from __future__ import annotations

from emc.ingest.models import DiffHunk, FileDiff

DEFAULT_MAX_FILE_BYTES = 200_000
DEFAULT_MAX_DIFF_BYTES = 1_000_000
DEFAULT_MAX_TOTAL_HUNKS = 100


def apply_caps(
    files: list[FileDiff],
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_diff_bytes: int = DEFAULT_MAX_DIFF_BYTES,
    max_total_hunks: int = DEFAULT_MAX_TOTAL_HUNKS,
) -> tuple[list[FileDiff], bool, str | None]:
    """Apply size and hunk count caps to parsed file diffs.

    Returns:
        (capped_files, is_truncated, reason_if_truncated)
    """
    capped_files: list[FileDiff] = []
    total_bytes = 0
    total_hunks = 0
    is_truncated = False
    reasons: list[str] = []

    for file_diff in files:
        if file_diff.is_binary:
            continue

        file_bytes = sum(len(h.content.encode("utf-8")) for h in file_diff.hunks)

        # Check single file cap
        if file_bytes > max_file_bytes:
            is_truncated = True
            reasons.append(
                f"File '{file_diff.path}' ({file_bytes:,} bytes) exceeded single-file cap of "
                f"{max_file_bytes:,} bytes and was omitted."
            )
            continue

        # Check accumulated diff bytes
        if total_bytes + file_bytes > max_diff_bytes:
            is_truncated = True
            reasons.append(
                f"Diff byte cap reached ({max_diff_bytes:,} bytes). Remaining files were truncated."
            )
            break

        # Check hunk cap per file
        accepted_hunks: list[DiffHunk] = []
        for hunk in file_diff.hunks:
            if total_hunks >= max_total_hunks:
                is_truncated = True
                reasons.append(
                    f"Total hunk limit reached ({max_total_hunks} hunks). "
                    f"Remaining hunks were truncated."
                )
                break
            accepted_hunks.append(hunk)
            total_hunks += 1

        if accepted_hunks:
            capped_file = file_diff.model_copy(update={"hunks": accepted_hunks})
            capped_files.append(capped_file)
            total_bytes += file_bytes

        if is_truncated and total_hunks >= max_total_hunks:
            break

    reason_str = " | ".join(reasons) if reasons else None
    return capped_files, is_truncated, reason_str
