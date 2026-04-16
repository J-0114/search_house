"""
Shared pytest configuration and fixtures for the Task Manager API test suite.

Setup strategy
--------------
1. JWT_SECRET and RATELIMIT_ENABLED are injected into os.environ *before* any
   app module is imported, because dependencies/auth.py reads JWT_SECRET at
   module-load time and raises RuntimeError if it is absent.

2. The `database` module is monkey-patched to use an in-memory SQLite engine
   before `main.py` (and its routers) is imported.  This means every call to
   `init_db()` and `get_db()` automatically targets the test database.

3. The `get_db` FastAPI dependency is overridden via `app.dependency_overrides`
   so route handlers receive sessions from the same test engine.

4. An `autouse` `reset_db` fixture drops and recreates all tables before every
   test function, guaranteeing full isolation between tests.

5. Helper fixtures (`regular_user`, `admin_user`, `viewer_user`) insert users
   directly into the DB and return pre-signed JWT tokens so tests do not need
   to exercise the /auth endpoints to set up state.
"""

import os

# Must be set BEFORE any app module is imported.
os.environ["JWT_SECRET"] = "TEST_SECRET"
os.environ["RATELIMIT_ENABLED"] = "0"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient, ASGITransport

# ---------------------------------------------------------------------------
# Patch database module before importing the app
# ---------------------------------------------------------------------------
import database as _db_module

_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
)
_TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)

_db_module.engine = _test_engine
_db_module.SessionLocal = _TestSessionLocal

# ---------------------------------------------------------------------------
# Import app *after* patching so all routers pick up the test engine
# ---------------------------------------------------------------------------
from main import app  # noqa: E402
from database import Base  # noqa: E402
from dependencies.db import get_db  # noqa: E402
from dependencies.auth import create_access_token, hash_password  # noqa: E402
from models.orm import User  # noqa: E402
import models.orm  # noqa: E402, F401 — registers all ORM models with Base

# Create tables once so the schema is ready for the first test
Base.metadata.create_all(bind=_test_engine)


# ---------------------------------------------------------------------------
# Dependency override
# ---------------------------------------------------------------------------

def _get_test_db():
    db = _TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _get_test_db

# ---------------------------------------------------------------------------
# Register anyio pytest plugin (provides @pytest.mark.anyio)
# ---------------------------------------------------------------------------
pytest_plugins = ("anyio",)


@pytest.fixture(scope="session")
def anyio_backend():
    """Use the asyncio backend for all async tests."""
    return "asyncio"


# ---------------------------------------------------------------------------
# DB isolation
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_db():
    """Drop and recreate every table before each test for full isolation."""
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)
    yield


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

@pytest.fixture
async def client():
    """Async HTTPX client connected to the FastAPI app (no lifespan triggered)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# User factory helpers
# ---------------------------------------------------------------------------

def _insert_user(email: str, role: str = "user", password: str = "password123") -> dict:
    """Insert a user directly into the test DB; return {id, email, token}."""
    db = _TestSessionLocal()
    try:
        user = User(email=email, hashed_password=hash_password(password), role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token(user_id=user.id, role=user.role)
        return {"id": user.id, "email": user.email, "token": token}
    finally:
        db.close()


@pytest.fixture
def make_user():
    """Factory fixture — call make_user(email, role='user') inside a test."""
    return _insert_user


@pytest.fixture
def regular_user():
    """A user with the 'user' role pre-inserted into the test DB."""
    return _insert_user("user@test.com", role="user")


@pytest.fixture
def admin_user():
    """A user with the 'admin' role pre-inserted into the test DB."""
    return _insert_user("admin@test.com", role="admin")


@pytest.fixture
def viewer_user():
    """A user with the 'viewer' role pre-inserted into the test DB."""
    return _insert_user("viewer@test.com", role="viewer")


# ---------------------------------------------------------------------------
# Auth header helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def user_headers(regular_user):
    return {"Authorization": f"Bearer {regular_user['token']}"}


@pytest.fixture
def admin_headers(admin_user):
    return {"Authorization": f"Bearer {admin_user['token']}"}


@pytest.fixture
def viewer_headers(viewer_user):
    return {"Authorization": f"Bearer {viewer_user['token']}"}


# ---------------------------------------------------------------------------
# Task factory helper
# ---------------------------------------------------------------------------

TASK_PAYLOAD = {
    "title": "Test outage task",
    "description": "A test work order",
    "status": "reported",
    "priority": "medium",
    "category": "grid_maintenance",
}
