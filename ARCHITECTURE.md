# MultiDimensionalDB v2 — Architectural Overview

This document describes the architecture of MultiDimensionalDB v2 as implemented in this repository.

Goals prioritized: correctness, durability, and testability over performance.

## 1. What this project is

MultiDimensionalDB v2 is a small embedded document database implemented as a Python library with an optional FastAPI wrapper.

- Embedded: local file storage; no networking in the core.
- Document DB: values are JSON-serializable documents (or JSON-compatible primitives).
- Multi-dimensional keys: keys are N-dimensional coordinate paths (sequence of strings).

Primary entrypoint: [`MultiDB`](multidb/api.py:1)

Optional REST wrapper: [`multidb.server.app:app`](multidb/server/app.py:1)

## 2. High-level architecture

The system is structured into:

- API layer: public database handle and transaction semantics.
- Engine layer: storage, recovery, locking, and key encoding.
- Indexing layer: minimal indexes maintained on commit.
- Query layer: expression tree and evaluator.
- Server wrapper: thin FastAPI layer mapping HTTP requests to library calls.

Key design choice: durable operations are implemented by rewriting the full database file on commit, using an atomic replace operation, rather than a WAL/journal.

## 3. Data model

### 3.1 Keys

External form: `tuple[str, ...]` with length `N` where `N = dimensions`.

On-disk form: a single encoded string, constructed by percent-encoding each component and joining with `/`.

Key codec: [`multidb.engine.keycodec`](multidb/engine/keycodec.py:1)

### 3.2 Values

Values must be JSON-serializable by default.

The library validates serializability on `set()`.

## 4. Storage format and durability

### 4.1 On-disk format

The database is stored as a single JSON file with a stable schema (format name and version).

Storage code: [`multidb.engine.storage`](multidb/engine/storage.py:1)

Key fields:

- `format`, `format_version`
- `meta`: includes `dimensions`, timestamps, and index definitions
- `data`: mapping `encoded_key -> value`
- `index`: materialized indexes (prefix keys and optional field indexes)

### 4.2 Atomic commits

Commit writes to a temp file and then atomically replaces the main file:

1. Serialize complete next-state payload to `path + .tmp`.
2. Flush and fsync the temp file.
3. Replace main file via `os.replace(tmp, path)`.
4. Best-effort directory fsync.

Commit code: [`write_atomic()`](multidb/engine/storage.py:1)

Correctness goal: after a crash, the database is either the old valid file or the new valid file, not a torn partial write.

### 4.3 Recovery on open

On open, recovery checks for an orphaned temp file and promotes it if needed.

Recovery code: [`recover_if_needed()`](multidb/engine/storage.py:1)

Recovery rules:

- If main is valid and temp exists: delete temp.
- If main is missing/invalid and temp is valid: promote temp.
- If neither is valid: raise `StorageCorruptionError`.

## 5. Concurrency model and locking

Design target: single writer, multiple readers, cross-platform.

Locking code: [`multidb.engine.locking`](multidb/engine/locking.py:1)

Two lock files are used:

- `*.writer.lock`: exclusive lock held for the lifetime of a writer session.
- `*.rw.lock`: shared lock used for reads; exclusive lock used during commit.

Integration points:

- Writer lock acquired in [`MultiDB._initialize()`](multidb/api.py:1) when opened with `mode='rw'`.
- Commit acquires an exclusive rw lock in [`MultiDB.commit()`](multidb/api.py:1).
- Read-only operations load from disk and use shared rw locking during file read.

## 6. Transaction semantics

`mode='rw'` provides an overlay transaction model:

- Writes are accumulated in-memory (`_overlay_set`, `_overlay_del`).
- Reads consult overlay first, then base.
- `commit()` materializes a new on-disk state and clears the overlay.
- `rollback()` discards overlay and reloads base state from disk.

Implementation: [`multidb.api`](multidb/api.py:1)

`mode='r'` is read-only; each read operation reloads from disk to reflect the latest committed state.

## 7. Indexing

Indexes are correctness-first and rebuilt on commit.

### 7.1 Prefix index

Purpose: accelerate prefix key scans.

Representation: sorted list of all encoded keys.

Implementation: [`multidb.index.prefix`](multidb/index/prefix.py:1)

### 7.2 Field indexes

Purpose: optional acceleration for field-based predicates.

Representation: `index_name -> canonical_value -> [encoded_keys...]`.

Implementation: [`multidb.index.fields`](multidb/index/fields.py:1)

Note: current `find()` uses the prefix index as the primary candidate filter; field indexes are persisted and rebuilt but not yet used for candidate selection.

## 8. Query system

Queries are represented as a small expression tree (AST) and evaluated against candidate documents.

AST: [`multidb.query.ast`](multidb/query/ast.py:1)

Evaluator: [`multidb.query.eval`](multidb/query/eval.py:1)

`MultiDB.find()` supports:

- Prefix restriction.
- `where` as either an AST expression or a Python callable.

See: [`MultiDB.find()`](multidb/api.py:1)

## 9. Slice API

`slice(dim_slices)` returns a nested dictionary view of matching keys.

Selectors per dimension:

- `None`: wildcard
- `str`: exact match
- `list/tuple/set[str]`: membership match
- `callable`: predicate on the component

Implementation: [`MultiDB.slice()`](multidb/api.py:1)

## 10. FastAPI wrapper

The FastAPI app is a thin translation layer that maps HTTP requests to library operations.

App module: [`multidb.server.app`](multidb/server/app.py:1)

Request body models: [`multidb.server.schemas`](multidb/server/schemas.py:1)

The wrapper does not bypass durability or locking; it opens the library with appropriate modes for each endpoint.

## 11. Testing strategy

Testing emphasizes real file IO and real multiprocess behavior.

Key tests:

- Recovery logic: [`tests/test_storage_recovery.py`](tests/test_storage_recovery.py)
- Multiprocess locking: [`tests/test_locking_multiprocess.py`](tests/test_locking_multiprocess.py)
- API behavior: [`tests/test_api_basic.py`](tests/test_api_basic.py)
- Slice behavior: [`tests/test_slice.py`](tests/test_slice.py)
- Key encoding: [`tests/test_keycodec.py`](tests/test_keycodec.py)

Run tests with:

- `.\.venv\Scripts\python.exe -m pytest -q`

