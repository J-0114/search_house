"""
Data models for Task Manager API
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ---------------------------------------------------------------------------
# User / Auth schemas
# ---------------------------------------------------------------------------

class UserRole(str, Enum):
    VIEWER = "viewer"
    USER = "user"
    ADMIN = "admin"


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: int
    email: str
    role: UserRole

    model_config = {"from_attributes": True}


class UserRoleUpdate(BaseModel):
    role: UserRole


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TaskStatus(str, Enum):
    REPORTED = "reported"       # Issue logged, not yet assigned
    ASSIGNED = "assigned"       # Assigned to a technician
    IN_PROGRESS = "in_progress" # Technician on-site or working
    RESOLVED = "resolved"       # Work completed, pending sign-off
    CLOSED = "closed"           # Verified and closed


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"   # Active outage or safety risk


class TaskCategory(str, Enum):
    GRID_MAINTENANCE = "grid_maintenance"       # Scheduled grid upkeep
    OUTAGE_RESPONSE = "outage_response"         # Unplanned power cut
    METER_INSPECTION = "meter_inspection"       # Meter reading / audit
    SOLAR_INSTALLATION = "solar_installation"   # Residential/commercial solar
    EV_CHARGING = "ev_charging"                 # EV infrastructure
    CUSTOMER_REQUEST = "customer_request"       # Contract / billing issue
    SAFETY_INSPECTION = "safety_inspection"     # Regulatory safety check


# ---------------------------------------------------------------------------
# Task schemas
# ---------------------------------------------------------------------------

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    status: TaskStatus = TaskStatus.REPORTED
    priority: TaskPriority = TaskPriority.MEDIUM
    category: TaskCategory = TaskCategory.GRID_MAINTENANCE
    location: Optional[str] = Field(None, max_length=200, description="Address or grid zone")
    asset_id: Optional[str] = Field(None, max_length=50, description="Equipment identifier (e.g. meter or transformer ID)")


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    category: Optional[TaskCategory] = None
    location: Optional[str] = Field(None, max_length=200)
    asset_id: Optional[str] = Field(None, max_length=50)


class CategoryResponse(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class TaskResponse(BaseModel):
    id: int
    user_id: int
    title: str
    description: Optional[str]
    status: TaskStatus
    priority: TaskPriority
    # legacy single-category field (nullable after migration to many-to-many)
    category: Optional[TaskCategory] = None
    categories: List[CategoryResponse] = []
    location: Optional[str]
    asset_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int
    page: int
    limit: int
    pages: int


# ---------------------------------------------------------------------------
# Category schemas
# ---------------------------------------------------------------------------

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class BulkCategorizeRequest(BaseModel):
    task_ids: List[int] = Field(..., min_length=1)
    category_id: int


class BulkCategorizeResponse(BaseModel):
    updated: int
    category: CategoryResponse


# ---------------------------------------------------------------------------
# Comment schemas
# ---------------------------------------------------------------------------

class CommentCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=2000)


class CommentResponse(BaseModel):
    id: int
    task_id: int
    author: str
    body: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Attachment schemas
# ---------------------------------------------------------------------------

class AttachmentResponse(BaseModel):
    id: int
    task_id: int
    filename: str
    content_type: str
    size: int
    uploaded_by: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Audit log schemas
# ---------------------------------------------------------------------------

class AuditLogResponse(BaseModel):
    id: int
    task_id: int
    action: str
    changed_by: str
    field: Optional[str]
    old_value: Optional[str]
    new_value: Optional[str]
    timestamp: datetime

    model_config = {"from_attributes": True}
