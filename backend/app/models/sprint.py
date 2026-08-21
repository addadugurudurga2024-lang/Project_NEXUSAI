from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class SprintStatus(str, Enum):
    planning = "planning"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class SprintCreate(BaseModel):
    name: str
    project_id: str
    goal: Optional[str] = None
    status: SprintStatus = SprintStatus.planning
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    capacity_hours: float = 0.0
    planned_story_points: int = 0


class SprintUpdate(BaseModel):
    name: Optional[str] = None
    goal: Optional[str] = None
    status: Optional[SprintStatus] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    capacity_hours: Optional[float] = None
    planned_story_points: Optional[int] = None
    completed_story_points: Optional[int] = None
    velocity: Optional[float] = None


class SprintResponse(BaseModel):
    id: str
    name: str
    project_id: str
    goal: Optional[str] = None
    status: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    capacity_hours: float
    planned_story_points: int
    completed_story_points: int = 0
    velocity: float = 0.0
    task_count: int = 0
    created_at: Optional[datetime] = None
