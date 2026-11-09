"""Diff ingestion, parsing, filtering, and untrusted encapsulation."""

from emc.ingest.caps import apply_caps
from emc.ingest.git import (
    GitError,
    GitExecutionError,
    get_commit_diff,
    get_staged_diff,
    get_unstaged_diff,
    ingest_diff,
)
from emc.ingest.ignore import filter_ignored_files, load_ignore_spec
from emc.ingest.models import DiffHunk, DiffLine, DiffLineType, FileDiff, IngestResult
from emc.ingest.parser import parse_unified_diff
from emc.ingest.untrusted import (
    encapsulate_diff,
    sanitize_delimiters,
    scan_for_injection_markers,
)

__all__ = [
    "DiffHunk",
    "DiffLine",
    "DiffLineType",
    "FileDiff",
    "GitError",
    "GitExecutionError",
    "IngestResult",
    "apply_caps",
    "encapsulate_diff",
    "filter_ignored_files",
    "get_commit_diff",
    "get_staged_diff",
    "get_unstaged_diff",
    "ingest_diff",
    "load_ignore_spec",
    "parse_unified_diff",
    "sanitize_delimiters",
    "scan_for_injection_markers",
]
