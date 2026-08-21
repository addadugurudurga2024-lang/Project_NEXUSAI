from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum


class EmployeeStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    on_leave = "on_leave"


class EmployeeCreate(BaseModel):
    name: str
    email: EmailStr
    role: str
    specialization: Optional[str] = None
    skills: List[str] = []
    experience_years: float = 0.0
    weekly_capacity_hours: float = 40.0
    availability_percentage: float = 100.0
    status: EmployeeStatus = EmployeeStatus.active
    user_id: Optional[str] = None


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    specialization: Optional[str] = None
    skills: Optional[List[str]] = None
    experience_years: Optional[float] = None
    weekly_capacity_hours: Optional[float] = None
    availability_percentage: Optional[float] = None
    status: Optional[EmployeeStatus] = None


class EmployeeResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    specialization: Optional[str] = None
    skills: List[str] = []
    experience_years: float
    weekly_capacity_hours: float
    availability_percentage: float
    status: str
    user_id: Optional[str] = None
    assigned_project_ids: List[str] = []
    created_at: Optional[datetime] = None
