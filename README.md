# MultiDimensionalDB

MultiDimensionalDB v2 is a tiny embedded document database for Python.

Key properties:

- Library-first design (usable without any server)
- Single-file JSON storage
- Atomic, crash-safe commits via temp-file replace
- Safe multi-process access (single writer, multiple readers)
- Minimal indexing and query support (MVP)

> **See also:** [USE_CASES.md](USE_CASES.md) — a concise overview of practical applications and patterns enabled by this multidimensional JSON storage model.  
You can initialize the database with any number of dimensions and read/write values using coordinates.

### If you like it please buy me a coffee: [Donation link](https://www.paypal.com/ncp/payment/Z36XJEEA4MNV6)

---

## Features

- JSON file-based embedded document database
- N-dimensional coordinate keys
- Atomic commit and recovery
- Prefix key listing and basic querying
- Optional FastAPI wrapper with Swagger (`/docs`) and ReDoc (`/redoc`)

---

## Installation

## 1. Create a virtual environment

### Windows (PowerShell)

```powershell
python -m venv venv
venv\Scripts\activate
```

### Linux / macOS / WSL

```bash
python3 -m venv venv
source venv/bin/activate
```

---

### 2. Install dependencies

From within the activated venv:

This project uses `uv` for environment management.

```powershell
uv venv .venv
uv pip install -r requirements.txt --python .venv\Scripts\python.exe
```

## Library usage (v2)

Create/open a database and commit writes:

```python
from multidb import MultiDB

db = MultiDB.create("./mydb.json", dimensions=2)
db.set(("user1", "orders"), {"count": 3})
db.commit()

ro = MultiDB.open("./mydb.json", mode="r")
print(ro.get(("user1", "orders")))
```

## Running the FastAPI wrapper (v2)

Inside the project folder:

```powershell
.\.venv\Scripts\python.exe -m uvicorn multidb.server.app:app --reload
```

The server will start at:

```
http://localhost:8000
```

---

## API Documentation

FastAPI automatically exposes interactive documentation:

### Swagger UI (interactive)
```
http://localhost:8000/docs
```

### ReDoc (static reference docs)
```
http://localhost:8000/redoc
```

---

## Typical API Usage

### Initialize a DB

The FastAPI wrapper uses query parameters for simplicity.

```bash
curl -X POST "http://localhost:8000/init?path=./mydb.json&dimensions=3&overwrite=true"
```

---

### Set a value

```bash
curl -X POST "http://localhost:8000/item?path=./mydb.json" \
  -H "Content-Type: application/json" \
  -d '{"coords": ["user1", "2025-01-01", "orders"], "value": {"order_id": 123, "amount": 49.99}}'
```

---

### Get an item

```bash
curl "http://localhost:8000/item?path=./mydb.json&coords=user1&coords=2025-01-01&coords=orders"
```

---

### List by prefix

```bash
curl "http://localhost:8000/list?path=./mydb.json&prefix=user1"
```

---

### Delete an item

```bash
curl -X DELETE "http://localhost:8000/item?path=./mydb.json" \
  -H "Content-Type: application/json" \
  -d '{"coords": ["user1", "2025-01-01", "orders"]}'
```

