from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum


class RecommendationPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class RecommendationStatus(str, Enum):
    pending = "pending"
    reviewed = "reviewed"
    accepted = "accepted"
    rejected = "rejected"
    completed = "completed"
    implemented = "implemented"


class RecommendationCreate(BaseModel):
    project_id: str = Field(..., alias="projectId")
    employee_id: Optional[str] = Field(None, alias="employeeId")
    category: str
    priority: RecommendationPriority = RecommendationPriority.medium
    title: str
    description: Optional[str] = None
    reason: str
    suggested_action: str = Field(..., alias="suggestedAction")
    expected_impact: str = Field(..., alias="expectedImpact")
    status: RecommendationStatus = RecommendationStatus.pending

    class Config:
        populate_by_name = True


class RecommendationUpdate(BaseModel):
    status: RecommendationStatus
    notes: Optional[str] = None


class RecommendationResponse(BaseModel):
    id: str
    project_id: str
    project_name: Optional[str] = None
    employee_id: Optional[str] = None
    employee_name: Optional[str] = None
    category: str
    priority: str
    title: str
    description: Optional[str] = None
    reason: str
    suggested_action: str
    expected_impact: str
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
