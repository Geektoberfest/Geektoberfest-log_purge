"""Core logic: find files older than N days and delete them.

This module does no printing and no prompting, so it is easy to test
and to reuse from other Python code.
"""

from __future__ import annotations

import fnmatch
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from .utils import SECONDS_PER_DAY

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Candidate:
    """A file that is old enough to be purged."""

    path: Path
    size: int
    mtime: float


@dataclass
class PurgeResult:
    """Outcome of a deletion run."""

    deleted: int = 0
    freed_bytes: int = 0
    failures: list[tuple[Path, OSError]] = field(default_factory=list)


def find_old_files(
    root: str | os.PathLike,
    days: float,
    pattern: str = "*",
    recursive: bool = True,
    now: float | None = None,
    min_size: int | None = None,
    max_size: int | None = None,
) -> list[Candidate]:
    """Return files under *root* whose mtime is older than *days* days.

    - Only regular files are returned; directories are never candidates.
    - Symlinks are skipped, so nothing outside *root* can be touched.
    - *pattern* is an fnmatch glob applied to the file name (e.g. ``*.log``).
    - *min_size* / *max_size* (bytes) filter files by size.
    """
    if days < 0:
        raise ValueError("days must be >= 0")
    if min_size is not None and min_size < 0:
        raise ValueError("min_size must be >= 0")
    if max_size is not None and max_size < 0:
        raise ValueError("max_size must be >= 0")
    if min_size is not None and max_size is not None and min_size > max_size:
        raise ValueError("min_size cannot be greater than max_size")

    root = Path(root)
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")

    now = time.time() if now is None else now
    cutoff = now - days * SECONDS_PER_DAY
    candidates: list[Candidate] = []

    def _onerror(exc: OSError) -> None:
        log.warning("Cannot read %s: %s", getattr(exc, "filename", "?"), exc.strerror)

    for dirpath, _dirnames, filenames in os.walk(root, onerror=_onerror):
        for name in filenames:
            if not fnmatch.fnmatch(name, pattern):
                continue
            path = Path(dirpath) / name
            try:
                if path.is_symlink():
                    continue
                st = path.stat()
            except OSError as exc:
                log.warning("Cannot stat %s: %s", path, exc.strerror)
                continue
            if st.st_mtime < cutoff:
                if min_size is not None and st.st_size < min_size:
                    continue
                if max_size is not None and st.st_size > max_size:
                    continue
                candidates.append(Candidate(path, st.st_size, st.st_mtime))
        if not recursive:
            break  # only the top-level directory

    candidates.sort(key=lambda c: c.path)
    return candidates


def delete_files(candidates: list[Candidate]) -> PurgeResult:
    """Delete each candidate. A failure on one file never stops the run."""
    result = PurgeResult()
    for c in candidates:
        try:
            c.path.unlink()
        except OSError as exc:
            log.error("Failed to delete %s: %s", c.path, exc.strerror)
            result.failures.append((c.path, exc))
        else:
            result.deleted += 1
            result.freed_bytes += c.size
            log.debug("Deleted %s", c.path)
    return result
