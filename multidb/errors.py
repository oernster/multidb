"""Public error types for MultiDimensionalDB v2."""

from __future__ import annotations


class MultiDBError(Exception):
    """Base class for all MultiDimensionalDB errors."""


class StorageCorruptionError(MultiDBError):
    """Raised when on-disk data is missing or cannot be validated/recovered."""


class LockError(MultiDBError):
    """Raised when the database cannot acquire the required file locks."""


class ReadOnlyError(MultiDBError):
    """Raised when attempting to mutate state in read-only mode."""


class ValidationError(MultiDBError, ValueError):
    """Raised when inputs fail validation (keys, values, schema)."""
