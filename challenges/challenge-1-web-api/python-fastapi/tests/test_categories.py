"""
Integration tests for the categories router:
  POST /categories               (admin only)
  GET  /categories               (any authenticated user)
  POST /tasks/bulk/categorize    (user or admin; transactional)
"""

import pytest

from tests.conftest import TASK_PAYLOAD

pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_category(client, admin_headers, name: str = "Test Category") -> dict:
    resp = await client.post("/categories", json={"name": name}, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_task(client, headers, title: str = "Task") -> dict:
    resp = await client.post("/tasks", json={**TASK_PAYLOAD, "title": title}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# POST /categories
# ---------------------------------------------------------------------------

class TestCreateCategory:
    async def test_create_category_admin_returns_201(self, client, admin_headers):
        """Admin can create a category and receives 201 with category data."""
        resp = await client.post("/categories", json={"name": "Substation"}, headers=admin_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Substation"
        assert isinstance(data["id"], int)

    async def test_create_category_user_returns_403(self, client, user_headers):
        """Regular user (non-admin) cannot create a category."""
        resp = await client.post("/categories", json={"name": "ForbiddenCat"}, headers=user_headers)
        assert resp.status_code == 403

    async def test_create_category_viewer_returns_403(self, client, viewer_headers):
        """Viewer role cannot create a category."""
        resp = await client.post("/categories", json={"name": "ViewerCat"}, headers=viewer_headers)
        assert resp.status_code == 403

    async def test_create_category_no_auth_returns_403(self, client):
        """Missing Authorization header returns 403."""
        resp = await client.post("/categories", json={"name": "NoCat"})
        assert resp.status_code == 403

    async def test_create_category_duplicate_name_returns_409(self, client, admin_headers):
        """Creating two categories with the same name returns 409 on the second attempt."""
        await client.post("/categories", json={"name": "Duplicate"}, headers=admin_headers)
        resp = await client.post("/categories", json={"name": "Duplicate"}, headers=admin_headers)
        assert resp.status_code == 409

    async def test_create_category_empty_name_returns_422(self, client, admin_headers):
        """Category name must be at least 1 character; empty string returns 422."""
        resp = await client.post("/categories", json={"name": ""}, headers=admin_headers)
        assert resp.status_code == 422

    async def test_create_category_missing_name_returns_422(self, client, admin_headers):
        """Omitting the name field returns 422."""
        resp = await client.post("/categories", json={}, headers=admin_headers)
        assert resp.status_code == 422

    async def test_create_category_name_too_long_returns_422(self, client, admin_headers):
        """Category name exceeding 100 characters returns 422."""
        resp = await client.post("/categories", json={"name": "x" * 101}, headers=admin_headers)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /categories
# ---------------------------------------------------------------------------

class TestListCategories:
    async def test_list_categories_returns_200_for_user(self, client, user_headers):
        """Authenticated user receives a list (possibly empty)."""
        resp = await client.get("/categories", headers=user_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_categories_returns_200_for_viewer(self, client, viewer_headers):
        """Viewer can also list categories."""
        resp = await client.get("/categories", headers=viewer_headers)
        assert resp.status_code == 200

    async def test_list_categories_returns_200_for_admin(self, client, admin_headers):
        """Admin can list categories."""
        resp = await client.get("/categories", headers=admin_headers)
        assert resp.status_code == 200

    async def test_list_categories_no_auth_returns_403(self, client):
        """Unauthenticated request returns 403."""
        resp = await client.get("/categories")
        assert resp.status_code == 403

    async def test_list_categories_shows_created_category(self, client, admin_headers):
        """A newly created category appears in the list."""
        await _create_category(client, admin_headers, "NewLabel")
        resp = await client.get("/categories", headers=admin_headers)
        names = [c["name"] for c in resp.json()]
        assert "NewLabel" in names

    async def test_list_categories_sorted_by_name(self, client, admin_headers):
        """Categories are returned in alphabetical order."""
        await _create_category(client, admin_headers, "Zebra")
        await _create_category(client, admin_headers, "Alpha")
        resp = await client.get("/categories", headers=admin_headers)
        names = [c["name"] for c in resp.json()]
        assert names == sorted(names)


# ---------------------------------------------------------------------------
# POST /tasks/bulk/categorize
# ---------------------------------------------------------------------------

class TestBulkCategorize:
    async def test_bulk_categorize_assigns_category_to_tasks(
        self, client, user_headers, admin_headers
    ):
        """Assigning an existing category to multiple owned tasks returns 200."""
        t1 = await _create_task(client, user_headers, "Task A")
        t2 = await _create_task(client, user_headers, "Task B")
        cat = await _create_category(client, admin_headers, "Bulk Cat")

        resp = await client.post(
            "/tasks/bulk/categorize",
            json={"task_ids": [t1["id"], t2["id"]], "category_id": cat["id"]},
            headers=user_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"] == 2
        assert data["category"]["id"] == cat["id"]

    async def test_bulk_categorize_category_not_found_returns_404(
        self, client, user_headers
    ):
        """Non-existent category_id returns 404."""
        task = await _create_task(client, user_headers)
        resp = await client.post(
            "/tasks/bulk/categorize",
            json={"task_ids": [task["id"]], "category_id": 99999},
            headers=user_headers,
        )
        assert resp.status_code == 404

    async def test_bulk_categorize_task_not_found_rolls_back(
        self, client, user_headers, admin_headers
    ):
        """If any task_id is not found the whole operation rolls back with 404."""
        task = await _create_task(client, user_headers)
        cat = await _create_category(client, admin_headers, "Rollback Cat")

        resp = await client.post(
            "/tasks/bulk/categorize",
            json={"task_ids": [task["id"], 99999], "category_id": cat["id"]},
            headers=user_headers,
        )
        assert resp.status_code == 404

        # Confirm the valid task was NOT categorized (rollback occurred)
        get_resp = await client.get(f"/tasks/{task['id']}", headers=user_headers)
        assert get_resp.json()["categories"] == []

    async def test_bulk_categorize_not_owner_returns_403(
        self, client, user_headers, admin_headers, make_user
    ):
        """Cannot categorize a task owned by another user."""
        task = await _create_task(client, user_headers)
        cat = await _create_category(client, admin_headers, "OwnerCat")

        other = make_user("owner_other@test.com", role="user")
        resp = await client.post(
            "/tasks/bulk/categorize",
            json={"task_ids": [task["id"]], "category_id": cat["id"]},
            headers={"Authorization": f"Bearer {other['token']}"},
        )
        assert resp.status_code == 403

    async def test_bulk_categorize_viewer_returns_403(
        self, client, user_headers, admin_headers, viewer_headers
    ):
        """Viewer cannot use bulk categorize."""
        task = await _create_task(client, user_headers)
        cat = await _create_category(client, admin_headers, "ViewerAttempt")

        resp = await client.post(
            "/tasks/bulk/categorize",
            json={"task_ids": [task["id"]], "category_id": cat["id"]},
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    async def test_bulk_categorize_no_auth_returns_403(
        self, client, user_headers, admin_headers
    ):
        """Unauthenticated request returns 403."""
        task = await _create_task(client, user_headers)
        cat = await _create_category(client, admin_headers, "NoAuthCat")
        resp = await client.post(
            "/tasks/bulk/categorize",
            json={"task_ids": [task["id"]], "category_id": cat["id"]},
        )
        assert resp.status_code == 403

    async def test_bulk_categorize_empty_task_ids_returns_422(
        self, client, admin_headers, user_headers
    ):
        """task_ids list must have at least 1 element; empty list returns 422."""
        cat = await _create_category(client, admin_headers, "EmptyCat")
        resp = await client.post(
            "/tasks/bulk/categorize",
            json={"task_ids": [], "category_id": cat["id"]},
            headers=user_headers,
        )
        assert resp.status_code == 422

    async def test_bulk_categorize_admin_can_categorize_any_task(
        self, client, user_headers, admin_headers
    ):
        """Admin can assign categories to tasks they do not own."""
        task = await _create_task(client, user_headers)
        cat = await _create_category(client, admin_headers, "AdminCat")

        resp = await client.post(
            "/tasks/bulk/categorize",
            json={"task_ids": [task["id"]], "category_id": cat["id"]},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["updated"] == 1
