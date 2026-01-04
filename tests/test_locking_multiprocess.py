from __future__ import annotations

import multiprocessing as mp
import time
from pathlib import Path

from multidb import MultiDB
from multidb.errors import LockError


def _writer_hold_open(db_path: str, hold_s: float) -> None:
    # Hold the writer lock for a bit.
    db = MultiDB.open(db_path, mode="rw")
    time.sleep(hold_s)
    db.rollback()


def _writer_try_open(db_path: str, q: mp.Queue) -> None:
    try:
        db = MultiDB.open(db_path, mode="rw")
        db.rollback()
        q.put(True)
    except LockError:
        q.put(False)


def test_two_writers_cannot_open_concurrently(tmp_path: Path) -> None:
    db_path = tmp_path / "db.json"
    MultiDB.create(db_path, dimensions=1)

    q: mp.Queue = mp.Queue()

    p1 = mp.Process(target=_writer_hold_open, args=(str(db_path), 1.5))
    p2 = mp.Process(target=_writer_try_open, args=(str(db_path), q))

    p1.start()
    # Give the first writer time to acquire the lock.
    time.sleep(0.2)
    p2.start()

    p2.join(timeout=5)
    p1.join(timeout=5)

    assert q.get(timeout=2) is False


def _reader_get(db_path: str, q: mp.Queue) -> None:
    db = MultiDB.open(db_path, mode="r")
    q.put(db.get(("a",)))


def test_reader_can_open_while_writer_session_exists(tmp_path: Path) -> None:
    db_path = tmp_path / "db.json"
    db = MultiDB.create(db_path, dimensions=1)
    db.set(("a",), 123)
    db.commit()

    writer = mp.Process(target=_writer_hold_open, args=(str(db_path), 1.0))
    q: mp.Queue = mp.Queue()
    reader = mp.Process(target=_reader_get, args=(str(db_path), q))

    writer.start()
    time.sleep(0.2)
    reader.start()

    reader.join(timeout=5)
    writer.join(timeout=5)

    assert q.get(timeout=2) == 123
