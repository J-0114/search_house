"""
Integration tests for the tasks router:
  POST   /tasks
  GET    /tasks
  GET    /tasks/{id}
  PUT    /tasks/{id}
  PATCH  /tasks/{id}
  PATCH  /tasks/{id}/complete
  DELETE /tasks/{id}
"""

import pytest

from tests.conftest import TASK_PAYLOAD

pytestmark = pytest.mark.anyio

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

async def _create_task(client, headers, payload=None) -> dict:
    """POST /tasks and return the response JSON (asserts 201)."""
    resp = await client.post("/tasks", json=payload or TASK_PAYLOAD, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# POST /tasks
# ---------------------------------------------------------------------------

class TestCreateTask:
    async def test_create_task_as_user_returns_201(self, client, user_headers):
        """User with 'user' role can create a task and receives 201."""
        resp = await client.post("/tasks", json=TASK_PAYLOAD, headers=user_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == TASK_PAYLOAD["title"]
        assert data["status"] == "reported"
        assert data["priority"] == "medium"
        assert isinstance(data["id"], int)
        assert "created_at" in data

    async def test_create_task_as_admin_returns_201(self, client, admin_headers):
        """Admin can create a task."""
        resp = await client.post("/tasks", json=TASK_PAYLOAD, headers=admin_headers)
        assert resp.status_code == 201

    async def test_create_task_no_auth_returns_403(self, client):
        """Request without Authorization header returns 403."""
        resp = await client.post("/tasks", json=TASK_PAYLOAD)
        assert resp.status_code == 403

    async def test_create_task_viewer_returns_403(self, client, viewer_headers):
        """Viewer role is blocked from creating tasks (write is forbidden)."""
        resp = await client.post("/tasks", json=TASK_PAYLOAD, headers=viewer_headers)
        assert resp.status_code == 403

    async def test_create_task_title_too_short_returns_422(self, client, user_headers):
        """Title shorter than 3 characters fails validation."""
        resp = await client.post(
            "/tasks",
            json={**TASK_PAYLOAD, "title": "ab"},
            headers=user_headers,
        )
        assert resp.status_code == 422

    async def test_create_task_title_too_long_returns_422(self, client, user_headers):
        """Title longer than 100 characters fails validation."""
        resp = await client.post(
            "/tasks",
            json={**TASK_PAYLOAD, "title": "x" * 101},
            headers=user_headers,
        )
        assert resp.status_code == 422

    async def test_create_task_missing_title_returns_422(self, client, user_headers):
        """Omitting the required title field returns 422."""
        payload = {k: v for k, v in TASK_PAYLOAD.items() if k != "title"}
        resp = await client.post("/tasks", json=payload, headers=user_headers)
        assert resp.status_code == 422

    async def test_create_task_invalid_status_returns_422(self, client, user_headers):
        """An unknown status enum value returns 422."""
        resp = await client.post(
            "/tasks",
            json={**TASK_PAYLOAD, "status": "nonexistent"},
            headers=user_headers,
        )
        assert resp.status_code == 422

    async def test_create_task_description_too_long_returns_422(self, client, user_headers):
        """Description exceeding 500 characters returns 422."""
        resp = await client.post(
            "/tasks",
            json={**TASK_PAYLOAD, "description": "d" * 501},
            headers=user_headers,
        )
        assert resp.status_code == 422

    async def test_create_task_owner_matches_token(self, client, regular_user, user_headers):
        """Created task's user_id matches the authenticated user's id."""
        resp = await client.post("/tasks", json=TASK_PAYLOAD, headers=user_headers)
        assert resp.json()["user_id"] == regular_user["id"]


# ---------------------------------------------------------------------------
# GET /tasks
# ---------------------------------------------------------------------------

class TestListTasks:
    async def test_list_tasks_returns_200_for_user(self, client, user_headers):
        """Authenticated user receives the paginated task list."""
        resp = await client.get("/tasks", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "tasks" in data
        assert "total" in data
        assert "page" in data
        assert "pages" in data

    async def test_list_tasks_returns_200_for_viewer(self, client, viewer_headers):
        """Viewers (read-only role) can still list tasks."""
        resp = await client.get("/tasks", headers=viewer_headers)
        assert resp.status_code == 200

    async def test_list_tasks_no_auth_returns_403(self, client):
        """No auth header → 403 from HTTPBearer."""
        resp = await client.get("/tasks")
        assert resp.status_code == 403

    async def test_list_tasks_shows_created_task(self, client, user_headers):
        """A task just created appears in the list."""
        await _create_task(client, user_headers)
        resp = await client.get("/tasks", headers=user_headers)
        data = resp.json()
        assert data["total"] == 1
        assert data["tasks"][0]["title"] == TASK_PAYLOAD["title"]

    async def test_list_tasks_filter_by_status(self, client, user_headers):
        """Status filter returns only tasks with the matching status."""
        await _create_task(client, user_headers, {**TASK_PAYLOAD, "status": "reported"})
        await _create_task(client, user_headers, {**TASK_PAYLOAD, "title": "Another task", "status": "closed"})

        resp = await client.get("/tasks?status=reported", headers=user_headers)
        data = resp.json()
        assert data["total"] == 1
        assert data["tasks"][0]["status"] == "reported"

    async def test_list_tasks_filter_by_priority(self, client, user_headers):
        """Priority filter returns only tasks with the matching priority."""
        await _create_task(client, user_headers, {**TASK_PAYLOAD, "priority": "critical"})
        await _create_task(client, user_headers, {**TASK_PAYLOAD, "title": "Low task", "priority": "low"})

        resp = await client.get("/tasks?priority=critical", headers=user_headers)
        data = resp.json()
        assert data["total"] == 1
        assert data["tasks"][0]["priority"] == "critical"

    async def test_list_tasks_search_by_title(self, client, user_headers):
        """The q query parameter searches within title and description."""
        await _create_task(client, user_headers, {**TASK_PAYLOAD, "title": "Solar panel install Lisboa"})
        await _create_task(client, user_headers, {**TASK_PAYLOAD, "title": "Grid fault Setúbal"})

        resp = await client.get("/tasks?q=Solar", headers=user_headers)
        data = resp.json()
        assert data["total"] == 1
        assert "Solar" in data["tasks"][0]["title"]

    async def test_list_tasks_pagination_limit_1(self, client, user_headers):
        """limit=1 returns exactly one task per page."""
        for i in range(3):
            await _create_task(client, user_headers, {**TASK_PAYLOAD, "title": f"Task {i}"})

        resp = await client.get("/tasks?page=1&limit=1", headers=user_headers)
        data = resp.json()
        assert len(data["tasks"]) == 1
        assert data["total"] == 3
        assert data["pages"] == 3

    async def test_list_tasks_pagination_second_page(self, client, user_headers):
        """page=2 with limit=1 returns the second task."""
        for i in range(3):
            await _create_task(client, user_headers, {**TASK_PAYLOAD, "title": f"Task {i}"})

        p1 = (await client.get("/tasks?page=1&limit=1", headers=user_headers)).json()
        p2 = (await client.get("/tasks?page=2&limit=1", headers=user_headers)).json()
        assert p1["tasks"][0]["id"] != p2["tasks"][0]["id"]

    async def test_list_tasks_page_beyond_range_returns_empty(self, client, user_headers):
        """A page number far beyond existing data returns an empty tasks list."""
        await _create_task(client, user_headers)
        resp = await client.get("/tasks?page=999&limit=20", headers=user_headers)
        data = resp.json()
        assert data["tasks"] == []
        assert data["total"] == 1

    async def test_list_tasks_limit_max_100(self, client, user_headers):
        """limit=100 (boundary maximum) is accepted."""
        resp = await client.get("/tasks?limit=100", headers=user_headers)
        assert resp.status_code == 200

    async def test_list_tasks_limit_over_100_returns_422(self, client, user_headers):
        """limit=101 exceeds the maximum and returns 422."""
        resp = await client.get("/tasks?limit=101", headers=user_headers)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /tasks/{id}
# ---------------------------------------------------------------------------

class TestGetTask:
    async def test_get_task_returns_task_data(self, client, user_headers):
        """Existing task id returns 200 and the full task object."""
        task = await _create_task(client, user_headers)
        resp = await client.get(f"/tasks/{task['id']}", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == task["id"]
        assert data["title"] == task["title"]

    async def test_get_task_viewer_can_read(self, client, user_headers, viewer_headers):
        """Viewer role is allowed to read a single task."""
        task = await _create_task(client, user_headers)
        resp = await client.get(f"/tasks/{task['id']}", headers=viewer_headers)
        assert resp.status_code == 200

    async def test_get_task_not_found_returns_404(self, client, user_headers):
        """Non-existent task id returns 404."""
        resp = await client.get("/tasks/99999", headers=user_headers)
        assert resp.status_code == 404

    async def test_get_task_no_auth_returns_403(self, client, user_headers):
        """Missing Authorization header returns 403."""
        task = await _create_task(client, user_headers)
        resp = await client.get(f"/tasks/{task['id']}")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PUT /tasks/{id}
# ---------------------------------------------------------------------------

class TestUpdateTask:
    async def test_update_task_by_owner_returns_200(self, client, user_headers):
        """Owner can fully replace a task's fields."""
        task = await _create_task(client, user_headers)
        updated = {**TASK_PAYLOAD, "title": "Updated title", "priority": "high"}
        resp = await client.put(f"/tasks/{task['id']}", json=updated, headers=user_headers)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated title"
        assert resp.json()["priority"] == "high"

    async def test_update_task_by_admin_on_any_task(self, client, user_headers, admin_headers):
        """Admin can update a task owned by a different user."""
        task = await _create_task(client, user_headers)
        updated = {**TASK_PAYLOAD, "title": "Admin override"}
        resp = await client.put(f"/tasks/{task['id']}", json=updated, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Admin override"

    async def test_update_task_not_owner_returns_403(self, client, user_headers, make_user):
        """A different non-admin user cannot update another user's task."""
        task = await _create_task(client, user_headers)
        other = make_user("other@test.com", role="user")
        other_headers = {"Authorization": f"Bearer {other['token']}"}
        resp = await client.put(
            f"/tasks/{task['id']}",
            json={**TASK_PAYLOAD, "title": "Stolen update"},
            headers=other_headers,
        )
        assert resp.status_code == 403

    async def test_update_task_not_found_returns_404(self, client, user_headers):
        """Updating a non-existent task returns 404."""
        resp = await client.put("/tasks/99999", json=TASK_PAYLOAD, headers=user_headers)
        assert resp.status_code == 404

    async def test_update_task_no_auth_returns_403(self, client, user_headers):
        """Missing auth header returns 403."""
        task = await _create_task(client, user_headers)
        resp = await client.put(f"/tasks/{task['id']}", json=TASK_PAYLOAD)
        assert resp.status_code == 403

    async def test_update_task_viewer_returns_403(self, client, user_headers, viewer_headers):
        """Viewer cannot perform a full update."""
        task = await _create_task(client, user_headers)
        resp = await client.put(f"/tasks/{task['id']}", json=TASK_PAYLOAD, headers=viewer_headers)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /tasks/{id}
# ---------------------------------------------------------------------------

class TestPartialUpdateTask:
    async def test_patch_task_single_field(self, client, user_headers):
        """Partial update of one field leaves the rest unchanged."""
        task = await _create_task(client, user_headers)
        resp = await client.patch(
            f"/tasks/{task['id']}",
            json={"priority": "critical"},
            headers=user_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["priority"] == "critical"
        assert data["title"] == TASK_PAYLOAD["title"]

    async def test_patch_task_multiple_fields(self, client, user_headers):
        """Multiple fields can be updated in a single PATCH."""
        task = await _create_task(client, user_headers)
        resp = await client.patch(
            f"/tasks/{task['id']}",
            json={"status": "assigned", "priority": "high"},
            headers=user_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "assigned"
        assert data["priority"] == "high"

    async def test_patch_task_not_owner_returns_403(self, client, user_headers, make_user):
        """Non-owner cannot partially update a task."""
        task = await _create_task(client, user_headers)
        other = make_user("other2@test.com", role="user")
        resp = await client.patch(
            f"/tasks/{task['id']}",
            json={"priority": "low"},
            headers={"Authorization": f"Bearer {other['token']}"},
        )
        assert resp.status_code == 403

    async def test_patch_task_not_found_returns_404(self, client, user_headers):
        """Patching a non-existent task returns 404."""
        resp = await client.patch(
            "/tasks/99999",
            json={"priority": "low"},
            headers=user_headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /tasks/{id}/complete
# ---------------------------------------------------------------------------

class TestCompleteTask:
    async def test_complete_task_sets_resolved(self, client, user_headers):
        """Completing a task sets its status to 'resolved'."""
        task = await _create_task(client, user_headers)
        resp = await client.patch(f"/tasks/{task['id']}/complete", headers=user_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"

    async def test_complete_task_not_owner_returns_403(self, client, user_headers, make_user):
        """A different user cannot complete another user's task."""
        task = await _create_task(client, user_headers)
        other = make_user("other3@test.com", role="user")
        resp = await client.patch(
            f"/tasks/{task['id']}/complete",
            headers={"Authorization": f"Bearer {other['token']}"},
        )
        assert resp.status_code == 403

    async def test_complete_task_not_found_returns_404(self, client, user_headers):
        """Completing a non-existent task returns 404."""
        resp = await client.patch("/tasks/99999/complete", headers=user_headers)
        assert resp.status_code == 404

    async def test_complete_task_admin_can_complete_any(self, client, user_headers, admin_headers):
        """Admin can mark any task as resolved regardless of ownership."""
        task = await _create_task(client, user_headers)
        resp = await client.patch(f"/tasks/{task['id']}/complete", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"


# ---------------------------------------------------------------------------
# DELETE /tasks/{id}
# ---------------------------------------------------------------------------

class TestDeleteTask:
    async def test_delete_task_by_owner_returns_204(self, client, user_headers):
        """Owner can delete their own task, receiving 204 No Content."""
        task = await _create_task(client, user_headers)
        resp = await client.delete(f"/tasks/{task['id']}", headers=user_headers)
        assert resp.status_code == 204

    async def test_delete_task_is_actually_gone(self, client, user_headers):
        """After deletion, GET on the same task returns 404."""
        task = await _create_task(client, user_headers)
        await client.delete(f"/tasks/{task['id']}", headers=user_headers)
        resp = await client.get(f"/tasks/{task['id']}", headers=user_headers)
        assert resp.status_code == 404

    async def test_delete_task_not_owner_returns_403(self, client, user_headers, make_user):
        """A non-owner user cannot delete another user's task."""
        task = await _create_task(client, user_headers)
        other = make_user("del_other@test.com", role="user")
        resp = await client.delete(
            f"/tasks/{task['id']}",
            headers={"Authorization": f"Bearer {other['token']}"},
        )
        assert resp.status_code == 403

    async def test_delete_task_admin_can_delete_any(self, client, user_headers, admin_headers):
        """Admin can delete a task owned by another user."""
        task = await _create_task(client, user_headers)
        resp = await client.delete(f"/tasks/{task['id']}", headers=admin_headers)
        assert resp.status_code == 204

    async def test_delete_task_not_found_returns_404(self, client, user_headers):
        """Deleting a non-existent task returns 404."""
        resp = await client.delete("/tasks/99999", headers=user_headers)
        assert resp.status_code == 404

    async def test_delete_task_no_auth_returns_403(self, client, user_headers):
        """Missing auth returns 403."""
        task = await _create_task(client, user_headers)
        resp = await client.delete(f"/tasks/{task['id']}")
        assert resp.status_code == 403
