"""
Categories router — /categories
Includes the bulk categorize endpoint: POST /tasks/bulk/categorize
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from dependencies.auth import get_current_user, require_admin, require_user
from dependencies.db import get_db
from models.orm import Category, Task
from models.schemas import (
    BulkCategorizeRequest,
    BulkCategorizeResponse,
    CategoryCreate,
    CategoryResponse,
)

router = APIRouter(tags=["categories"])


# ---------------------------------------------------------------------------
# POST /categories — create a category (admin only)
# ---------------------------------------------------------------------------

@router.post("/categories", response_model=CategoryResponse, status_code=201)
async def create_category(
    body: CategoryCreate,
    _admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new category label. Requires admin role."""
    existing = db.scalar(select(Category).where(Category.name == body.name))
    if existing:
        raise HTTPException(status_code=409, detail="Category name already exists")
    cat = Category(name=body.name)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


# ---------------------------------------------------------------------------
# GET /categories — list all categories
# ---------------------------------------------------------------------------

@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(
    _user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all available categories."""
    return list(db.scalars(select(Category).order_by(Category.name)).all())


# ---------------------------------------------------------------------------
# POST /tasks/bulk/categorize — assign a category to multiple tasks (transactional)
# ---------------------------------------------------------------------------

@router.post("/tasks/bulk/categorize", response_model=BulkCategorizeResponse)
async def bulk_categorize(
    body: BulkCategorizeRequest,
    current_user: dict = Depends(require_user),
    db: Session = Depends(get_db),
):
    """
    Assign a category to multiple tasks in a single atomic transaction.
    Requires user or admin role. If ANY task ID is not found, the entire operation rolls back.
    """
    category = db.get(Category, body.category_id)
    if category is None:
        raise HTTPException(status_code=404, detail=f"Category {body.category_id} not found")

    tasks: list[Task] = []
    for task_id in body.task_ids:
        task = db.get(Task, task_id, options=[selectinload(Task.categories)])
        if task is None:
            db.rollback()
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        if task.user_id != current_user["user_id"] and current_user["role"] != "admin":
            db.rollback()
            raise HTTPException(
                status_code=403,
                detail=f"You do not have permission to modify task {task_id}",
            )
        tasks.append(task)

    # All IDs valid — apply inside a single transaction
    try:
        for task in tasks:
            if category not in task.categories:
                task.categories.append(category)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to categorize tasks")

    return BulkCategorizeResponse(updated=len(tasks), category=category)
