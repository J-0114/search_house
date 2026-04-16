"""
Task CRUD router — /tasks
"""

import math
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import or_, select, func
from sqlalchemy.orm import Session, selectinload

from dependencies.auth import get_current_user, require_user
from dependencies.db import get_db
from models.orm import Task, User
from models.schemas import (
    TaskCategory,
    TaskCreate,
    TaskListResponse,
    TaskPriority,
    TaskResponse,
    TaskStatus,
    TaskUpdate,
)
from routers.audit import record_audit, snapshot_diff, task_snapshot

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _actor_email(db: Session, current_user: dict) -> str:
    """Resolve the authenticated user's email for audit entries."""
    user = db.get(User, current_user["user_id"])
    return user.email if user else f"user:{current_user['user_id']}"


def _get_task_or_404(task_id: int, db: Session) -> Task:
    task = db.get(Task, task_id, options=[selectinload(Task.categories)])
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _check_owner(task: Task, current_user: dict) -> None:
    """Admins can modify any task; users can only modify their own."""
    if current_user["role"] == "admin":
        return
    if task.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="You do not have permission to modify this task")


# ---------------------------------------------------------------------------
# POST /tasks
# ---------------------------------------------------------------------------

@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    body: Annotated[
        TaskCreate,
        Body(
            openapi_examples={
                "outage": {
                    "summary": "Outage response (critical)",
                    "value": {
                        "title": "Power outage — Zona Industrial Setúbal",
                        "description": "Full blackout affecting 3 industrial units. Transformer fault suspected.",
                        "status": "reported",
                        "priority": "critical",
                        "category": "outage_response",
                        "location": "Zona Industrial Setúbal, Lote 14",
                        "asset_id": "TR-9021-STB",
                    },
                },
                "solar": {
                    "summary": "Solar panel installation",
                    "value": {
                        "title": "Residential solar install — Lisboa Norte",
                        "description": "Install 12-panel system, 6 kWp. Customer contract EDP-SOL-2026-4471.",
                        "status": "assigned",
                        "priority": "medium",
                        "category": "solar_installation",
                        "location": "Rua das Flores 42, Lisboa",
                        "asset_id": "SOL-4471",
                    },
                },
                "meter": {
                    "summary": "Meter inspection",
                    "value": {
                        "title": "Quarterly meter audit — block C",
                        "description": "Scheduled smart meter accuracy check for residential block C.",
                        "status": "reported",
                        "priority": "low",
                        "category": "meter_inspection",
                        "location": "Avenida da República 200, Porto",
                        "asset_id": "MTR-77342-C",
                    },
                },
            }
        ),
    ],
    current_user: dict = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Create a new field-ops task. Requires user or admin role."""
    task = Task(
        user_id=current_user["user_id"],
        title=body.title,
        description=body.description,
        status=body.status.value,
        priority=body.priority.value,
        legacy_category=body.category.value if body.category else None,
        location=body.location,
        asset_id=body.asset_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    # Re-fetch with categories eagerly loaded so the response includes the relationship
    task = db.scalar(select(Task).where(Task.id == task.id).options(selectinload(Task.categories)))
    record_audit(db, task.id, "create", _actor_email(db, current_user))
    db.commit()
    return task


# ---------------------------------------------------------------------------
# GET /tasks
# ---------------------------------------------------------------------------

@router.get("", response_model=TaskListResponse)
async def list_tasks(
    status: Optional[TaskStatus] = Query(None),
    priority: Optional[TaskPriority] = Query(None),
    category: Optional[TaskCategory] = Query(None, description="Filter by legacy category"),
    location: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Search in title and description"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all tasks. All roles see all tasks; only owners/admins can edit or delete."""
    stmt = select(Task).options(selectinload(Task.categories))

    if status:
        stmt = stmt.where(Task.status == status.value)
    if priority:
        stmt = stmt.where(Task.priority == priority.value)
    if category:
        stmt = stmt.where(Task.legacy_category == category.value)
    if location:
        stmt = stmt.where(Task.location.ilike(f"%{location}%"))
    if q:
        stmt = stmt.where(
            or_(Task.title.ilike(f"%{q}%"), Task.description.ilike(f"%{q}%"))
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    pages = max(1, math.ceil(total / limit))
    items = db.scalars(stmt.offset((page - 1) * limit).limit(limit)).all()

    return TaskListResponse(tasks=list(items), total=total, page=page, limit=limit, pages=pages)


# ---------------------------------------------------------------------------
# GET /tasks/{task_id}
# ---------------------------------------------------------------------------

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a task by ID. All roles can see any task."""
    return _get_task_or_404(task_id, db)


# ---------------------------------------------------------------------------
# PUT /tasks/{task_id}
# ---------------------------------------------------------------------------

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    body: TaskCreate,
    current_user: dict = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Replace all fields of a task. Requires user or admin role."""
    task = _get_task_or_404(task_id, db)
    _check_owner(task, current_user)
    before = task_snapshot(task)
    task.title = body.title
    task.description = body.description
    task.status = body.status.value
    task.priority = body.priority.value
    task.legacy_category = body.category.value if body.category else None
    task.location = body.location
    task.asset_id = body.asset_id
    record_audit(db, task.id, "update", _actor_email(db, current_user), snapshot_diff(before, task))
    db.commit()
    db.refresh(task)
    return task


# ---------------------------------------------------------------------------
# PATCH /tasks/{task_id}
# ---------------------------------------------------------------------------

@router.patch("/{task_id}", response_model=TaskResponse)
async def partial_update_task(
    task_id: int,
    body: Annotated[
        TaskUpdate,
        Body(
            openapi_examples={
                "escalate": {"summary": "Escalate", "value": {"status": "assigned", "priority": "critical"}},
                "resolve": {"summary": "Mark in progress", "value": {"status": "in_progress"}},
            }
        ),
    ],
    current_user: dict = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Partially update a task's fields. Requires user or admin role."""
    task = _get_task_or_404(task_id, db)
    _check_owner(task, current_user)
    before = task_snapshot(task)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        orm_field = "legacy_category" if field == "category" else field
        if hasattr(value, "value"):
            value = value.value
        setattr(task, orm_field, value)
    record_audit(db, task.id, "update", _actor_email(db, current_user), snapshot_diff(before, task))
    db.commit()
    db.refresh(task)
    return task


# ---------------------------------------------------------------------------
# PATCH /tasks/{task_id}/complete
# ---------------------------------------------------------------------------

@router.patch("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: int,
    current_user: dict = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Mark a task as resolved. Requires user or admin role."""
    task = _get_task_or_404(task_id, db)
    _check_owner(task, current_user)
    before = task_snapshot(task)
    task.status = TaskStatus.RESOLVED.value
    record_audit(db, task.id, "update", _actor_email(db, current_user), snapshot_diff(before, task))
    db.commit()
    db.refresh(task)
    return task


# ---------------------------------------------------------------------------
# DELETE /tasks/{task_id}
# ---------------------------------------------------------------------------

@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: int,
    current_user: dict = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Delete a task. Requires user or admin role."""
    task = _get_task_or_404(task_id, db)
    _check_owner(task, current_user)
    email = _actor_email(db, current_user)
    task_id_val = task.id
    db.delete(task)
    record_audit(db, task_id_val, "delete", email)
    db.commit()
