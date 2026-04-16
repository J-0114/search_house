"""
Integration tests for POST /auth/register, POST /auth/login, POST /auth/refresh.
"""

import pytest

pytestmark = pytest.mark.anyio


class TestRegister:
    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    async def test_register_returns_201_with_user_data(self, client):
        """New user with valid email + password returns 201 and user payload."""
        resp = await client.post(
            "/auth/register",
            json={"email": "alice@test.com", "password": "securepass"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "alice@test.com"
        assert data["role"] == "viewer"
        assert isinstance(data["id"], int)
        assert "hashed_password" not in data
        assert "password" not in data

    async def test_register_role_defaults_to_viewer(self, client):
        """Newly registered users always get the viewer role."""
        resp = await client.post(
            "/auth/register",
            json={"email": "bob@test.com", "password": "password123"},
        )
        assert resp.status_code == 201
        assert resp.json()["role"] == "viewer"

    # ------------------------------------------------------------------
    # Conflict
    # ------------------------------------------------------------------

    async def test_register_duplicate_email_returns_409(self, client):
        """Registering the same email twice returns 409 Conflict."""
        payload = {"email": "dup@test.com", "password": "password123"}
        await client.post("/auth/register", json=payload)
        resp = await client.post("/auth/register", json=payload)
        assert resp.status_code == 409

    # ------------------------------------------------------------------
    # Validation errors
    # ------------------------------------------------------------------

    async def test_register_invalid_email_returns_422(self, client):
        """A non-email string in the email field returns 422."""
        resp = await client.post(
            "/auth/register",
            json={"email": "not-an-email", "password": "password123"},
        )
        assert resp.status_code == 422

    async def test_register_password_too_short_returns_422(self, client):
        """Password shorter than 8 characters returns 422."""
        resp = await client.post(
            "/auth/register",
            json={"email": "short@test.com", "password": "abc"},
        )
        assert resp.status_code == 422

    async def test_register_password_too_long_returns_422(self, client):
        """Password longer than 128 characters returns 422."""
        resp = await client.post(
            "/auth/register",
            json={"email": "long@test.com", "password": "x" * 129},
        )
        assert resp.status_code == 422

    async def test_register_missing_email_returns_422(self, client):
        """Omitting the email field returns 422."""
        resp = await client.post("/auth/register", json={"password": "password123"})
        assert resp.status_code == 422

    async def test_register_missing_password_returns_422(self, client):
        """Omitting the password field returns 422."""
        resp = await client.post("/auth/register", json={"email": "nopass@test.com"})
        assert resp.status_code == 422

    async def test_register_empty_body_returns_422(self, client):
        """Empty JSON body returns 422."""
        resp = await client.post("/auth/register", json={})
        assert resp.status_code == 422


class TestLogin:
    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    async def test_login_returns_200_with_token(self, client):
        """Correct credentials return 200 and a bearer token."""
        await client.post(
            "/auth/register",
            json={"email": "login@test.com", "password": "password123"},
        )
        resp = await client.post(
            "/auth/login",
            json={"email": "login@test.com", "password": "password123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0

    # ------------------------------------------------------------------
    # Auth failures
    # ------------------------------------------------------------------

    async def test_login_wrong_password_returns_401(self, client):
        """Valid email but wrong password returns 401."""
        await client.post(
            "/auth/register",
            json={"email": "wrongpw@test.com", "password": "password123"},
        )
        resp = await client.post(
            "/auth/login",
            json={"email": "wrongpw@test.com", "password": "badpassword"},
        )
        assert resp.status_code == 401

    async def test_login_unknown_email_returns_401(self, client):
        """Email that was never registered returns 401."""
        resp = await client.post(
            "/auth/login",
            json={"email": "ghost@test.com", "password": "password123"},
        )
        assert resp.status_code == 401

    # ------------------------------------------------------------------
    # Validation errors
    # ------------------------------------------------------------------

    async def test_login_missing_fields_returns_422(self, client):
        """Completely empty body returns 422."""
        resp = await client.post("/auth/login", json={})
        assert resp.status_code == 422

    async def test_login_invalid_email_returns_422(self, client):
        """Non-email string in email field returns 422."""
        resp = await client.post(
            "/auth/login",
            json={"email": "notanemail", "password": "password123"},
        )
        assert resp.status_code == 422


class TestRefresh:
    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    async def test_refresh_returns_new_token(self, client, user_headers):
        """Valid token produces a fresh access token."""
        resp = await client.post("/auth/refresh", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_refresh_admin_token_preserves_role(self, client, admin_headers):
        """Refreshing an admin token returns a token that still grants admin access."""
        resp = await client.post("/auth/refresh", headers=admin_headers)
        assert resp.status_code == 200
        # The refreshed token should still allow admin-only routes
        refreshed_headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
        admin_resp = await client.get("/admin/users", headers=refreshed_headers)
        assert admin_resp.status_code == 200

    # ------------------------------------------------------------------
    # Auth failures
    # ------------------------------------------------------------------

    async def test_refresh_invalid_token_returns_401(self, client):
        """A garbage token string returns 401."""
        resp = await client.post(
            "/auth/refresh",
            headers={"Authorization": "Bearer this.is.garbage"},
        )
        assert resp.status_code == 401

    async def test_refresh_no_auth_header_returns_403(self, client):
        """Missing Authorization header returns 403 (HTTPBearer scheme required)."""
        resp = await client.post("/auth/refresh")
        assert resp.status_code == 403
