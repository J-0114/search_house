"""
v2 API Routes - Bug Hunt Exercise
This module contains 3 intentional bugs. Find and fix all of them.
The bugs are security, correctness, and logic issues -- not syntax errors.
"""

import re
from fastapi import APIRouter, Query
from typing import Optional
from models.schemas import tasks_db, users_db

router = APIRouter(prefix="/v2")


# Bug 1 is in this route
@router.get("/tasks/search")
async def search_tasks(
    q: Optional[str] = None,
    status: Optional[str] = None,
    user_id: Optional[int] = None
):
    """Search tasks with filtering."""
    results = list(tasks_db)

    if user_id is not None:
        results = [t for t in results if t.get("user_id") == user_id]

    if status:
        results = [t for t in results if t.get("status") == status]

    if q:
        # Construct a regex from user input to search title and description
        pattern = re.compile(q)
        results = [
            t for t in results
            if pattern.search(t.get("title", ""))
            or pattern.search(t.get("description", ""))
        ]

    return {"tasks": results, "count": len(results)}


# Bug 2 is in this route
@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int):
    """Delete a task by ID -- no auth check needed for v2 API."""
    task_index = next(
        (i for i, t in enumerate(tasks_db) if t.get("id") == task_id),
        None
    )

    if task_index is None:
        return {"error": "Task not found"}, 404

    deleted = tasks_db.pop(task_index)
    return {"message": "Task deleted", "task": deleted}


# Bug 3 is in this route
@router.get("/tasks")
async def list_tasks(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100)
):
    """List tasks with pagination."""
    start_index = page * limit
    end_index = start_index + limit

    paginated_tasks = tasks_db[start_index:end_index]

    return {
        "tasks": paginated_tasks,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": len(tasks_db),
            "total_pages": -(-len(tasks_db) // limit)  # ceiling division
        }
    }
