"""
Audit log router — /tasks/{task_id}/audit
Also exports `record_audit`, a helper called by tasks.py to persist mutations.

Design note: AuditLog.task_id is a plain int (no FK) so audit records survive
task deletion and the DELETE action is always persisted.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from dependencies.auth import get_current_user
from dependencies.db import get_db
from models.orm import AuditLog, Task
from models.schemas import AuditLogResponse

router = APIRouter(tags=["audit"])

# Fields tracked for before/after diffs on Task mutations
TRACKED_FIELDS: list[str] = [
    "title", "description", "status", "priority",
    "legacy_category", "location", "asset_id",
]


# ---------------------------------------------------------------------------
# Public helper — called from tasks.py (not a route)
# ---------------------------------------------------------------------------

def record_audit(
    db: Session,
    task_id: int,
    action: str,          # "create" | "update" | "delete"
    changed_by: str,
    changes: Optional[list[tuple[str, Optional[str], Optional[str]]]] = None,
) -> None:
    """
    Append one or more AuditLog rows to the current session (no commit).

    For create/delete pass changes=None — a single header row is written.
    For updates pass a list of (field, old_value, new_value) tuples;
    only tuples where old != new are written.
    """
    if not changes:
        db.add(AuditLog(task_id=task_id, action=action, changed_by=changed_by))
        return

    wrote = False
    for field, old, new in changes:
        if old == new:
            continue
        db.add(AuditLog(
            task_id=task_id,
            action=action,
            changed_by=changed_by,
            field=field,
            old_value=str(old) if old is not None else None,
            new_value=str(new) if new is not None else None,
        ))
        wrote = True

    # If nothing actually changed, write a no-op entry so the call is traceable
    if not wrote:
        db.add(AuditLog(task_id=task_id, action=action, changed_by=changed_by))


def task_snapshot(task: Task) -> dict[str, Optional[str]]:
    """Capture a dict of the tracked fields before a mutation."""
    return {f: getattr(task, f) for f in TRACKED_FIELDS}


def snapshot_diff(
    before: dict[str, Optional[str]],
    after: Task,
) -> list[tuple[str, Optional[str], Optional[str]]]:
    """Return (field, old, new) for every tracked field that changed."""
    return [
        (f, before[f], getattr(after, f))
        for f in TRACKED_FIELDS
        if before[f] != getattr(after, f)
    ]


# ---------------------------------------------------------------------------
# GET /tasks/{task_id}/audit
# ---------------------------------------------------------------------------

@router.get("/tasks/{task_id}/audit", response_model=list[AuditLogResponse])
async def get_audit_log(
    task_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the full audit trail for a task, newest first."""
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    logs = db.scalars(
        select(AuditLog)
        .where(AuditLog.task_id == task_id)
        .order_by(AuditLog.timestamp.desc())
    ).all()
    return list(logs)
