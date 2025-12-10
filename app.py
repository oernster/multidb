"""FastAPI application exposing the multidimensional JSON DB."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from config import DB_FILE_PATH
from db import JSONMultiDB
from schemas import (
    DeleteItemRequest,
    GetItemResponse,
    InfoResponse,
    InitRequest,
    InitResponse,
    SetItemRequest,
    SliceRequest,
    SliceResponse,
)


class DatabaseService:
    """Application layer façade around :class:`JSONMultiDB`.

    This keeps FastAPI routes free from persistence details and allows
    for easier substitution in tests or other front-ends.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db: JSONMultiDB | None = None

    # ------------------------------------------------------------------ #
    # Lifecycle helpers
    # ------------------------------------------------------------------ #

    def _ensure_loaded(self) -> JSONMultiDB:
        if self._db is None:
            if not self._db_path.exists():
                raise HTTPException(
                    status_code=400,
                    detail="Database is not initialized. Call /init first.",
                )
            self._db = JSONMultiDB(self._db_path)
        return self._db

    def init_database(self, dimensions: int) -> JSONMultiDB:
        self._db = JSONMultiDB.create_new(self._db_path, dimensions=dimensions)
        return self._db

    def is_initialized(self) -> bool:
        if self._db is not None:
            return True
        if self._db_path.exists():
            return True
        return False

    # ------------------------------------------------------------------ #
    # Delegated operations
    # ------------------------------------------------------------------ #

    def info(self) -> InfoResponse:
        if not self.is_initialized():
            return InfoResponse(dimensions=None, initialized=False)

        db = self._ensure_loaded()
        return InfoResponse(dimensions=db.get_dimensions(), initialized=True)

    def set_item(self, coords: List[str], value: Any) -> GetItemResponse:
        db = self._ensure_loaded()
        try:
            db.set_value(coords, value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return GetItemResponse(coords=coords, value=value)

    def get_item(self, coords: List[str]) -> GetItemResponse:
        db = self._ensure_loaded()
        try:
            value = db.get_value(coords)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return GetItemResponse(coords=coords, value=value)

    def delete_item(self, coords: List[str]) -> dict[str, Any]:
        db = self._ensure_loaded()
        try:
            db.delete_value(coords)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"message": "Deleted", "coords": coords}

    def slice_items(self, prefix: List[str]) -> SliceResponse:
        db = self._ensure_loaded()
        prefix = prefix or []
        try:
            data = db.get_slice(prefix)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return SliceResponse(prefix=prefix, data=data)


app = FastAPI(title="Multidimensional JSON DB API")

_db_service = DatabaseService(DB_FILE_PATH)


def get_database_service() -> DatabaseService:
    """FastAPI dependency returning the shared database service."""
    return _db_service


@app.get("/info", response_model=InfoResponse)
def info(service: DatabaseService = Depends(get_database_service)) -> InfoResponse:
    """Return basic information about the database."""
    return service.info()


@app.post("/init", response_model=InitResponse)
def init_db(
    req: InitRequest,
    service: DatabaseService = Depends(get_database_service),
) -> InitResponse:
    """Initialise (or re-initialise) the database."""
    db = service.init_database(req.dimensions)
    return InitResponse(message="Database initialized", dimensions=db.get_dimensions())


@app.post("/item", response_model=GetItemResponse)
def set_item(
    req: SetItemRequest,
    service: DatabaseService = Depends(get_database_service),
) -> GetItemResponse:
    """Create or replace a value at an N-dimensional coordinate."""
    return service.set_item(coords=req.coords, value=req.value)


@app.get("/item", response_model=GetItemResponse)
def get_item(
    coords: List[str] = Query(...),
    service: DatabaseService = Depends(get_database_service),
) -> GetItemResponse:
    """Retrieve a value at an N-dimensional coordinate."""
    return service.get_item(coords=coords)


@app.delete("/item", response_class=JSONResponse)
def delete_item(
    req: DeleteItemRequest,
    service: DatabaseService = Depends(get_database_service),
) -> JSONResponse:
    """Delete value at an N-dimensional coordinate."""
    body = service.delete_item(coords=req.coords)
    return JSONResponse(content=body)


@app.post("/slice", response_model=SliceResponse)
def slice_items(
    req: SliceRequest,
    service: DatabaseService = Depends(get_database_service),
) -> SliceResponse:
    """Return a slice of the database for a given coordinate prefix."""
    return service.slice_items(prefix=req.prefix)


@app.get("/")
def root() -> dict[str, str]:
    """Simple health endpoint for convenience."""
    return {"message": "Multidimensional JSON DB API. See /docs for Swagger UI."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
