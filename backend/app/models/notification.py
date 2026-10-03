from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class NotificationCreate(BaseModel):
    user_id: str = Field(..., alias="userId")
    type: str
    title: str
    message: str
    related_project_id: Optional[str] = Field(None, alias="relatedProjectId")
    related_issue_id: Optional[str] = Field(None, alias="relatedIssueId")
    assigned_by: Optional[str] = Field(None, alias="assignedBy")
    assigned_by_name: Optional[str] = Field(None, alias="assignedByName")
    severity: Optional[str] = "medium"
    is_read: bool = Field(False, alias="isRead")

    class Config:
        populate_by_name = True


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    type: str
    title: str
    message: str
    related_project_id: Optional[str] = None
    related_issue_id: Optional[str] = None
    assigned_by: Optional[str] = None
    assigned_by_name: Optional[str] = None
    severity: Optional[str] = "medium"
    is_read: bool
    created_at: Optional[datetime] = None
