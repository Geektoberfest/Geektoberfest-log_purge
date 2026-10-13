"""Small helpers shared by the core logic and the CLI."""

from __future__ import annotations

import re

SECONDS_PER_DAY = 86_400

SIZE_UNITS: dict[str, int] = {
    "b": 1,
    "k": 1024,
    "kb": 1024,
    "m": 1024**2,
    "mb": 1024**2,
    "g": 1024**3,
    "gb": 1024**3,
    "t": 1024**4,
    "tb": 1024**4,
}


def parse_size(size_str: str) -> int:
    """Parse a human-readable size string into bytes.

    Accepts units like B, KB, MB, GB, TB (case-insensitive) or bare integers.
    Raises ValueError on invalid formats or negative values.
    """
    if not isinstance(size_str, str):
        raise ValueError(f"Size must be a string, got {type(size_str).__name__}")
    s = size_str.strip()
    if not s:
        raise ValueError("Empty size string")

    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]*)", s)
    if not match:
        raise ValueError(f"Invalid size string: '{size_str}'")

    number_part, unit_part = match.groups()
    try:
        val = float(number_part)
    except ValueError:
        raise ValueError(f"Invalid size number: '{number_part}'") from None

    unit = unit_part.lower()
    if unit == "":
        multiplier = 1
    elif unit in SIZE_UNITS:
        multiplier = SIZE_UNITS[unit]
    else:
        raise ValueError(f"Unknown size unit: '{unit_part}'")

    bytes_val = int(val * multiplier)
    if bytes_val < 0:
        raise ValueError("Size cannot be negative")
    return bytes_val


def format_size(num_bytes: int) -> str:
    """Return a human-readable size, e.g. ``1536`` -> ``'1.5 KB'``."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"  # pragma: no cover


def age_in_days(mtime: float, now: float) -> float:
    """Age of a file in days, given its modification time."""
    return (now - mtime) / SECONDS_PER_DAY
