"""Thread-safe append-only storage and reading for .emc/ledger.jsonl."""

from __future__ import annotations

import contextlib
import json
import logging
import sys
import threading
from collections.abc import Iterator
from pathlib import Path

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

from pydantic import ValidationError

from emc.config import find_config_file, load_config
from emc.ledger.models import LedgerEvent

logger = logging.getLogger(__name__)

# In-process lock for concurrent write protection
_LEDGER_LOCK = threading.Lock()
DEFAULT_LEDGER_FILENAME = "ledger.jsonl"


@contextlib.contextmanager
def _interprocess_lock(lock_path: Path) -> Iterator[None]:
    """Cross-process file lock using flock on POSIX or msvcrt on Windows."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock_file = lock_path.open("a+b")
    except OSError:
        yield
        return

    try:
        if sys.platform == "win32":
            try:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            except OSError:
                pass
        else:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            except OSError:
                pass
        yield
    finally:
        try:
            if sys.platform == "win32":
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            try:
                lock_file.close()
            except OSError:
                pass


def get_default_ledger_path(base_dir: Path | None = None) -> Path:
    """Resolve the default path to the ledger file (.emc/ledger.jsonl)."""
    if base_dir is not None:
        return (base_dir / ".emc" / DEFAULT_LEDGER_FILENAME).resolve()

    # Check configured path if available
    cfg_file = find_config_file()
    if cfg_file is not None:
        cfg, _ = load_config(cfg_file)
        if cfg.ledger_path:
            p = Path(cfg.ledger_path)
            return p if p.is_absolute() else (cfg_file.parent / p).resolve()

    return (Path.cwd() / ".emc" / DEFAULT_LEDGER_FILENAME).resolve()


def append_event(
    event: LedgerEvent,
    ledger_path: Path | None = None,
) -> None:
    """Append a single event to the ledger in a thread-safe manner."""
    append_events([event], ledger_path=ledger_path)


def append_events(
    events: list[LedgerEvent],
    ledger_path: Path | None = None,
) -> None:
    """Append multiple events to the ledger under lock, creating parents if missing."""
    if not events:
        return

    path = ledger_path or get_default_ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")

    with _LEDGER_LOCK:
        with _interprocess_lock(lock_path):
            with path.open("a", encoding="utf-8") as f:
                for ev in events:
                    f.write(ev.model_dump_json() + "\n")
                f.flush()


def read_events_with_stats(
    ledger_path: Path | None = None,
) -> tuple[list[LedgerEvent], int]:
    """Read all valid events from ledger file, returning (events, corrupt_count).

    Corrupted lines (invalid JSON or invalid schema) are gracefully skipped without
    discarding valid neighboring records.
    """
    path = ledger_path or get_default_ledger_path()
    if not path.is_file():
        return [], 0

    valid_events: list[LedgerEvent] = []
    corrupt_count = 0
    lock_path = path.with_name(path.name + ".lock")

    with _LEDGER_LOCK:
        with _interprocess_lock(lock_path):
            try:
                with path.open("r", encoding="utf-8", errors="replace") as f:
                    for line_num, line in enumerate(f, start=1):
                        raw = line.strip()
                        if not raw:
                            continue
                        try:
                            ev = LedgerEvent.model_validate_json(raw)
                            valid_events.append(ev)
                        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
                            corrupt_count += 1
                            logger.warning(
                                "Skipping corrupted ledger entry at line %d in %s: %s",
                                line_num,
                                path,
                                exc,
                            )
            except OSError as exc:
                logger.error("Failed to read ledger file %s: %s", path, exc)
                return [], 0

    return valid_events, corrupt_count


def read_events(ledger_path: Path | None = None) -> list[LedgerEvent]:
    """Read all valid events from ledger, discarding any corrupt lines gracefully."""
    events, _ = read_events_with_stats(ledger_path=ledger_path)
    return events


def clear_ledger(ledger_path: Path | None = None) -> None:
    """Clear or reset ledger file (primarily for tests)."""
    path = ledger_path or get_default_ledger_path()
    lock_path = path.with_name(path.name + ".lock")
    with _LEDGER_LOCK:
        with _interprocess_lock(lock_path):
            if path.exists():
                path.unlink()
            if lock_path.exists():
                try:
                    lock_path.unlink()
                except OSError:
                    pass
