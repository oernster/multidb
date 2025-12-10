"""Database layer for the multidimensional JSON store."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class JsonFileStorage:
    """Simple JSON file storage abstraction.

    This class has a very small responsibility: reading and writing
    JSON-serialisable dictionaries to a given path.
    """

    path: Path

    def read(self) -> Dict[str, Any]:
        if not self.path.exists():
            raise FileNotFoundError(f"Database file does not exist: {self.path}")
        raw_text = self.path.read_text(encoding="utf-8")
        return json.loads(raw_text)

    def write(self, payload: Dict[str, Any]) -> None:
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class JSONMultiDB:
    """N-dimensional JSON-backed key/value store.

    Public API:

    * :meth:`create_new`  – create a new database file.
    * :meth:`get_dimensions`
    * :meth:`set_value`
    * :meth:`get_value`
    * :meth:`delete_value`
    * :meth:`get_slice`
    """

    def __init__(self, path: Path) -> None:
        self._storage = JsonFileStorage(path=path)
        self._lock = threading.Lock()
        self._dimensions: int = 0
        self._data: Dict[str, Any] = {}
        self._load()

    # --------------------------------------------------------------------- #
    # Construction helpers
    # --------------------------------------------------------------------- #

    @staticmethod
    def _default_structure(dimensions: int) -> Dict[str, Any]:
        return {"meta": {"dimensions": dimensions}, "data": {}}

    @classmethod
    def create_new(cls, path: Path, dimensions: int) -> "JSONMultiDB":
        """Create (or overwrite) a DB file with the given number of dimensions."""
        if dimensions <= 0:
            raise ValueError("dimensions must be a positive integer")

        storage = JsonFileStorage(path=path)
        structure = cls._default_structure(dimensions)
        storage.write(structure)
        return cls(path=path)

    # --------------------------------------------------------------------- #
    # Persistence
    # --------------------------------------------------------------------- #

    def _load(self) -> None:
        raw = self._storage.read()
        try:
            self._dimensions = int(raw["meta"]["dimensions"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Invalid DB file: missing or bad dimensions") from exc
        self._data = dict(raw.get("data", {}))

    def _persist(self) -> None:
        payload = self._default_structure(self._dimensions)
        payload["data"] = self._data
        self._storage.write(payload)

    # --------------------------------------------------------------------- #
    # Introspection
    # --------------------------------------------------------------------- #

    def get_dimensions(self) -> int:
        return self._dimensions

    # --------------------------------------------------------------------- #
    # Core operations
    # --------------------------------------------------------------------- #

    def set_value(self, coords: List[str], value: Any) -> None:
        """Create or replace a value at the given coordinate."""
        if len(coords) != self._dimensions:
            raise ValueError(
                f"Expected {self._dimensions} coordinates, got {len(coords)}"
            )

        with self._lock:
            node: Dict[str, Any] = self._data
            for key in coords[:-1]:
                if key not in node or not isinstance(node[key], dict):
                    node[key] = {}
                node = node[key]  # type: ignore[assignment]

            node[coords[-1]] = value
            self._persist()

    def get_value(self, coords: List[str]) -> Any:
        """Retrieve a value at the given coordinate."""
        if len(coords) != self._dimensions:
            raise ValueError(
                f"Expected {self._dimensions} coordinates, got {len(coords)}"
            )

        node: Dict[str, Any] = self._data
        for key in coords[:-1]:
            if key not in node or not isinstance(node[key], dict):
                raise KeyError(f"Path not found at key: {key}")
            node = node[key]  # type: ignore[assignment]

        leaf_key = coords[-1]
        if leaf_key not in node:
            raise KeyError(f"Leaf key not found: {leaf_key}")

        return node[leaf_key]

    def delete_value(self, coords: List[str]) -> None:
        """Delete a value at the given coordinate.

        Any now-empty intermediate dictionaries are removed as well.
        """
        if len(coords) != self._dimensions:
            raise ValueError(
                f"Expected {self._dimensions} coordinates, got {len(coords)}"
            )

        with self._lock:
            node: Dict[str, Any] = self._data
            node_stack: List[Dict[str, Any]] = [node]

            for key in coords[:-1]:
                if key not in node or not isinstance(node[key], dict):
                    raise KeyError(f"Path not found at key: {key}")
                node = node[key]  # type: ignore[assignment]
                node_stack.append(node)

            leaf_key = coords[-1]
            if leaf_key not in node:
                raise KeyError(f"Leaf key not found: {leaf_key}")
            del node[leaf_key]

            # Clean up empty dictionaries from the leaf upwards.
            for index in range(len(coords) - 2, -1, -1):
                parent = node_stack[index]
                key = coords[index]
                child = parent.get(key)
                if isinstance(child, dict) and not child:
                    del parent[key]
                else:
                    break

            self._persist()

    def get_slice(self, prefix: List[str]) -> Any:
        """Return a sub-tree for a given prefix of coordinates.

        The empty prefix returns the entire data tree.
        """
        if len(prefix) > self._dimensions:
            raise ValueError("Prefix longer than number of dimensions")

        node: Any = self._data
        for key in prefix:
            if not isinstance(node, dict) or key not in node:
                raise KeyError(f"Path not found at key: {key}")
            node = node[key]

        # Defensive copy to prevent accidental mutation of internal state.
        return json.loads(json.dumps(node))
