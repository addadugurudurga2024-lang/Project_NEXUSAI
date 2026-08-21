from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class IssueSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class IssuePriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class IssueStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"
    wont_fix = "wont_fix"


class IssueCategory(str, Enum):
    bug = "bug"
    security = "security"
    performance = "performance"
    ux = "ux"
    database = "database"
    backend = "backend"
    frontend = "frontend"
    devops = "devops"
    requirement = "requirement"
    other = "other"


class IssueCreate(BaseModel):
    title: str
    description: Optional[str] = None
    project_id: str
    task_id: Optional[str] = None
    category: IssueCategory = IssueCategory.bug
    severity: IssueSeverity = IssueSeverity.medium
    priority: IssuePriority = IssuePriority.medium
    status: IssueStatus = IssueStatus.open
    assignee_id: Optional[str] = None
    resolution: Optional[str] = None


class IssueUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[IssueCategory] = None
    severity: Optional[IssueSeverity] = None
    priority: Optional[IssuePriority] = None
    status: Optional[IssueStatus] = None
    assignee_id: Optional[str] = None
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None


class IssueResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    project_id: str
    task_id: Optional[str] = None
    category: str
    severity: str
    priority: str
    status: str
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
