"""
Integration tests for the comments router:
  POST   /tasks/{task_id}/comments
  GET    /tasks/{task_id}/comments
  DELETE /tasks/{task_id}/comments/{comment_id}
"""

import pytest

from tests.conftest import TASK_PAYLOAD

pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_task(client, headers) -> dict:
    resp = await client.post("/tasks", json=TASK_PAYLOAD, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _add_comment(client, task_id: int, headers, body: str = "Test comment") -> dict:
    resp = await client.post(
        f"/tasks/{task_id}/comments",
        json={"body": body},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# POST /tasks/{task_id}/comments
# ---------------------------------------------------------------------------

class TestAddComment:
    async def test_add_comment_as_user_returns_201(self, client, user_headers, regular_user):
        """User can post a comment and receives 201 with comment data."""
        task = await _create_task(client, user_headers)
        resp = await client.post(
            f"/tasks/{task['id']}/comments",
            json={"body": "First comment!"},
            headers=user_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["body"] == "First comment!"
        assert data["task_id"] == task["id"]
        assert data["author"] == regular_user["email"]
        assert isinstance(data["id"], int)
        assert "created_at" in data

    async def test_add_comment_as_admin_returns_201(self, client, user_headers, admin_headers):
        """Admin can add a comment to any task."""
        task = await _create_task(client, user_headers)
        resp = await client.post(
            f"/tasks/{task['id']}/comments",
            json={"body": "Admin comment"},
            headers=admin_headers,
        )
        assert resp.status_code == 201

    async def test_add_comment_task_not_found_returns_404(self, client, user_headers):
        """Posting a comment to a non-existent task returns 404."""
        resp = await client.post(
            "/tasks/99999/comments",
            json={"body": "Orphan comment"},
            headers=user_headers,
        )
        assert resp.status_code == 404

    async def test_add_comment_viewer_returns_403(self, client, user_headers, viewer_headers):
        """Viewer role cannot post comments (write operation)."""
        task = await _create_task(client, user_headers)
        resp = await client.post(
            f"/tasks/{task['id']}/comments",
            json={"body": "Viewer sneak"},
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    async def test_add_comment_no_auth_returns_403(self, client, user_headers):
        """Missing Authorization header returns 403."""
        task = await _create_task(client, user_headers)
        resp = await client.post(
            f"/tasks/{task['id']}/comments",
            json={"body": "Anonymous"},
        )
        assert resp.status_code == 403

    async def test_add_comment_empty_body_returns_422(self, client, user_headers):
        """Comment body must be at least 1 character; empty string returns 422."""
        task = await _create_task(client, user_headers)
        resp = await client.post(
            f"/tasks/{task['id']}/comments",
            json={"body": ""},
            headers=user_headers,
        )
        assert resp.status_code == 422

    async def test_add_comment_body_too_long_returns_422(self, client, user_headers):
        """Comment body exceeding 2000 characters returns 422."""
        task = await _create_task(client, user_headers)
        resp = await client.post(
            f"/tasks/{task['id']}/comments",
            json={"body": "x" * 2001},
            headers=user_headers,
        )
        assert resp.status_code == 422

    async def test_add_comment_missing_body_returns_422(self, client, user_headers):
        """Omitting the body field returns 422."""
        task = await _create_task(client, user_headers)
        resp = await client.post(
            f"/tasks/{task['id']}/comments",
            json={},
            headers=user_headers,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /tasks/{task_id}/comments
# ---------------------------------------------------------------------------

class TestListComments:
    async def test_list_comments_returns_200_with_list(self, client, user_headers):
        """Listing comments for a task returns 200 and a list."""
        task = await _create_task(client, user_headers)
        resp = await client.get(f"/tasks/{task['id']}/comments", headers=user_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_comments_returns_posted_comments(self, client, user_headers):
        """Comments posted to a task appear in the list."""
        task = await _create_task(client, user_headers)
        await _add_comment(client, task["id"], user_headers, "Alpha")
        await _add_comment(client, task["id"], user_headers, "Beta")

        resp = await client.get(f"/tasks/{task['id']}/comments", headers=user_headers)
        bodies = [c["body"] for c in resp.json()]
        assert "Alpha" in bodies
        assert "Beta" in bodies
        assert len(bodies) == 2

    async def test_list_comments_viewer_can_read(self, client, user_headers, viewer_headers):
        """Viewer can list comments (read-only access is allowed)."""
        task = await _create_task(client, user_headers)
        await _add_comment(client, task["id"], user_headers)
        resp = await client.get(f"/tasks/{task['id']}/comments", headers=viewer_headers)
        assert resp.status_code == 200

    async def test_list_comments_task_not_found_returns_404(self, client, user_headers):
        """Listing comments for a non-existent task returns 404."""
        resp = await client.get("/tasks/99999/comments", headers=user_headers)
        assert resp.status_code == 404

    async def test_list_comments_no_auth_returns_403(self, client, user_headers):
        """Missing Authorization header returns 403."""
        task = await _create_task(client, user_headers)
        resp = await client.get(f"/tasks/{task['id']}/comments")
        assert resp.status_code == 403

    async def test_list_comments_ordered_oldest_first(self, client, user_headers):
        """Comments are returned oldest-first."""
        task = await _create_task(client, user_headers)
        c1 = await _add_comment(client, task["id"], user_headers, "First")
        c2 = await _add_comment(client, task["id"], user_headers, "Second")

        resp = await client.get(f"/tasks/{task['id']}/comments", headers=user_headers)
        comments = resp.json()
        assert comments[0]["id"] == c1["id"]
        assert comments[1]["id"] == c2["id"]


# ---------------------------------------------------------------------------
# DELETE /tasks/{task_id}/comments/{comment_id}
# ---------------------------------------------------------------------------

class TestDeleteComment:
    async def test_delete_own_comment_returns_204(self, client, user_headers):
        """Comment author can delete their own comment, receiving 204."""
        task = await _create_task(client, user_headers)
        comment = await _add_comment(client, task["id"], user_headers)
        resp = await client.delete(
            f"/tasks/{task['id']}/comments/{comment['id']}",
            headers=user_headers,
        )
        assert resp.status_code == 204

    async def test_delete_comment_is_gone_after_delete(self, client, user_headers):
        """Deleted comment no longer appears in the comment list."""
        task = await _create_task(client, user_headers)
        comment = await _add_comment(client, task["id"], user_headers)
        await client.delete(
            f"/tasks/{task['id']}/comments/{comment['id']}",
            headers=user_headers,
        )
        resp = await client.get(f"/tasks/{task['id']}/comments", headers=user_headers)
        ids = [c["id"] for c in resp.json()]
        assert comment["id"] not in ids

    async def test_delete_others_comment_returns_403(
        self, client, user_headers, make_user
    ):
        """A user cannot delete a comment they did not write."""
        task = await _create_task(client, user_headers)
        comment = await _add_comment(client, task["id"], user_headers)

        other = make_user("comment_other@test.com", role="user")
        resp = await client.delete(
            f"/tasks/{task['id']}/comments/{comment['id']}",
            headers={"Authorization": f"Bearer {other['token']}"},
        )
        assert resp.status_code == 403

    async def test_delete_comment_admin_can_delete_any(
        self, client, user_headers, admin_headers
    ):
        """Admin can delete any comment regardless of authorship."""
        task = await _create_task(client, user_headers)
        comment = await _add_comment(client, task["id"], user_headers)
        resp = await client.delete(
            f"/tasks/{task['id']}/comments/{comment['id']}",
            headers=admin_headers,
        )
        assert resp.status_code == 204

    async def test_delete_comment_not_found_returns_404(self, client, user_headers):
        """Deleting a non-existent comment returns 404."""
        task = await _create_task(client, user_headers)
        resp = await client.delete(
            f"/tasks/{task['id']}/comments/99999",
            headers=user_headers,
        )
        assert resp.status_code == 404

    async def test_delete_comment_viewer_returns_403(
        self, client, user_headers, viewer_headers
    ):
        """Viewer cannot delete comments (write operation)."""
        task = await _create_task(client, user_headers)
        comment = await _add_comment(client, task["id"], user_headers)
        resp = await client.delete(
            f"/tasks/{task['id']}/comments/{comment['id']}",
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    async def test_delete_comment_no_auth_returns_403(self, client, user_headers):
        """Missing Authorization header returns 403."""
        task = await _create_task(client, user_headers)
        comment = await _add_comment(client, task["id"], user_headers)
        resp = await client.delete(f"/tasks/{task['id']}/comments/{comment['id']}")
        assert resp.status_code == 403
