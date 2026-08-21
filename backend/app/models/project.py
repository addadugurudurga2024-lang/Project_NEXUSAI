from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from enum import Enum


class ProjectStatus(str, Enum):
    planning = "planning"
    active = "active"
    on_hold = "on_hold"
    completed = "completed"
    cancelled = "cancelled"


class ProjectPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    client: Optional[str] = None
    domain: Optional[str] = None
    status: ProjectStatus = ProjectStatus.planning
    priority: ProjectPriority = ProjectPriority.medium
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    budget: float = 0.0
    current_expenditure: float = 0.0
    progress: float = 0.0
    manager_id: Optional[str] = None
    team_member_ids: List[str] = []
    requirements: Optional[str] = None
    tech_stack: List[str] = []


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    client: Optional[str] = None
    domain: Optional[str] = None
    status: Optional[ProjectStatus] = None
    priority: Optional[ProjectPriority] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    budget: Optional[float] = None
    current_expenditure: Optional[float] = None
    progress: Optional[float] = None
    manager_id: Optional[str] = None
    team_member_ids: Optional[List[str]] = None
    requirements: Optional[str] = None
    tech_stack: Optional[List[str]] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    client: Optional[str] = None
    domain: Optional[str] = None
    status: str
    priority: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    budget: float
    current_expenditure: float
    progress: float
    manager_id: Optional[str] = None
    manager_name: Optional[str] = None
    team_member_ids: List[str] = []
    requirements: Optional[str] = None
    tech_stack: List[str] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
