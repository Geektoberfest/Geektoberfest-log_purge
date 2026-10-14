"""Command-line interface for log-purge.

Exit codes:
    0   success (including "nothing to delete" and user declined)
    1   some files could not be deleted
    2   usage error (bad directory, no --yes in non-interactive mode, ...)
    130 interrupted with Ctrl+C
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from . import __version__
from .purger import PurgeResult, delete_files, find_old_files
from .utils import age_in_days, format_size


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="log-purge",
        description="Delete files older than N days from a directory.",
    )
    p.add_argument("directory", type=Path, help="directory to clean (e.g. /logs)")
    p.add_argument("-d", "--days", type=float, required=True,
                   help="delete files older than this many days")
    p.add_argument("-p", "--pattern", default="*",
                   help="glob matched against file names (default: *)")
    p.add_argument("--no-recursive", action="store_true",
                   help="only look at the top-level directory")
    p.add_argument("-n", "--dry-run", action="store_true",
                   help="list what would be deleted, delete nothing")
    p.add_argument("-y", "--yes", action="store_true",
                   help="skip the confirmation prompt (for cron / scripts)")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="list every file as it is handled")
    p.add_argument("-q", "--quiet", action="store_true",
                   help="print nothing except errors")
    p.add_argument("--log-file", type=Path,
                   help="path to a file where deletions are logged (appends)")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p



def _confirm(count: int, total: int, directory: Path) -> bool:
    answer = input(
        f"Delete {count} file(s) ({format_size(total)}) from {directory}? [y/N] "
    )
    return answer.strip().lower() in {"y", "yes"}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    log_level = logging.WARNING
    if args.verbose:
        log_level = logging.DEBUG
    elif args.quiet:
        log_level = logging.ERROR
    logging.basicConfig(
        level=log_level,
        format="%(levelname)s: %(message)s",
        force=True,
    )
    for h in logging.getLogger().handlers:
        h.setLevel(log_level)

    if args.days < 0:
        print("error: --days must be >= 0", file=sys.stderr)
        return 2
    directory = args.directory.resolve()
    if not directory.is_dir():
        print(f"error: not a directory: {directory}", file=sys.stderr)
        return 2
    if directory == Path(directory.anchor):
        print("error: refusing to purge a filesystem root", file=sys.stderr)
        return 2

    file_handler: logging.FileHandler | None = None
    pkg_logger = logging.getLogger("log_purge")
    if args.log_file:
        try:
            file_handler = logging.FileHandler(args.log_file, mode="a", encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot open log file: {exc.strerror or exc}", file=sys.stderr)
            return 2
        file_formatter = logging.Formatter(
            fmt="%(asctime)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
        file_formatter.converter = time.gmtime
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.INFO)
        file_handler.addFilter(
            lambda record: record.getMessage().startswith(
                ("DELETED ", "FAILED ", "WOULD_DELETE ", "SUMMARY ")
            )
        )
        pkg_logger.addHandler(file_handler)
        pkg_logger.setLevel(logging.INFO)

    try:
        now = time.time()
        candidates = find_old_files(
            directory, args.days, args.pattern,
            recursive=not args.no_recursive, now=now,
        )
        if not candidates:
            if not args.quiet:
                print(f"Nothing to delete: no files older than {args.days:g} day(s).")
            pkg_logger.info("SUMMARY Nothing to delete: no files older than %g day(s).", args.days)
            return 0

        total = sum(c.size for c in candidates)
        if (args.verbose or args.dry_run) and not args.quiet:
            for c in candidates:
                print(f"  {c.path}  ({format_size(c.size)}, "
                      f"{age_in_days(c.mtime, now):.0f} days old)")

        if args.dry_run:
            delete_files(candidates, dry_run=True)
            if not args.quiet:
                print(f"[dry-run] Would delete {len(candidates)} file(s), "
                      f"freeing {format_size(total)}.")
            pkg_logger.info("SUMMARY [dry-run] Would delete %d file(s), freeing %s.",
                            len(candidates), format_size(total))
            return 0

        if not args.yes:
            if not sys.stdin.isatty():
                print("error: not a terminal; pass --yes to confirm deletion",
                      file=sys.stderr)
                return 2
            if not _confirm(len(candidates), total, directory):
                if not args.quiet:
                    print("Aborted. Nothing was deleted.")
                pkg_logger.info("SUMMARY Aborted. Nothing was deleted.")
                return 0

        result: PurgeResult = delete_files(candidates)

        if not args.quiet:
            print(f"Deleted {result.deleted} file(s), freed {format_size(result.freed_bytes)}.")
        if result.failures:
            print(f"{len(result.failures)} file(s) could not be deleted:", file=sys.stderr)
            for path, exc in result.failures:
                print(f"  {path}: {exc.strerror}", file=sys.stderr)
            pkg_logger.info(
                "SUMMARY Deleted %d file(s), freed %s (%d file(s) failed).",
                result.deleted, format_size(result.freed_bytes), len(result.failures),
            )
            return 1
        pkg_logger.info("SUMMARY Deleted %d file(s), freed %s.",
                        result.deleted, format_size(result.freed_bytes))
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    finally:
        if file_handler:
            pkg_logger.removeHandler(file_handler)
            file_handler.close()



if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
