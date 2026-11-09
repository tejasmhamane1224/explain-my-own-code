"""Unified diff parser extracting structured files, hunks, and lines."""

from __future__ import annotations

import re

from emc.ingest.models import DiffHunk, DiffLine, FileDiff

HUNK_HEADER_RE = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@(.*)$")
DIFF_GIT_RE = re.compile(r"^diff --git\s+(?:a/)?(.*?)\s+(?:b/)?(.*)$")


def _clean_path(path: str) -> str:
    """Normalize git diff paths removing leading a/ or b/ prefixes."""
    path = path.strip()
    if path == "/dev/null":
        return path
    if path.startswith("a/") or path.startswith("b/"):
        return path[2:]
    return path


def parse_unified_diff(diff_text: str) -> list[FileDiff]:
    """Parse standard unified diff text into a list of structured FileDiff objects."""
    if not diff_text or not diff_text.strip():
        return []

    lines = diff_text.splitlines()
    files: list[FileDiff] = []

    current_file: FileDiff | None = None
    current_hunk: DiffHunk | None = None
    header_lines: list[str] = []

    current_old_line = 0
    current_new_line = 0

    def finalize_hunk() -> None:
        nonlocal current_hunk
        if current_hunk is not None and current_file is not None:
            current_file.hunks.append(current_hunk)
            current_hunk = None

    def finalize_file() -> None:
        nonlocal current_file
        finalize_hunk()
        if current_file is not None:
            current_file.raw_header = "\n".join(header_lines)
            files.append(current_file)
            current_file = None
            header_lines.clear()

    idx = 0
    n = len(lines)

    while idx < n:
        line = lines[idx]

        # 1. Start of a new file diff
        if line.startswith("diff --git "):
            finalize_file()
            m = DIFF_GIT_RE.match(line)
            old_p = _clean_path(m.group(1)) if m else None
            new_p = _clean_path(m.group(2)) if m else None
            current_file = FileDiff(old_path=old_p, new_path=new_p)
            header_lines.append(line)
            idx += 1
            continue

        # 2. File metadata header lines
        if current_hunk is None and (
            line.startswith("old mode ")
            or line.startswith("new mode ")
            or line.startswith("deleted file mode ")
            or line.startswith("new file mode ")
            or line.startswith("copy from ")
            or line.startswith("copy to ")
            or line.startswith("rename from ")
            or line.startswith("rename to ")
            or line.startswith("similarity index ")
            or line.startswith("dissimilarity index ")
            or line.startswith("index ")
            or line.startswith("Binary files ")
        ):
            if current_file is None:
                current_file = FileDiff()
            header_lines.append(line)

            if "deleted file mode" in line:
                current_file.is_deleted = True
            elif "new file mode" in line:
                current_file.is_new = True
            elif "rename from " in line:
                current_file.is_rename = True
                current_file.old_path = line[len("rename from ") :].strip()
            elif "rename to " in line:
                current_file.is_rename = True
                current_file.new_path = line[len("rename to ") :].strip()
            elif "Binary files " in line or "GIT binary patch" in line:
                current_file.is_binary = True

            idx += 1
            continue

        # 3. Traditional --- and +++ lines
        if line.startswith("--- "):
            if current_file is None:
                current_file = FileDiff()
            header_lines.append(line)
            path_str = line[4:].strip()
            if path_str == "/dev/null":
                current_file.is_new = True
                current_file.old_path = None
            else:
                current_file.old_path = _clean_path(path_str)
            idx += 1
            continue

        if line.startswith("+++ "):
            if current_file is None:
                current_file = FileDiff()
            header_lines.append(line)
            path_str = line[4:].strip()
            if path_str == "/dev/null":
                current_file.is_deleted = True
                current_file.new_path = None
            else:
                current_file.new_path = _clean_path(path_str)
            idx += 1
            continue

        # 4. Hunk header: @@ -old,count +new,count @@ section
        hunk_match = HUNK_HEADER_RE.match(line)
        if hunk_match:
            finalize_hunk()
            if current_file is None:
                current_file = FileDiff()

            old_start = int(hunk_match.group(1))
            old_lines = (
                int(hunk_match.group(2))
                if hunk_match.group(2) is not None
                else (0 if old_start == 0 else 1)
            )
            new_start = int(hunk_match.group(3))
            new_lines = (
                int(hunk_match.group(4))
                if hunk_match.group(4) is not None
                else (0 if new_start == 0 else 1)
            )
            section = hunk_match.group(5).strip()

            current_hunk = DiffHunk(
                header=line,
                old_start=old_start,
                old_lines=old_lines,
                new_start=new_start,
                new_lines=new_lines,
                section_header=section,
            )
            current_old_line = old_start
            current_new_line = new_start
            idx += 1
            continue

        # 5. Lines inside a hunk
        if current_hunk is not None:
            if line.startswith("+"):
                diff_line = DiffLine(
                    line_type="+",
                    content=line[1:],
                    raw=line,
                    old_line_number=None,
                    new_line_number=current_new_line,
                )
                current_new_line += 1
                current_hunk.lines.append(diff_line)
            elif line.startswith("-"):
                diff_line = DiffLine(
                    line_type="-",
                    content=line[1:],
                    raw=line,
                    old_line_number=current_old_line,
                    new_line_number=None,
                )
                current_old_line += 1
                current_hunk.lines.append(diff_line)
            elif line.startswith(" "):
                diff_line = DiffLine(
                    line_type=" ",
                    content=line[1:],
                    raw=line,
                    old_line_number=current_old_line,
                    new_line_number=current_new_line,
                )
                current_old_line += 1
                current_new_line += 1
                current_hunk.lines.append(diff_line)
            elif line == "":
                # Git diff context lines can sometimes lose trailing space
                diff_line = DiffLine(
                    line_type=" ",
                    content="",
                    raw=" ",
                    old_line_number=current_old_line,
                    new_line_number=current_new_line,
                )
                current_old_line += 1
                current_new_line += 1
                current_hunk.lines.append(diff_line)
            elif line.startswith("\\"):
                # "\ No newline at end of file"
                diff_line = DiffLine(
                    line_type="\\",
                    content=line[1:].strip(),
                    raw=line,
                    old_line_number=None,
                    new_line_number=None,
                )
                current_hunk.lines.append(diff_line)
            else:
                # Unexpected line outside or between hunks
                header_lines.append(line)
            idx += 1
            continue

        # Outside of hunk (or trailing diff notes)
        header_lines.append(line)
        idx += 1

    finalize_file()
    return files
