from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    review = "review"
    done = "done"
    blocked = "blocked"


class TaskPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    project_id: str
    sprint_id: Optional[str] = None
    assignee_id: Optional[str] = None
    status: TaskStatus = TaskStatus.todo
    priority: TaskPriority = TaskPriority.medium
    story_points: int = 0
    estimated_hours: float = 0.0
    actual_hours: float = 0.0
    completion_percentage: float = 0.0
    due_date: Optional[str] = None
    task_type: Optional[str] = "feature"
    labels: List[str] = []


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    sprint_id: Optional[str] = None
    assignee_id: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    story_points: Optional[int] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    completion_percentage: Optional[float] = None
    due_date: Optional[str] = None
    task_type: Optional[str] = None
    labels: Optional[List[str]] = None


class TaskResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    project_id: str
    sprint_id: Optional[str] = None
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    status: str
    priority: str
    story_points: int
    estimated_hours: float
    actual_hours: float
    completion_percentage: float
    due_date: Optional[str] = None
    task_type: Optional[str] = None
    labels: List[str] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
