"""
Task Manager API - Starter Code
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from routers import admin, attachments, audit, auth, categories, comments, tasks
from routers.auth import limiter
from database import init_db
from logging_config import setup_logging
from middleware.request_id import RequestIdMiddleware
import logging

setup_logging()

logger = logging.getLogger(__name__)

tags_metadata = [
    {
        "name": "auth",
        "description": "Register, login, and refresh JWT tokens.",
    },
    {
        "name": "tasks",
        "description": "Field operations task management — create, track and resolve grid, outage, solar and inspection work orders.",
    },
    {
        "name": "admin",
        "description": "Admin-only endpoints. Requires `admin` role.",
    },
    {
        "name": "categories",
        "description": "Category management and bulk task categorization.",
    },
    {
        "name": "comments",
        "description": "Comments on tasks.",
    },
    {
        "name": "attachments",
        "description": "File attachments on tasks. Max 5 MB per file.",
    },
    {
        "name": "audit",
        "description": "Immutable audit trail — every task mutation recorded with actor, field, before/after values.",
    },
    {
        "name": "health",

        "description": "Service health check.",
    },
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup: initialising database")
    init_db()
    logger.info("startup: complete")
    yield
    logger.info("shutdown: complete")


app = FastAPI(
    title="EDP Field Ops — Task Manager API",
    lifespan=lifespan,
    description=(
        "REST API for managing field operations work orders at EDP. "
        "Track outages, grid maintenance, solar installations, EV charging deployments and safety inspections.\n\n"
        "### Quick start\n"
        "1. `POST /auth/register` — create an account\n"
        "2. `POST /auth/login` — get a JWT token\n"
        "3. Click **Authorize** above and paste the token\n"
        "4. `POST /tasks` — open a new work order\n"
        "5. `GET /tasks` — list your tasks\n"
    ),
    version="1.0.0",
    openapi_tags=tags_metadata,
    swagger_ui_parameters={
        "tryItOutEnabled": True,
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "filter": True,
        "defaultModelsExpandDepth": 2,
        "defaultModelExpandDepth": 2,
    },
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS — enumerate explicit origins instead of wildcard to allow credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-Request-ID"],
)

# Correlation ID — must be outermost so requestId is set before any router runs
app.add_middleware(RequestIdMiddleware)





@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "message": "Task Manager API is running"}


app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", include_in_schema=False)  # noqa: F811
async def frontend():
    return FileResponse("static/index.html")

# Authentication routes
app.include_router(auth.router)

# Task routes
app.include_router(tasks.router)

# Admin routes
app.include_router(admin.router)

# Category & bulk categorize routes
app.include_router(categories.router)

# Comment routes
app.include_router(comments.router)

# Attachment routes
app.include_router(attachments.router)

# Audit log routes
app.include_router(audit.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
