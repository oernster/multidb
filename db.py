# db.py

import json
import threading
from pathlib import Path
from typing import Any, List, Dict

class JSONMultiDB:
    """
    Simple N-dimensional JSON-backed "NoSQL" store.

    The on-disk structure looks like:
    {
      "meta": {
        "dimensions": 3
      },
      "data": {
        "x": {
          "y": {
            "z": { ... stored value ... }
          }
        }
      }
    }
    """

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._load()

    # ---------- Static helpers ----------

    @staticmethod
    def _default_structure(dimensions: int) -> Dict[str, Any]:
        return {
            "meta": {"dimensions": dimensions},
            "data": {}
        }

    @classmethod
    def create_new(cls, path: Path, dimensions: int) -> "JSONMultiDB":
        """
        Create (or overwrite) a DB file with the given number of dimensions.
        """
        if dimensions <= 0:
            raise ValueError("dimensions must be a positive integer")

        structure = cls._default_structure(dimensions)
        path.write_text(json.dumps(structure, indent=2))
        return cls(path)

    # ---------- Internal IO helpers ----------

    def _load(self) -> None:
        if not self.path.exists():
            raise FileNotFoundError(f"DB file {self.path} does not exist")

        raw = json.loads(self.path.read_text())
        self.dimensions: int = int(raw["meta"]["dimensions"])
        self.data: Dict[str, Any] = raw.get("data", {})

    def _persist(self) -> None:
        """
        Persist current state to disk. Thread-safe.
        """
        with self._lock:
            obj = {
                "meta": {"dimensions": self.dimensions},
                "data": self.data,
            }
            self.path.write_text(json.dumps(obj, indent=2))

    # ---------- Public API ----------

    def get_dimensions(self) -> int:
        return self.dimensions

    def set_value(self, coords: List[str], value: Any) -> None:
        """
        Set value at an exact N-dimensional coordinate.
        coords length must equal self.dimensions.
        """
        if len(coords) != self.dimensions:
            raise ValueError(
                f"Expected {self.dimensions} coordinates, got {len(coords)}"
            )

        node = self.data
        # Traverse/create all but last level
        for key in coords[:-1]:
            if key not in node or not isinstance(node[key], dict):
                node[key] = {}
            node = node[key]

        # Set leaf value
        node[coords[-1]] = value
        self._persist()

    def get_value(self, coords: List[str]) -> Any:
        """
        Get value at an exact N-dimensional coordinate.
        """
        if len(coords) != self.dimensions:
            raise ValueError(
                f"Expected {self.dimensions} coordinates, got {len(coords)}"
            )

        node = self.data
        for key in coords[:-1]:
            if key not in node or not isinstance(node[key], dict):
                raise KeyError(f"Path not found at key: {key}")
            node = node[key]

        leaf_key = coords[-1]
        if leaf_key not in node:
            raise KeyError(f"Leaf key not found: {leaf_key}")

        return node[leaf_key]

    def delete_value(self, coords: List[str]) -> None:
        """
        Delete value at an exact N-dimensional coordinate.
        """
        if len(coords) != self.dimensions:
            raise ValueError(
                f"Expected {self.dimensions} coordinates, got {len(coords)}"
            )

        node_stack = []
        node = self.data

        # Traverse and keep track of nodes/keys for cleanup
        for key in coords[:-1]:
            if key not in node or not isinstance(node[key], dict):
                raise KeyError(f"Path not found at key: {key}")
            node_stack.append((node, key))
            node = node[key]

        leaf_key = coords[-1]
        if leaf_key not in node:
            raise KeyError(f"Leaf key not found: {leaf_key}")

        # Delete the leaf
        del node[leaf_key]

        # Optional cleanup: remove empty dicts on the way back up
        for parent, k in reversed(node_stack):
            if isinstance(parent.get(k), dict) and not parent[k]:
                del parent[k]
            else:
                break

        self._persist()

    def get_slice(self, prefix: List[str]) -> Any:
        """
        Get an entire sub-tree for a partial coordinate prefix.
        e.g. for dims=3,
          prefix=["x"] -> return all at x, including y/z...
          prefix=["x", "y"] -> return all at x->y
        """
        if len(prefix) > self.dimensions:
            raise ValueError("Prefix longer than number of dimensions")

        node = self.data
        for key in prefix:
            if key not in node or not isinstance(node[key], dict):
                raise KeyError(f"Path not found at key: {key}")
            node = node[key]

        # Return a deep-ish copy (JSON-safe)
        return json.loads(json.dumps(node))
