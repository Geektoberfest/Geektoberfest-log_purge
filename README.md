# log-purge

[![CI](https://github.com/YOUR_USERNAME/log-purge/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/log-purge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)

A small, dependency-free Python CLI that deletes files older than N days.
Built to keep a `/logs` directory from filling up the disk.

## Install

```bash
pip install -e .          # gives you the `log-purge` command
# or run without installing:
PYTHONPATH=src python -m log_purge --help
```

Requires Python 3.9+. No third-party dependencies.

## Usage

```bash
# Preview only (deletes nothing)
log-purge /logs --days 30 --dry-run

# Interactive: shows count + total size, asks [y/N]
log-purge /logs --days 30

# Cron / scripts: skip the prompt
log-purge /logs --days 30 --yes

# Only *.log files, top-level directory only
log-purge /logs -d 14 -p "*.log" --no-recursive --yes

# Only delete files older than 30 days that are at least 10 MB
log-purge /logs -d 30 --min-size 10MB --yes
```

| Option | Meaning |
|---|---|
| `-d, --days N` | Delete files older than N days (required) |
| `-p, --pattern GLOB` | Match file names, default `*` |
| `--no-recursive` | Don't descend into subdirectories |
| `--min-size SIZE` | Delete only files at least this large (e.g. 10MB) |
| `--max-size SIZE` | Delete only files at most this large (e.g. 100MB) |
| `-n, --dry-run` | List what would be deleted, delete nothing |
| `-y, --yes` | Skip the confirmation prompt |
| `-v, --verbose` | Print every file handled |
| `-q, --quiet` | Print nothing except errors |

Cron example (daily at 02:00):

```
0 2 * * * log-purge /logs --days 30 --pattern "*.log" --yes
```

## Safety

- Age is based on **modification time**.
- Only regular files are deleted; directories are never removed.
- Symlinks are skipped, so nothing outside the target can be touched.
- Refuses to run on a filesystem root.
- Without `--yes`, a non-interactive run (no terminal) is refused rather than deleting silently.
- A failure on one file is reported and the run continues.

## Exit codes

`0` success / nothing to do / declined · `1` some deletions failed · `2` usage error · `130` interrupted

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Security issues: [SECURITY.md](SECURITY.md).

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Project layout

```
src/log_purge/cli.py      argument parsing, prompt, output, exit codes
src/log_purge/purger.py   find_old_files() and delete_files() (no I/O formatting)
src/log_purge/utils.py    size formatting and age helpers
tests/                    pytest suites for core logic and CLI

```

## License

[MIT](LICENSE)
