"""Application configuration objects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    """Immutable container for application configuration."""

    db_file_path: Path = Path("multidimensional_db.json")


config = AppConfig()

# Backwards-compatible simple name used by the rest of the application.
DB_FILE_PATH: Path = config.db_file_path
