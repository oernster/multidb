import json
import warnings
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app
from db import JSONMultiDB

# Suppress noisy third-party warnings so the test suite runs cleanly.
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)


@pytest.fixture
def temp_db_path(tmp_path):
    """Return a path for a temporary JSON DB file and reset app state."""
    path = tmp_path / "test_db.json"
    # Point the app at this temp file and reset in-memory DB
    app.DB_FILE_PATH = path
    app._db = None
    return path


@pytest.fixture
def client(temp_db_path):
    """FastAPI TestClient wired to use the temporary DB file."""
    # temp_db_path fixture already configured app.DB_FILE_PATH and app._db
    return TestClient(app.app)


# ---------- JSONMultiDB unit tests ----------

def test_create_new_and_load_round_trip(tmp_path):
    db_path = tmp_path / "db.json"

    # Create a new DB with 3 dimensions
    db = JSONMultiDB.create_new(db_path, dimensions=3)
    assert db.get_dimensions() == 3
    assert db.data == {}

    # File should exist on disk and be valid JSON
    assert db_path.exists()
    raw = json.loads(db_path.read_text())
    assert raw["meta"]["dimensions"] == 3
    assert raw["data"] == {}

    # Reload from disk into a fresh instance
    db2 = JSONMultiDB(db_path)
    assert db2.get_dimensions() == 3
    assert db2.data == {}


def test_create_new_with_invalid_dimensions_raises(tmp_path):
    db_path = tmp_path / "db.json"
    with pytest.raises(ValueError):
        JSONMultiDB.create_new(db_path, dimensions=0)
    with pytest.raises(ValueError):
        JSONMultiDB.create_new(db_path, dimensions=-1)


def test_file_must_exist_for_init(tmp_path):
    db_path = tmp_path / "does_not_exist.json"
    assert not db_path.exists()
    with pytest.raises(FileNotFoundError):
        JSONMultiDB(db_path)


def test_set_and_get_value_happy_path(tmp_path):
    db_path = tmp_path / "db.json"
    db = JSONMultiDB.create_new(db_path, dimensions=3)

    coords = ["user1", "2025-01", "orders"]
    value = {"order_id": 123, "total": 9.99}

    db.set_value(coords, value)
    # Value should be retrievable
    assert db.get_value(coords) == value

    # Underlying data structure should reflect nested dictionaries
    assert db.data["user1"]["2025-01"]["orders"] == value


def test_set_value_with_wrong_number_of_coords_raises(tmp_path):
    db_path = tmp_path / "db.json"
    db = JSONMultiDB.create_new(db_path, dimensions=2)

    with pytest.raises(ValueError):
        db.set_value(["only_one"], value=1)

    with pytest.raises(ValueError):
        db.set_value(["a", "b", "c"], value=1)


def test_get_value_errors_for_missing_path_or_wrong_length(tmp_path):
    db_path = tmp_path / "db.json"
    db = JSONMultiDB.create_new(db_path, dimensions=2)
    db.set_value(["x", "y"], 42)

    # Wrong number of coordinates
    with pytest.raises(ValueError):
        db.get_value(["x"])

    # Missing intermediate key
    with pytest.raises(KeyError):
        db.get_value(["missing", "y"])

    # Missing leaf key
    with pytest.raises(KeyError):
        db.get_value(["x", "missing"])


def test_delete_value_and_cleanup_empties_intermediate_dicts(tmp_path):
    db_path = tmp_path / "db.json"
    db = JSONMultiDB.create_new(db_path, dimensions=3)

    coords1 = ["entity1", "2025", "01"]
    coords2 = ["entity1", "2025", "02"]

    db.set_value(coords1, {"value": 1})
    db.set_value(coords2, {"value": 2})

    # Delete first value: parent keys should still exist because coords2 remains
    db.delete_value(coords1)
    assert db.get_value(coords2) == {"value": 2}
    assert "01" not in db.data["entity1"]["2025"]

    # Delete second value: cleanup should remove now-empty nested dicts
    db.delete_value(coords2)
    assert "entity1" not in db.data


def test_get_slice_for_entire_tree_and_prefix(tmp_path):
    db_path = tmp_path / "db.json"
    db = JSONMultiDB.create_new(db_path, dimensions=3)

    db.set_value(["u1", "2025", "01"], {"orders": 1})
    db.set_value(["u1", "2025", "02"], {"orders": 2})
    db.set_value(["u2", "2025", "01"], {"orders": 3})

    # Full tree via prefix=[]
    full = db.get_slice([])
    assert full == db.data

    # Modify returned object and ensure underlying data is unchanged (deep copy)
    full["u1"]["2025"]["01"]["orders"] = 999
    assert db.data["u1"]["2025"]["01"]["orders"] == 1

    # Single-key prefix
    u1_slice = db.get_slice(["u1"])
    assert set(u1_slice.keys()) == {"2025"}
    assert "u2" not in u1_slice

    # Two-key prefix
    u1_2025 = db.get_slice(["u1", "2025"])
    assert set(u1_2025.keys()) == {"01", "02"}

    # Non-existent prefix raises KeyError
    with pytest.raises(KeyError):
        db.get_slice(["missing"])

    # Prefix longer than dimensions raises ValueError
    with pytest.raises(ValueError):
        db.get_slice(["too", "many", "keys", "here"])


