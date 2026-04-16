"""
Comments router — /tasks/{task_id}/comments
"""

import os
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from dependencies.auth import get_current_user, require_user
from dependencies.db import get_db
from models.orm import Comment, Task, User
from models.schemas import CommentCreate, CommentResponse

router = APIRouter(tags=["comments"])


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class _CommentBroadcaster:
    def __init__(self):
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, task_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[task_id].add(ws)

    def disconnect(self, task_id: int, ws: WebSocket) -> None:
        self._connections[task_id].discard(ws)

    async def broadcast(self, task_id: int, data: dict) -> None:
        dead: set[WebSocket] = set()
        for ws in list(self._connections.get(task_id, set())):
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._connections[task_id].discard(ws)


broadcaster = _CommentBroadcaster()


def _get_task_or_404(task_id: int, db: Session) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# ---------------------------------------------------------------------------
# POST /tasks/{task_id}/comments
# ---------------------------------------------------------------------------

@router.post("/tasks/{task_id}/comments", response_model=CommentResponse, status_code=201)
async def add_comment(
    task_id: int,
    body: CommentCreate,
    current_user: dict = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Add a comment to a task. Requires user or admin role."""
    task = _get_task_or_404(task_id, db)
    # Resolve email from DB so the author field is always accurate
    user = db.get(User, current_user["user_id"])
    author_email = user.email if user else f"user:{current_user['user_id']}"
    comment = Comment(
        task_id=task.id,
        author=author_email,
        body=body.body,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    await broadcaster.broadcast(task_id, {
        "type": "new",
        "comment": {
            "id": comment.id,
            "task_id": comment.task_id,
            "author": comment.author,
            "body": comment.body,
            "created_at": comment.created_at.isoformat(),
        },
    })
    return comment


# ---------------------------------------------------------------------------
# GET /tasks/{task_id}/comments
# ---------------------------------------------------------------------------

@router.get("/tasks/{task_id}/comments", response_model=list[CommentResponse])
async def list_comments(
    task_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all comments for a task, ordered by creation time (oldest first)."""
    _get_task_or_404(task_id, db)
    comments = db.scalars(
        select(Comment).where(Comment.task_id == task_id).order_by(Comment.created_at)
    ).all()
    return list(comments)


# ---------------------------------------------------------------------------
# DELETE /tasks/{task_id}/comments/{comment_id}
# ---------------------------------------------------------------------------

@router.delete("/tasks/{task_id}/comments/{comment_id}", status_code=204)
async def delete_comment(
    task_id: int,
    comment_id: int,
    current_user: dict = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Delete a comment. Authors can delete their own; admins can delete any."""
    _get_task_or_404(task_id, db)
    comment = db.get(Comment, comment_id)
    if comment is None or comment.task_id != task_id:
        raise HTTPException(status_code=404, detail="Comment not found")

    if current_user["role"] != "admin":
        user = db.get(User, current_user["user_id"])
        if not user or comment.author != user.email:
            raise HTTPException(status_code=403, detail="You can only delete your own comments")

    db.delete(comment)
    db.commit()
    await broadcaster.broadcast(task_id, {"type": "delete", "comment_id": comment_id})


# ---------------------------------------------------------------------------
# WS /ws/tasks/{task_id}/comments
# ---------------------------------------------------------------------------

@router.websocket("/ws/tasks/{task_id}/comments")
async def ws_comments(
    task_id: int,
    websocket: WebSocket,
    token: str = Query(...),
):
    """WebSocket — push comment events (new/delete) to all viewers of a task."""
    JWT_SECRET = os.environ.get("JWT_SECRET")
    try:
        jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except JWTError:
        await websocket.close(code=4001)
        return

    await broadcaster.connect(task_id, websocket)
    try:
        while True:
            await websocket.receive_text()   # keep-alive / ignore client messages
    except WebSocketDisconnect:
        broadcaster.disconnect(task_id, websocket)
