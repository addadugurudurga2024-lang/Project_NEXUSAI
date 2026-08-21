from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class AllocationStatus(str, Enum):
    suggested = "suggested"
    accepted = "accepted"
    rejected = "rejected"
    applied = "applied"


class ResourceAllocationCreate(BaseModel):
    project_id: str = Field(..., alias="projectId")
    task_id: str = Field(..., alias="taskId")
    employee_id: str = Field(..., alias="employeeId")
    from_employee_id: Optional[str] = None
    current_allocation_hours: float = Field(..., alias="currentAllocationHours")
    recommended_allocation_hours: float = Field(..., alias="recommendedAllocationHours")
    allocation_change: float = Field(..., alias="allocationChange")
    reason: str
    expected_impact: str = Field(..., alias="expectedImpact")
    status: AllocationStatus = AllocationStatus.suggested

    class Config:
        populate_by_name = True


class ResourceAllocationResponse(BaseModel):
    id: str
    project_id: str
    project_name: Optional[str] = None
    task_id: str
    task_title: Optional[str] = None
    employee_id: str
    employee_name: Optional[str] = None
    from_employee_id: Optional[str] = None
    from_employee_name: Optional[str] = None
    current_allocation_hours: float
    recommended_allocation_hours: float
    allocation_change: float
    reason: str
    expected_impact: str
    status: str
    created_at: Optional[datetime] = None
