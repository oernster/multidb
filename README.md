# AxisDB

**AxisDB** is a tiny embedded document database for Python, designed for simple, reliable storage of JSON documents addressed by **N-dimensional coordinate keys**.

It is library-first, requires no server, and stores all data in a single JSON file with atomic, crash-safe commits.

> **See also:**  
> [USE_CASES.md](https://github.com/oernster/AxisDB/blob/main/USE_CASES.md) — a concise overview of practical applications and patterns enabled by this multidimensional JSON storage model.

---

## Key properties

- Library-first design (usable without any server)
- Single-file JSON storage
- Atomic, crash-safe commits via temp-file replace
- Safe multi-process access (single writer, multiple readers) via file locks
- Minimal but useful query + indexing support (correctness-first)

---

## Features

- Embedded JSON document database
- N-dimensional coordinate keys
- Atomic commit and recovery
- Key listing (`list`) and multidimensional slicing (`slice`)
- Basic querying (`find`) with optional persisted field indexes
- Optional FastAPI wrapper with Swagger (`/docs`) and ReDoc (`/redoc`)

---

## Installation

### Core library

```bash
pip install axisdb
```

### Optional server components

```bash
pip install "axisdb[server]"
```

---

## Basic library usage

Create a database, write a value, and commit:

```python
from axisdb import AxisDB

db = AxisDB.create("./mydb.json", dimensions=2)
db.set(("user1", "orders"), {"count": 3})
db.commit()

ro = AxisDB.open("./mydb.json", mode="r")
print(ro.get(("user1", "orders")))
```

Notes:

- **Dimensions are fixed** at database creation time; all keys must be a `tuple[str, ...]` of that length.
- Values must be **JSON-serializable** (validated by default on `set`).
- `mode="rw"` writes are staged in-memory until `commit()`; `rollback()` discards uncommitted changes.
- `mode="r"` reloads from disk on each operation to reflect the latest committed state.

---

## Query and indexing (MVP)

AxisDB is optimized for correctness and predictable behavior over complex query planning.

- Indexes are **materialized and persisted** in the DB file.
- Indexes are **rebuilt on each commit** (correctness-first MVP).
- `find()` can use indexes only when there are **no pending writes in the current session**.

### Index types

- **Prefix index** — always maintained; used by `find(prefix=...)` to reduce scan work
  (note: `list(prefix=...)` currently filters materialized keys directly).
- **Field indexes** — optional, user-defined; can accelerate simple equality predicates of the form
  `Field(("path", "to", "field"), "==", literal)`.

Define a field index:

```python
from axisdb import AxisDB

db = AxisDB.create("./mydb.json", dimensions=2)
db.define_field_index("by_customer_id", ("customer_id",))
```

Query with an expression:

```python
from axisdb import AxisDB
from axisdb.query.ast import Field

db = AxisDB.open("./mydb.json", mode="r")
rows = db.find(prefix=("orders",), where=Field(("customer_id",), "==", "c2"))
```

---

## Running the FastAPI wrapper (optional)

After installing the server extras:

```bash
pip install "axisdb[server]"
```

Run the server:

```bash
python -m uvicorn axisdb.server.app:app --reload
```

The server will start at:

```
http://localhost:8000
```

---

## API documentation

FastAPI automatically exposes interactive documentation:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### REST endpoints (thin wrapper)

The server is intentionally a minimal translation layer over the library:

- `GET /info?path=...`
- `POST /init?path=...&dimensions=...&overwrite=false`
- `POST /item?path=...` (body: `{ "coords": [...], "value": ... }`)
- `GET /item?path=...&coords=...&coords=...`
- `DELETE /item?path=...` (body: `{ "coords": [...] }`)
- `GET /list?path=...&prefix=...&depth=...`
- `GET /find?path=...&prefix=...&field=...&op===&value=...&limit=...`

The wrapper does not bypass durability or locking: it opens the database in `mode="r"` or `mode="rw"` as needed and uses the same commit semantics.

---

## Concurrency model (locking)

By default (`lock=True`), AxisDB uses two lock files next to the database file:

- `*.writer.lock` — exclusive lock held for the lifetime of a writer session (`mode="rw"`)
- `*.rw.lock` — shared during reads; exclusive during `commit()`

This supports **single-writer / multiple-reader** access across processes.

---

## Versioning and compatibility

This project follows **semantic versioning**.

Guaranteed stable within a major version:

- Public `AxisDB` API: `open`, `create`, `get`, `set`, `delete`, `exists`, `list`, `slice`, `find`, `commit`, `rollback`
- Public exception types in `axisdb.errors`
- On-disk file format (`format=axisdb`, `format_version=2`)

May change in minor versions:

- Internal module structure and private attributes
- Index query planning details

Breaking changes will only occur in the next major version.

---

## Development

Run tests:

```bash
python -m pytest -q
```
