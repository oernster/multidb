from __future__ import annotations

from pathlib import Path

import pytest

from multidb import MultiDB
from multidb.errors import ReadOnlyError
from multidb.query.ast import Field


def test_create_set_get_commit_roundtrip(tmp_path: Path) -> None:
    db_path = tmp_path / "db.json"
    db = MultiDB.create(db_path, dimensions=2)
    db.set(("u1", "k1"), {"v": 1})
    db.commit()

    db2 = MultiDB.open(db_path, mode="r")
    assert db2.get(("u1", "k1")) == {"v": 1}


def test_rollback_discards_overlay(tmp_path: Path) -> None:
    db_path = tmp_path / "db.json"
    db = MultiDB.create(db_path, dimensions=1)
    db.set(("a",), 1)
    db.commit()

    db.set(("a",), 2)
    db.rollback()
    assert db.get(("a",)) == 1


def test_read_only_rejects_writes(tmp_path: Path) -> None:
    db_path = tmp_path / "db.json"
    MultiDB.create(db_path, dimensions=1)

    ro = MultiDB.open(db_path, mode="r")
    with pytest.raises(ReadOnlyError):
        ro.set(("a",), 1)


def test_list_with_prefix_and_depth(tmp_path: Path) -> None:
    db_path = tmp_path / "db.json"
    db = MultiDB.create(db_path, dimensions=3)
    db.set(("u1", "2025", "01"), 1)
    db.set(("u1", "2025", "02"), 2)
    db.set(("u2", "2025", "01"), 3)
    db.commit()

    assert set(db.list(prefix=("u1",))) == {
        ("u1", "2025", "01"),
        ("u1", "2025", "02"),
    }
    # Depth relative to prefix: prefix len=1, depth=1 => return 2 components.
    assert set(db.list(prefix=("u1",), depth=1)) == {("u1", "2025")}


def test_find_with_field_predicate(tmp_path: Path) -> None:
    db_path = tmp_path / "db.json"
    db = MultiDB.create(db_path, dimensions=2)
    db.set(("k", "1"), {"customer_id": "c1", "amount": 10})
    db.set(("k", "2"), {"customer_id": "c2", "amount": 20})
    db.commit()

    expr = Field(("customer_id",), "==", "c2")
    rows = db.find(prefix=("k",), where=expr)
    assert rows == [(("k", "2"), {"customer_id": "c2", "amount": 20})]
