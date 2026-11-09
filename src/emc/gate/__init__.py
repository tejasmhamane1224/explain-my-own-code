"""Commit gate evaluation and Comprehension trailer formatter."""

from emc.gate.evaluator import GateResult, evaluate_gate, log_skip_event
from emc.gate.trailer import (
    DEFAULT_TRAILER_PREFIX,
    append_commit_trailer,
    format_commit_trailer,
    get_git_comment_char,
    get_staged_trailer_file,
    load_staged_trailer,
    save_staged_trailer,
)

__all__ = [
    "DEFAULT_TRAILER_PREFIX",
    "GateResult",
    "append_commit_trailer",
    "evaluate_gate",
    "format_commit_trailer",
    "get_git_comment_char",
    "get_staged_trailer_file",
    "load_staged_trailer",
    "log_skip_event",
    "save_staged_trailer",
]
