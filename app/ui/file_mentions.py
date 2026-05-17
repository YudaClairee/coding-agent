"""Pure utilities for `@` file-mention autocomplete and expansion.

No Textual imports — safe to unit test in isolation.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass

MAX_RESULTS = 20
MAX_FILE_BYTES = 200_000

SKIP_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".next",
        ".turbo",
        "target",
    }
)

# Matches `@<non-whitespace>` at start of string or after whitespace.
_MENTION_RE = re.compile(r"(?:^|(?<=\s))@(\S+)")


@dataclass(frozen=True)
class FileEntry:
    """A candidate file that can be mentioned via `@`."""

    relpath: str  # forward-slash, relative to base_dir
    basename: str


def _normalize(rel: str) -> str:
    return rel.replace(os.sep, "/").lstrip("./")


def _git_ls_files(base_dir: str) -> list[str] | None:
    """Return a list of tracked + untracked (not ignored) paths, or None on failure."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=base_dir,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None
    if result.returncode != 0:
        return None
    return [line for line in result.stdout.splitlines() if line]


def _walk_files(base_dir: str) -> list[str]:
    """Fallback discovery when git is unavailable."""
    out: list[str] = []
    for root, dirs, files in os.walk(base_dir):
        # Prune hidden dot-dirs and known heavy dirs in place.
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, base_dir)
            out.append(rel)
    return out


def list_repo_files(base_dir: str) -> list[FileEntry]:
    """Discover candidate files under `base_dir`.

    Preference order:
      1. `git ls-files --cached --others --exclude-standard`
      2. `os.walk` fallback with SKIP_DIRS pruning.

    Entries whose relpath contains a space are dropped (the `@<token>` regex
    cannot encode them).
    """
    raw = _git_ls_files(base_dir)
    if raw is None:
        raw = _walk_files(base_dir)

    seen: set[str] = set()
    entries: list[FileEntry] = []
    for rel in raw:
        rel = _normalize(rel)
        if not rel or " " in rel:
            continue
        if rel in seen:
            continue
        seen.add(rel)
        entries.append(FileEntry(relpath=rel, basename=os.path.basename(rel)))

    entries.sort(key=lambda e: e.relpath)
    return entries


def score_match(query: str, entry: FileEntry) -> int | None:
    """Return a score for how well `entry` matches `query`, or None if no match.

    Higher is better. Empty query returns 0 (unfiltered list, stable sort).
    """
    if not query:
        return 0

    q = query.lower()
    base = entry.basename.lower()
    rel = entry.relpath.lower()

    if base.startswith(q):
        return 1000 - len(entry.basename)
    if q in base:
        return 800 - len(entry.basename)
    if q in rel:
        return 600 - len(entry.relpath)

    # Subsequence match on relpath.
    gap = 0
    last = -1
    i = 0
    for ch in q:
        idx = rel.find(ch, last + 1)
        if idx == -1:
            return None
        if last != -1:
            gap += idx - last - 1
        last = idx
        i += 1
    if i != len(q):
        return None
    return 400 - gap


def filter_files(
    query: str, entries: list[FileEntry], limit: int = MAX_RESULTS
) -> list[FileEntry]:
    """Score, sort, and truncate entries for the given query."""
    scored: list[tuple[int, FileEntry]] = []
    for entry in entries:
        score = score_match(query, entry)
        if score is None:
            continue
        scored.append((score, entry))
    # Stable sort: higher score first, then alpha by relpath.
    scored.sort(key=lambda pair: (-pair[0], pair[1].relpath))
    return [entry for _, entry in scored[:limit]]


def find_mention_token(text: str, cursor: int) -> tuple[int, int, str] | None:
    """Find the `@<token>` the cursor is inside, if any.

    Walks backward from `cursor - 1` over non-whitespace characters. If an `@`
    is found that sits at the start of the string or after whitespace, returns
    `(at_index, cursor, query)` — where `query` is the text between `@` and the
    cursor. Returns None otherwise.

    This guards against `user@host` and `@decorator` mid-word triggers.
    """
    if cursor < 0 or cursor > len(text):
        return None

    i = cursor - 1
    while i >= 0 and not text[i].isspace():
        if text[i] == "@":
            if i == 0 or text[i - 1].isspace():
                return i, cursor, text[i + 1 : cursor]
            return None
        i -= 1
    return None


def _safe_resolve(base_dir: str, rel: str) -> str | None:
    """Return the absolute path iff it stays within `base_dir`, else None."""
    base_abs = os.path.realpath(base_dir)
    candidate = os.path.realpath(os.path.join(base_abs, rel))
    if candidate != base_abs and not candidate.startswith(base_abs + os.sep):
        return None
    return candidate


def _read_file_block(base_dir: str, rel: str) -> str:
    """Return a single `<file ...>` block for `rel`, with error on failure."""
    resolved = _safe_resolve(base_dir, rel)
    if resolved is None:
        return f'<file path="{rel}" error="path outside project"/>\n'
    if not os.path.exists(resolved):
        return f'<file path="{rel}" error="not found"/>\n'
    if not os.path.isfile(resolved):
        return f'<file path="{rel}" error="not a regular file"/>\n'
    try:
        size = os.path.getsize(resolved)
    except OSError:
        return f'<file path="{rel}" error="not found"/>\n'
    if size > MAX_FILE_BYTES:
        return f'<file path="{rel}" error="file exceeds 200KB limit"/>\n'
    try:
        with open(resolved, "rb") as f:
            raw = f.read()
    except OSError:
        return f'<file path="{rel}" error="not found"/>\n'
    try:
        contents = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            contents = raw.decode("utf-8", errors="replace")
        except Exception:
            return f'<file path="{rel}" error="binary or non-utf8"/>\n'
    return f'<file path="{rel}">\n{contents}\n</file>\n'


def expand_mentions(text: str, base_dir: str) -> str:
    """Prepend `<file>` blocks for every `@path` mention in `text`.

    Mentions are discovered via `_MENTION_RE`, deduped in order, and each
    resolved file is read (size-capped, utf-8 with replacement). On any
    failure a terse `<file .../>` error tag is emitted instead. If no
    mentions are found, `text` is returned unchanged.
    """
    matches = _MENTION_RE.findall(text)
    if not matches:
        return text

    # Dedupe preserving order.
    unique_paths = list(dict.fromkeys(matches))

    blocks: list[str] = []
    for rel in unique_paths:
        blocks.append(_read_file_block(base_dir, rel))

    return "".join(blocks) + "\n" + text
