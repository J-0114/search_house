"""
Auth router — /auth
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.orm import Session

from dependencies.auth import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from dependencies.db import get_db
from models.orm import User
from models.schemas import (
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    UserRole,
)

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer()
limiter = Limiter(key_func=get_remote_address)


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------

@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit("5/minute")
async def register(request: Request, body: UserRegister, db: Session = Depends(get_db)):
    """Register a new user. Email must be unique. Password is hashed with bcrypt."""
    existing = db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        role=UserRole.VIEWER.value,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, body: UserLogin, db: Session = Depends(get_db)):
    """Authenticate with email and password. Returns a JWT access token."""
    user = db.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user_id=user.id, role=user.role)
    return TokenResponse(access_token=token)


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------

@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """Issue a new token from a valid existing token. Role is always re-read from the DB."""
    payload = decode_token(credentials.credentials)
    user_id = int(payload["sub"])

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")

    # Re-read role from DB so a demoted user immediately loses elevated access
    token = create_access_token(user_id=user.id, role=user.role)
    return TokenResponse(access_token=token)
