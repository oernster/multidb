"""FastAPI wrapper over the MultiDB library.

This is intentionally a thin layer:
- It does not implement database logic.
- It converts HTTP requests into calls to [`MultiDB`](multidb/api.py:1).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query

from multidb import MultiDB
from multidb.errors import (
    LockError,
    ReadOnlyError,
    StorageCorruptionError,
    ValidationError,
)
from multidb.query.ast import Field
from multidb.server.schemas import DeleteBody, InitResponse, ItemBody

app = FastAPI(title="MultiDimensionalDB v2")


def _to_http(exc: Exception) -> HTTPException:
    if isinstance(exc, (ValidationError, ReadOnlyError)):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail="Not found")
    if isinstance(exc, LockError):
        return HTTPException(status_code=423, detail=str(exc))
    if isinstance(exc, StorageCorruptionError):
        return HTTPException(status_code=500, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@app.get("/info")
def info(path: str) -> dict[str, Any]:
    try:
        db = MultiDB.open(path, mode="r")
        return {"path": str(Path(path)), "dimensions": db.dimensions, "mode": "r"}
    except Exception as exc:  # noqa: BLE001
        raise _to_http(exc) from exc


@app.post("/init")
def init_db(path: str, dimensions: int, overwrite: bool = False) -> InitResponse:
    try:
        db = MultiDB.create(path, dimensions=dimensions, overwrite=overwrite)
        return InitResponse(
            path=str(Path(path)),
            dimensions=db.dimensions,
            created=True,
        )
    except Exception as exc:  # noqa: BLE001
        raise _to_http(exc) from exc


@app.post("/item")
def set_item(path: str, body: ItemBody = Body(...)) -> dict[str, Any]:
    try:
        with MultiDB.open(path, mode="rw") as db:
            db.set(tuple(body.coords), body.value)
            db.commit()
        return {"coords": body.coords, "value": body.value}
    except Exception as exc:  # noqa: BLE001
        raise _to_http(exc) from exc


@app.get("/item")
def get_item(path: str, coords: list[str] = Query(...)) -> dict[str, Any]:
    try:
        db = MultiDB.open(path, mode="r")
        value = db.get(tuple(coords))
        return {"coords": coords, "value": value}
    except Exception as exc:  # noqa: BLE001
        raise _to_http(exc) from exc


@app.delete("/item")
def delete_item(path: str, body: DeleteBody = Body(...)) -> dict[str, Any]:
    try:
        with MultiDB.open(path, mode="rw") as db:
            db.delete(tuple(body.coords))
            db.commit()
        return {"coords": body.coords, "deleted": True}
    except Exception as exc:  # noqa: BLE001
        raise _to_http(exc) from exc


@app.get("/list")
def list_items(
    path: str, prefix: list[str] | None = None, depth: int | None = None
) -> dict[str, Any]:
    try:
        db = MultiDB.open(path, mode="r")
        keys = db.list(prefix=tuple(prefix or ()), depth=depth)
        return {"keys": [list(k) for k in keys]}
    except Exception as exc:  # noqa: BLE001
        raise _to_http(exc) from exc


@app.get("/find")
def find_items(
    path: str,
    prefix: list[str] | None = None,
    field: list[str] | None = None,
    op: str = "==",
    value: Any = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Minimal query endpoint.

    MVP: supports a single field predicate.
    """

    try:
        db = MultiDB.open(path, mode="r")
        expr = None
        if field is not None:
            expr = Field(tuple(field), op, value)  # type: ignore[arg-type]
        rows = db.find(prefix=tuple(prefix or ()), where=expr, limit=limit)
        return {"rows": [{"key": list(k), "value": v} for k, v in rows]}
    except Exception as exc:  # noqa: BLE001
        raise _to_http(exc) from exc
