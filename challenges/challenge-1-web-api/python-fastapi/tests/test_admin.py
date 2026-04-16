"""
Integration tests for the admin router:
  GET   /admin/tasks               (admin only — all tasks across all users)
  GET   /admin/users               (admin only — all registered users)
  PATCH /admin/users/{id}/role     (admin only — change a user's role)
"""

import pytest

from tests.conftest import TASK_PAYLOAD

pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_task(client, headers, title: str = "Admin test task") -> dict:
    resp = await client.post("/tasks", json={**TASK_PAYLOAD, "title": title}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# GET /admin/tasks
# ---------------------------------------------------------------------------

class TestAdminListTasks:
    async def test_admin_list_tasks_returns_200(self, client, admin_headers):
        """Admin can access the global task list and receives a paginated response."""
        resp = await client.get("/admin/tasks", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "tasks" in data
        assert "total" in data
        assert "pages" in data

    async def test_admin_list_tasks_sees_all_users_tasks(
        self, client, user_headers, admin_headers, make_user
    ):
        """Admin task list includes tasks from all users, not just their own."""
        await _create_task(client, user_headers, "User task")
        other = make_user("admin_other@test.com", role="user")
        await _create_task(client, {"Authorization": f"Bearer {other['token']}"}, "Other task")

        resp = await client.get("/admin/tasks", headers=admin_headers)
        assert resp.json()["total"] == 2

    async def test_admin_list_tasks_user_returns_403(self, client, user_headers):
        """Regular user cannot access the admin task list."""
        resp = await client.get("/admin/tasks", headers=user_headers)
        assert resp.status_code == 403

    async def test_admin_list_tasks_viewer_returns_403(self, client, viewer_headers):
        """Viewer cannot access the admin task list."""
        resp = await client.get("/admin/tasks", headers=viewer_headers)
        assert resp.status_code == 403

    async def test_admin_list_tasks_no_auth_returns_403(self, client):
        """Unauthenticated request returns 403."""
        resp = await client.get("/admin/tasks")
        assert resp.status_code == 403

    async def test_admin_list_tasks_filter_by_status(self, client, user_headers, admin_headers):
        """Status filter works on the admin task list."""
        await _create_task(client, user_headers, "Reported task")
        resp = await client.get("/admin/tasks?status=reported", headers=admin_headers)
        data = resp.json()
        assert data["total"] >= 1
        assert all(t["status"] == "reported" for t in data["tasks"])

    async def test_admin_list_tasks_filter_by_user_id(
        self, client, regular_user, user_headers, admin_headers, make_user
    ):
        """user_id filter returns only tasks belonging to that user."""
        await _create_task(client, user_headers, "User task")
        other = make_user("user_filter@test.com", role="user")
        await _create_task(client, {"Authorization": f"Bearer {other['token']}"}, "Other task")

        resp = await client.get(
            f"/admin/tasks?user_id={regular_user['id']}", headers=admin_headers
        )
        data = resp.json()
        assert data["total"] == 1
        assert data["tasks"][0]["user_id"] == regular_user["id"]

    async def test_admin_list_tasks_pagination(self, client, user_headers, admin_headers):
        """Pagination parameters work on the admin task list."""
        for i in range(5):
            await _create_task(client, user_headers, f"Task {i}")

        resp = await client.get("/admin/tasks?page=1&limit=2", headers=admin_headers)
        data = resp.json()
        assert len(data["tasks"]) == 2
        assert data["total"] == 5
        assert data["pages"] == 3

    async def test_admin_list_tasks_limit_over_100_returns_422(self, client, admin_headers):
        """limit=101 is rejected with 422."""
        resp = await client.get("/admin/tasks?limit=101", headers=admin_headers)
        assert resp.status_code == 422

    async def test_admin_list_tasks_search_query(self, client, user_headers, admin_headers):
        """The q parameter searches title and description in the admin view."""
        await _create_task(client, user_headers, "Unique substation fault")
        await _create_task(client, user_headers, "Routine meter check")

        resp = await client.get("/admin/tasks?q=substation", headers=admin_headers)
        data = resp.json()
        assert data["total"] == 1
        assert "substation" in data["tasks"][0]["title"].lower()


# ---------------------------------------------------------------------------
# GET /admin/users
# ---------------------------------------------------------------------------

class TestAdminListUsers:
    async def test_admin_list_users_returns_200(self, client, admin_headers, admin_user):
        """Admin receives a list of all registered users."""
        resp = await client.get("/admin/users", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1  # at least the admin_user fixture

    async def test_admin_list_users_includes_all_users(
        self, client, admin_headers, regular_user, viewer_user
    ):
        """All created users appear in the admin user list."""
        resp = await client.get("/admin/users", headers=admin_headers)
        emails = [u["email"] for u in resp.json()]
        assert regular_user["email"] in emails
        assert viewer_user["email"] in emails

    async def test_admin_list_users_user_returns_403(self, client, user_headers):
        """Regular user cannot access the admin user list."""
        resp = await client.get("/admin/users", headers=user_headers)
        assert resp.status_code == 403

    async def test_admin_list_users_viewer_returns_403(self, client, viewer_headers):
        """Viewer cannot access the admin user list."""
        resp = await client.get("/admin/users", headers=viewer_headers)
        assert resp.status_code == 403

    async def test_admin_list_users_no_auth_returns_403(self, client):
        """Unauthenticated request returns 403."""
        resp = await client.get("/admin/users")
        assert resp.status_code == 403

    async def test_admin_list_users_does_not_expose_passwords(
        self, client, admin_headers, regular_user
    ):
        """User objects in the response must not include password fields."""
        resp = await client.get("/admin/users", headers=admin_headers)
        for user in resp.json():
            assert "hashed_password" not in user
            assert "password" not in user


# ---------------------------------------------------------------------------
# PATCH /admin/users/{id}/role
# ---------------------------------------------------------------------------

class TestAdminUpdateUserRole:
    async def test_admin_can_promote_user_to_admin(
        self, client, admin_headers, regular_user
    ):
        """Admin can change a user's role to admin."""
        resp = await client.patch(
            f"/admin/users/{regular_user['id']}/role",
            json={"role": "admin"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    async def test_admin_can_demote_user_to_viewer(
        self, client, admin_headers, regular_user
    ):
        """Admin can demote a user to the viewer role."""
        resp = await client.patch(
            f"/admin/users/{regular_user['id']}/role",
            json={"role": "viewer"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "viewer"

    async def test_admin_cannot_change_own_role(self, client, admin_headers, admin_user):
        """An admin cannot demote or change their own role (guard against lockout)."""
        resp = await client.patch(
            f"/admin/users/{admin_user['id']}/role",
            json={"role": "viewer"},
            headers=admin_headers,
        )
        assert resp.status_code == 400

    async def test_admin_update_role_user_not_found_returns_404(
        self, client, admin_headers
    ):
        """Updating the role of a non-existent user returns 404."""
        resp = await client.patch(
            "/admin/users/99999/role",
            json={"role": "user"},
            headers=admin_headers,
        )
        assert resp.status_code == 404

    async def test_admin_update_role_invalid_role_returns_422(
        self, client, admin_headers, regular_user
    ):
        """An unrecognised role value returns 422."""
        resp = await client.patch(
            f"/admin/users/{regular_user['id']}/role",
            json={"role": "superuser"},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    async def test_admin_update_role_user_returns_403(
        self, client, user_headers, regular_user
    ):
        """Regular user cannot change roles."""
        resp = await client.patch(
            f"/admin/users/{regular_user['id']}/role",
            json={"role": "admin"},
            headers=user_headers,
        )
        assert resp.status_code == 403

    async def test_admin_update_role_no_auth_returns_403(
        self, client, regular_user
    ):
        """Unauthenticated request returns 403."""
        resp = await client.patch(
            f"/admin/users/{regular_user['id']}/role",
            json={"role": "admin"},
        )
        assert resp.status_code == 403

    async def test_role_change_takes_effect_immediately(
        self, client, admin_headers, regular_user, user_headers
    ):
        """After being promoted to admin, the user's refreshed token grants admin access."""
        # Promote regular_user to admin
        await client.patch(
            f"/admin/users/{regular_user['id']}/role",
            json={"role": "admin"},
            headers=admin_headers,
        )
        # Refresh their token — the new token should have the admin role
        refresh_resp = await client.post("/auth/refresh", headers=user_headers)
        assert refresh_resp.status_code == 200
        new_token = refresh_resp.json()["access_token"]
        new_headers = {"Authorization": f"Bearer {new_token}"}

        # The refreshed token now lets them access admin endpoints
        admin_resp = await client.get("/admin/users", headers=new_headers)
        assert admin_resp.status_code == 200
