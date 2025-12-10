"""API tests for the FastAPI layer."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Generator, List

import pytest
from fastapi.testclient import TestClient

from app import DatabaseService, app, get_database_service

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)


@pytest.fixture
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """FastAPI TestClient wired up with a fresh DatabaseService."""
    db_path = tmp_path / "test_db.json"
    service = DatabaseService(db_path)

    app.dependency_overrides[get_database_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestInfoAndInitEndpoints:
    def test_info_before_initialization_shows_uninitialized(
        self,
        client: TestClient,
    ) -> None:
        response = client.get("/info")
        assert response.status_code == 200

        payload = response.json()
        assert payload == {"dimensions": None, "initialized": False}

    def test_init_endpoint_creates_db_file_and_returns_info(
        self,
        client: TestClient,
    ) -> None:
        response = client.post("/init", json={"dimensions": 3})
        assert response.status_code == 200

        data = response.json()
        assert data["message"] == "Database initialized"
        assert data["dimensions"] == 3

    def test_init_endpoint_rejects_invalid_dimensions(
        self,
        client: TestClient,
    ) -> None:
        for bad in (0, -1):
            response = client.post("/init", json={"dimensions": bad})
            assert response.status_code == 422  # pydantic validation


class TestItemCrudEndpoints:
    def test_item_crud_via_api(self, client: TestClient) -> None:
        init_resp = client.post("/init", json={"dimensions": 3})
        assert init_resp.status_code == 200

        coords: List[str] = ["user1", "2025-01-01", "orders"]
        value = {"id": 1, "total": 10.5}

        set_resp = client.post("/item", json={"coords": coords, "value": value})
        assert set_resp.status_code == 200
        assert set_resp.json() == {"coords": coords, "value": value}

        get_resp = client.get("/item", params=[("coords", c) for c in coords])
        assert get_resp.status_code == 200
        assert get_resp.json() == {"coords": coords, "value": value}

        slice_resp = client.post("/slice", json={"prefix": ["user1"]})
        assert slice_resp.status_code == 200
        body = slice_resp.json()
        assert body["prefix"] == ["user1"]
        assert "2025-01-01" in body["data"]

        delete_resp = client.request("DELETE", "/item", json={"coords": coords})
        assert delete_resp.status_code == 200
        assert delete_resp.json()["message"] == "Deleted"

        get_missing = client.get("/item", params=[("coords", c) for c in coords])
        assert get_missing.status_code == 404

    def test_endpoints_require_initialization(self, tmp_path: Path) -> None:
        """Endpoints should fail with a clear error before /init is called."""
        service = DatabaseService(tmp_path / "uninitialised.json")
        app.dependency_overrides[get_database_service] = lambda: service

        with TestClient(app) as bare_client:
            coords = ["user1", "2025-01-01", "orders"]

            resp_set = bare_client.post("/item", json={"coords": coords, "value": 1})
            assert resp_set.status_code == 400
            assert "Database is not initialized" in resp_set.json()["detail"]

            resp_get = bare_client.get(
                "/item",
                params=[("coords", c) for c in coords],
            )
            assert resp_get.status_code == 400

            resp_del = bare_client.request(
                "DELETE",
                "/item",
                json={"coords": coords},
            )
            assert resp_del.status_code == 400

            resp_slice = bare_client.post("/slice", json={"prefix": ["user1"]})
            assert resp_slice.status_code == 400

        app.dependency_overrides.clear()

    def test_item_endpoint_errors_for_invalid_coords_and_missing_keys(
        self,
        client: TestClient,
    ) -> None:
        client.post("/init", json={"dimensions": 3})

        resp = client.get(
            "/item",
            params=[("coords", "only_two"), ("coords", "values")],
        )
        assert resp.status_code == 400
        assert "Expected 3 coordinates" in resp.json()["detail"]

        coords = ["a", "b", "c"]
        client.post("/item", json={"coords": coords, "value": 1})

        resp_missing = client.get(
            "/item",
            params=[("coords", "missing"), ("coords", "b"), ("coords", "c")],
        )
        assert resp_missing.status_code == 404

        resp_missing_leaf = client.get(
            "/item",
            params=[("coords", "a"), ("coords", "b"), ("coords", "missing")],
        )
        assert resp_missing_leaf.status_code == 404

    def test_slice_endpoint_errors_for_invalid_prefix_or_missing_path(
        self,
        client: TestClient,
    ) -> None:
        client.post("/init", json={"dimensions": 2})
        client.post("/item", json={"coords": ["x", "y"], "value": 1})

        resp_long = client.post("/slice", json={"prefix": ["a", "b", "c"]})
        assert resp_long.status_code == 400
        assert "Prefix longer than number of dimensions" in resp_long.json()["detail"]

        resp_missing = client.post("/slice", json={"prefix": ["missing"]})
        assert resp_missing.status_code == 404


class TestRootEndpoint:
    def test_root_endpoint_returns_message(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert "Multidimensional JSON DB API" in response.json()["message"]
