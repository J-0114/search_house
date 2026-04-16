"""
Admin router — /admin
"""

import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select, func
from sqlalchemy.orm import Session, selectinload

from dependencies.auth import require_admin
from dependencies.db import get_db
from models.orm import Task, User
from models.schemas import (
    TaskCategory,
    TaskListResponse,
    TaskPriority,
    TaskStatus,
    UserResponse,
    UserRoleUpdate,
)

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# GET /admin/tasks — all tasks across all users
# ---------------------------------------------------------------------------

@router.get("/tasks", response_model=TaskListResponse)
async def admin_list_tasks(
    status: Optional[TaskStatus] = Query(None),
    priority: Optional[TaskPriority] = Query(None),
    category: Optional[TaskCategory] = Query(None),
    user_id: Optional[int] = Query(None, description="Filter by owner user ID"),
    q: Optional[str] = Query(None, description="Search in title and description"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all tasks across all users. Requires admin role."""
    stmt = select(Task).options(selectinload(Task.categories))

    if status:
        stmt = stmt.where(Task.status == status.value)
    if priority:
        stmt = stmt.where(Task.priority == priority.value)
    if category:
        stmt = stmt.where(Task.legacy_category == category.value)
    if user_id is not None:
        stmt = stmt.where(Task.user_id == user_id)
    if q:
        stmt = stmt.where(
            or_(Task.title.ilike(f"%{q}%"), Task.description.ilike(f"%{q}%"))
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    pages = max(1, math.ceil(total / limit))
    items = db.scalars(stmt.offset((page - 1) * limit).limit(limit)).all()

    return TaskListResponse(tasks=list(items), total=total, page=page, limit=limit, pages=pages)


# ---------------------------------------------------------------------------
# GET /admin/users — list all users
# ---------------------------------------------------------------------------

@router.get("/users", response_model=list[UserResponse])
async def admin_list_users(
    _admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return all registered users. Requires admin role."""
    return db.scalars(select(User).order_by(User.id)).all()


# ---------------------------------------------------------------------------
# PATCH /admin/users/{user_id}/role — change a user's role
# ---------------------------------------------------------------------------

@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def admin_update_user_role(
    user_id: int,
    body: UserRoleUpdate,
    current_admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Change a user's role. Admins cannot demote themselves."""
    if user_id == current_admin["user_id"]:
        raise HTTPException(status_code=400, detail="You cannot change your own role")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = body.role.value
    db.commit()
    db.refresh(user)
    return user
