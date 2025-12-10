# app.py

from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from config import DB_FILE_PATH
from db import JSONMultiDB
from schemas import (
    InitRequest,
    InitResponse,
    SetItemRequest,
    GetItemResponse,
    DeleteItemRequest,
    SliceRequest,
    SliceResponse,
    InfoResponse,
)

app = FastAPI(title="Multidimensional JSON DB API")

# Global DB instance (simple demo; not ideal for huge apps)
_db: Optional[JSONMultiDB] = None


def get_db(or_error: bool = True) -> Optional[JSONMultiDB]:
    global _db
    if _db is None and DB_FILE_PATH.exists():
        # Auto-load existing DB if file is present
        try:
            _db = JSONMultiDB(DB_FILE_PATH)
        except Exception:
            # If load fails, let it fall through
            pass

    if _db is None and or_error:
        raise HTTPException(
            status_code=400,
            detail="Database is not initialized. Call POST /init first.",
        )
    return _db


@app.get("/info", response_model=InfoResponse)
def info():
    """
    Get basic info about the DB (dimensions, initialized?).
    """
    db = get_db(or_error=False)
    if db is None:
        return InfoResponse(dimensions=None, initialized=False)
    return InfoResponse(dimensions=db.get_dimensions(), initialized=True)


@app.post("/init", response_model=InitResponse)
def init_db(req: InitRequest):
    """
    Initialize (or re-initialize) the DB with a given number of dimensions.
    This overwrites any existing DB file.
    """
    global _db
    try:
        _db = JSONMultiDB.create_new(DB_FILE_PATH, dimensions=req.dimensions)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return InitResponse(
        message="Database initialized",
        dimensions=_db.get_dimensions(),
    )


@app.post("/item", response_model=GetItemResponse)
def set_item(req: SetItemRequest):
    """
    Set a value at an N-dimensional coordinate.
    coords length must match the initialized dimensions.
    """
    db = get_db()
    try:
        db.set_value(req.coords, req.value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return GetItemResponse(coords=req.coords, value=req.value)


@app.get("/item", response_model=GetItemResponse)
def get_item(coords: List[str] = Query(..., description="Coordinate keys")):
    """
    Get value at an N-dimensional coordinate.
    Example: /item?coords=x&coords=y&coords=z
    """
    db = get_db()
    try:
        value = db.get_value(coords)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return GetItemResponse(coords=coords, value=value)


@app.delete("/item", response_class=JSONResponse)
def delete_item(req: DeleteItemRequest):
    """
    Delete value at an N-dimensional coordinate.
    """
    db = get_db()
    try:
        db.delete_value(req.coords)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"message": "Deleted", "coords": req.coords}


@app.post("/slice", response_model=SliceResponse)
def get_slice(req: SliceRequest):
    """
    Get a sub-tree for a coordinate prefix.
    For example, with 3 dimensions:
      prefix=[]          -> entire DB data tree
      prefix=["x"]       -> all at x, across remaining dimensions
      prefix=["x","y"]   -> all at x->y, across remaining dimensions
    """
    db = get_db()
    prefix = req.prefix or []

    try:
        if not prefix:
            # Whole data tree
            data = db.data  # already JSON-serializable
        else:
            data = db.get_slice(prefix)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return SliceResponse(prefix=prefix, data=data)


# Optional: convenience root
@app.get("/")
def root():
    return {"message": "Multidimensional JSON DB API. See /docs for Swagger UI."}


# To run with: uvicorn app:app --reload
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
