"""
Attachments router — /tasks/{task_id}/attachments
Files are stored on disk under uploads/<task_id>/ and limited to 5 MB.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from dependencies.auth import get_current_user, require_user
from dependencies.db import get_db
from models.orm import Attachment, Task, User
from models.schemas import AttachmentResponse

router = APIRouter(tags=["attachments"])

# Resolved relative to this file so it works regardless of CWD
UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
MAX_BYTES = 5 * 1024 * 1024  # 5 MB

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/zip",
}


def _check_owner(task: Task, current_user: dict) -> None:
    """Admins can upload to any task; users can only upload to their own."""
    if current_user["role"] == "admin":
        return
    if task.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="You do not have permission to modify this task")


def _get_task_or_404(task_id: int, db: Session) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# ---------------------------------------------------------------------------
# POST /tasks/{task_id}/attachments
# ---------------------------------------------------------------------------

@router.post("/tasks/{task_id}/attachments", response_model=AttachmentResponse, status_code=201)
async def upload_attachment(
    task_id: int,
    file: UploadFile,
    current_user: dict = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Upload a file to a task. Max 5 MB. Requires user or admin role."""
    task = _get_task_or_404(task_id, db)
    _check_owner(task, current_user)

    # Validate MIME type against allowlist (client-supplied content_type is untrusted)
    declared_mime = (file.content_type or "").split(";")[0].strip().lower()
    if declared_mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail=f"File type '{declared_mime}' is not allowed")

    # Read up to MAX_BYTES + 1 so we can detect oversize without buffering the whole file
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 5 MB limit")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    user = db.get(User, current_user["user_id"])
    uploader = user.email if user else f"user:{current_user['user_id']}"

    # Sanitise filename — strip any path components
    original_name = Path(file.filename or "upload").name
    storage_name = f"{uuid.uuid4().hex}_{original_name}"
    task_dir = UPLOAD_DIR / str(task_id)
    task_dir.mkdir(parents=True, exist_ok=True)
    storage_path = task_dir / storage_name
    storage_path.write_bytes(data)

    attachment = Attachment(
        task_id=task_id,
        filename=original_name,
        content_type=declared_mime,  # store the validated MIME, not raw client value
        size=len(data),
        storage_path=str(storage_path.resolve()),
        uploaded_by=uploader,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


# ---------------------------------------------------------------------------
# GET /tasks/{task_id}/attachments
# ---------------------------------------------------------------------------

@router.get("/tasks/{task_id}/attachments", response_model=list[AttachmentResponse])
async def list_attachments(
    task_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List metadata for all attachments on a task."""
    _get_task_or_404(task_id, db)
    rows = db.scalars(
        select(Attachment)
        .where(Attachment.task_id == task_id)
        .order_by(Attachment.uploaded_at)
    ).all()
    return list(rows)


# ---------------------------------------------------------------------------
# GET /tasks/{task_id}/attachments/{file_id}
# ---------------------------------------------------------------------------

@router.get("/tasks/{task_id}/attachments/{file_id}")
async def download_attachment(
    task_id: int,
    file_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download an attachment by ID."""
    _get_task_or_404(task_id, db)
    attachment = db.get(Attachment, file_id)
    if attachment is None or attachment.task_id != task_id:
        raise HTTPException(status_code=404, detail="Attachment not found")

    path = Path(attachment.storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=str(path),
        filename=attachment.filename,
        media_type="application/octet-stream",  # never trust client-supplied MIME on download
    )


# ---------------------------------------------------------------------------
# DELETE /tasks/{task_id}/attachments/{file_id}
# ---------------------------------------------------------------------------

@router.delete("/tasks/{task_id}/attachments/{file_id}", status_code=204)
async def delete_attachment(
    task_id: int,
    file_id: int,
    current_user: dict = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Delete an attachment. Uploader or admin only."""
    _get_task_or_404(task_id, db)
    attachment = db.get(Attachment, file_id)
    if attachment is None or attachment.task_id != task_id:
        raise HTTPException(status_code=404, detail="Attachment not found")

    if current_user["role"] != "admin":
        user = db.get(User, current_user["user_id"])
        if not user or attachment.uploaded_by != user.email:
            raise HTTPException(status_code=403, detail="You can only delete your own attachments")

    # Remove file from disk (best-effort — don't fail if already gone)
    path = Path(attachment.storage_path)
    if path.exists():
        path.unlink()

    db.delete(attachment)
    db.commit()