# ---------- FastAPI API tests ----------

def test_info_before_initialization_shows_uninitialized(client, temp_db_path):
    # Ensure no DB file exists and in-memory DB is reset
    if temp_db_path.exists():
        temp_db_path.unlink()
    app._db = None

    response = client.get("/info")
    assert response.status_code == 200
    data = response.json()
    assert data == {"dimensions": None, "initialized": False}


def test_init_endpoint_creates_db_file_and_returns_info(client, temp_db_path):
    response = client.post("/init", json={"dimensions": 3})
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Database initialized"
    assert data["dimensions"] == 3

    # DB file should exist with correct metadata
    assert temp_db_path.exists()
    raw = json.loads(temp_db_path.read_text())
    assert raw["meta"]["dimensions"] == 3


def test_init_endpoint_rejects_invalid_dimensions(client):
    # Pydantic validation (gt=0) rejects non-positive dimensions with HTTP 422
    for bad in [0, -1]:
        response = client.post("/init", json={"dimensions": bad})
        assert response.status_code == 422
        detail = response.json()["detail"]
        # At least one error should mention "greater than 0"
        assert any("greater than 0" in err.get("msg", "") for err in detail)


def test_item_crud_via_api(client):
    # Initialize DB with 3 dimensions
    init_resp = client.post("/init", json={"dimensions": 3})
    assert init_resp.status_code == 200

    coords = ["user1", "2025-01-01", "orders"]
    value = {"id": 1, "total": 10.5}

    # Create / set item
    set_resp = client.post("/item", json={"coords": coords, "value": value})
    assert set_resp.status_code == 200
    assert set_resp.json() == {"coords": coords, "value": value}

    # Retrieve item
    get_resp = client.get(
        "/item",
        params=[("coords", c) for c in coords],
    )
    assert get_resp.status_code == 200
    assert get_resp.json() == {"coords": coords, "value": value}

    # Slice with prefix
    slice_resp = client.post("/slice", json={"prefix": ["user1"]})
    assert slice_resp.status_code == 200
    body = slice_resp.json()
    assert body["prefix"] == ["user1"]
    # Should contain nested data for this user
    assert "2025-01-01" in body["data"]

    # Delete item (use generic request() to support json body for DELETE)
    del_resp = client.request("DELETE", "/item", json={"coords": coords})
    assert del_resp.status_code == 200
    assert del_resp.json()["message"] == "Deleted"

    # Subsequent GET should 404
    get_missing = client.get("/item", params=[("coords", c) for c in coords])
    assert get_missing.status_code == 404


def test_endpoints_require_initialization(client):
    # Reset app state and ensure DB file is absent
    app._db = None
    if app.DB_FILE_PATH.exists():
        app.DB_FILE_PATH.unlink()

    coords = ["user1", "2025-01-01", "orders"]

    # Any endpoint that requires a DB should return 400 until /init is called
    resp_set = client.post("/item", json={"coords": coords, "value": 1})
    assert resp_set.status_code == 400
    assert "Database is not initialized" in resp_set.json()["detail"]

    resp_get = client.get("/item", params=[("coords", c) for c in coords])
    assert resp_get.status_code == 400

    resp_del = client.request("DELETE", "/item", json={"coords": coords})
    assert resp_del.status_code == 400

    resp_slice = client.post("/slice", json={"prefix": ["user1"]})
    assert resp_slice.status_code == 400


def test_item_endpoint_errors_for_invalid_coords_length_or_missing_keys(client):
    client.post("/init", json={"dimensions": 3})

    # Wrong number of coordinates for GET
    resp = client.get("/item", params=[("coords", "only_two"), ("coords", "values")])
    assert resp.status_code == 400
    assert "Expected 3 coordinates" in resp.json()["detail"]

    # Set a valid item
    coords = ["a", "b", "c"]
    client.post("/item", json={"coords": coords, "value": 1})

    # Missing intermediate key
    resp_missing = client.get(
        "/item",
        params=[("coords", "missing"), ("coords", "b"), ("coords", "c")],
    )
    assert resp_missing.status_code == 404

    # Missing leaf key
    resp_missing_leaf = client.get(
        "/item",
        params=[("coords", "a"), ("coords", "b"), ("coords", "missing")],
    )
    assert resp_missing_leaf.status_code == 404


def test_slice_endpoint_errors_for_invalid_prefix_or_missing_path(client):
    client.post("/init", json={"dimensions": 2})
    # Set a value
    client.post("/item", json={"coords": ["x", "y"], "value": 1})

    # Prefix longer than dimensions
    resp_long = client.post("/slice", json={"prefix": ["a", "b", "c"]})
    assert resp_long.status_code == 400
    assert "Prefix longer than number of dimensions" in resp_long.json()["detail"]

    # Missing prefix path
    resp_missing = client.post("/slice", json={"prefix": ["missing"]})
    assert resp_missing.status_code == 404


def test_root_endpoint_returns_message(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Multidimensional JSON DB API" in response.json()["message"]
