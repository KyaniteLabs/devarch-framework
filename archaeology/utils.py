"""Shared utility functions for dev-archaeology modules."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any


_logger = logging.getLogger(__name__)


def _load_json(path: Path | str, verbose: bool = False) -> Any | None:
    """Load and parse a JSON file.

    Args:
        path: Path to the JSON file (can be Path or str).
        verbose: If True, print loading status (not used here, kept for API compatibility).

    Returns:
        Parsed JSON data, or None if the file doesn't exist or parsing fails.
    """
    p = Path(path) if isinstance(path, str) else path
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        _logger.warning("JSON parse error in %s: %s", p, e)
        return None
    except OSError as e:
        _logger.warning("I/O error reading %s: %s", p, e)
        return None


def atomic_write(path: Path | str, content: str, encoding: str = "utf-8") -> None:
    """Write content to a file atomically using temp file + rename."""
    p = Path(path) if isinstance(path, str) else path
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    try:
        tmp.write_text(content, encoding=encoding)
        os.replace(tmp, p)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _parse_date(date_str: str) -> datetime | None:
    """Parse a date string into a datetime object.

    Supports multiple date formats from git and other sources.
    Returns None for unparseable dates.

    Args:
        date_str: Date string to parse.

    Returns:
        datetime object if parsing succeeds, None otherwise.
    """
    if not date_str:
        return None
    date_str = str(date_str).strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(date_str[:19], fmt)
        except ValueError:
            continue
    return None


def _script_dir() -> Path:
    """Return the directory containing the calling script.

    Uses Path(__file__).resolve().parent to get the directory.
    Should be called from the module where __file__ is defined.

    Returns:
        Path object pointing to the script's directory.
    """
    return Path(__file__).resolve().parent
