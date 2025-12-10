"""Unit tests for the JSONMultiDB persistence layer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

import pytest

from db import JSONMultiDB


class TestJSONMultiDB:
    """Behavioural tests for the JSONMultiDB class."""

    def test_create_new_creates_file_and_sets_dimensions(self, tmp_path: Path) -> None:
        db_path = tmp_path / "db.json"
        db = JSONMultiDB.create_new(db_path, dimensions=3)

        assert db.get_dimensions() == 3
        assert db_path.exists()

        on_disk = json.loads(db_path.read_text(encoding="utf-8"))
        assert on_disk["meta"]["dimensions"] == 3
        assert on_disk["data"] == {}

    def test_create_new_with_invalid_dimensions_raises(self, tmp_path: Path) -> None:
        db_path = tmp_path / "db.json"
        with pytest.raises(ValueError):
            JSONMultiDB.create_new(db_path, dimensions=0)

    def test_init_requires_existing_file(self, tmp_path: Path) -> None:
        db_path = tmp_path / "does_not_exist.json"
        with pytest.raises(FileNotFoundError):
            JSONMultiDB(db_path)

    def test_set_and_get_value_round_trip(self, tmp_path: Path) -> None:
        db_path = tmp_path / "db.json"
        db = JSONMultiDB.create_new(db_path, dimensions=2)

        coords = ["user1", "2025-01"]
        value = {"orders": 5}

        db.set_value(coords, value)
        assert db.get_value(coords) == value

    def test_set_value_with_wrong_number_of_coords_raises(
        self,
        tmp_path: Path,
    ) -> None:
        db_path = tmp_path / "db.json"
        db = JSONMultiDB.create_new(db_path, dimensions=2)

        with pytest.raises(ValueError):
            db.set_value(["only_one"], value=1)

        with pytest.raises(ValueError):
            db.set_value(["too", "many", "coords"], value=1)

    def test_get_value_missing_path_raises_key_error(self, tmp_path: Path) -> None:
        db_path = tmp_path / "db.json"
        db = JSONMultiDB.create_new(db_path, dimensions=2)
        db.set_value(["x", "y"], 42)

        with pytest.raises(KeyError):
            db.get_value(["missing", "y"])

        with pytest.raises(KeyError):
            db.get_value(["x", "missing"])

    def test_delete_value_and_cleanup_empties_intermediate_dicts(
        self,
        tmp_path: Path,
    ) -> None:
        db_path = tmp_path / "db.json"
        db = JSONMultiDB.create_new(db_path, dimensions=3)

        coords1 = ["entity1", "2025", "01"]
        coords2 = ["entity1", "2025", "02"]

        db.set_value(coords1, {"value": 1})
        db.set_value(coords2, {"value": 2})

        db.delete_value(coords1)
        assert db.get_value(coords2) == {"value": 2}
        assert "01" not in db.get_slice(["entity1", "2025"])

        db.delete_value(coords2)
        assert "entity1" not in db.get_slice([])

    def test_get_slice_for_entire_tree_and_prefix(self, tmp_path: Path) -> None:
        db_path = tmp_path / "db.json"
        db = JSONMultiDB.create_new(db_path, dimensions=3)

        db.set_value(["u1", "2025", "01"], {"orders": 1})
        db.set_value(["u1", "2025", "02"], {"orders": 2})
        db.set_value(["u2", "2025", "01"], {"orders": 3})

        full_tree = db.get_slice([])
        assert full_tree != {}
        assert full_tree["u1"]["2025"]["01"]["orders"] == 1

        copy_tree = db.get_slice([])
        copy_tree["u1"]["2025"]["01"]["orders"] = 999
        untouched = db.get_slice(["u1", "2025", "01"])
        assert untouched["orders"] == 1

        u1_slice = db.get_slice(["u1"])
        assert set(u1_slice.keys()) == {"2025"}
        assert "u2" not in u1_slice

        u1_2025_slice = db.get_slice(["u1", "2025"])
        assert set(u1_2025_slice.keys()) == {"01", "02"}

    def test_get_slice_prefix_longer_than_dimensions_raises(
        self,
        tmp_path: Path,
    ) -> None:
        db, _ = self._build_sample_db(tmp_path)

        with pytest.raises(ValueError):
            db.get_slice(["too", "many", "coords", "here"])

    def test_get_slice_missing_path_raises_key_error(
        self,
        tmp_path: Path,
    ) -> None:
        db, _ = self._build_sample_db(tmp_path)

        with pytest.raises(KeyError):
            db.get_slice(["does_not_exist"])

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _build_sample_db(self, tmp_path: Path) -> Tuple[JSONMultiDB, Path]:
        db_path = tmp_path / "db.json"
        db = JSONMultiDB.create_new(db_path, dimensions=3)

        db.set_value(["a", "b", "c"], {"v": 1})
        db.set_value(["a", "b", "d"], {"v": 2})
        db.set_value(["x", "y", "z"], {"v": 3})

        return db, db_path
