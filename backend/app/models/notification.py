from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class NotificationCreate(BaseModel):
    user_id: str = Field(..., alias="userId")
    type: str
    title: str
    message: str
    related_project_id: Optional[str] = Field(None, alias="relatedProjectId")
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
    severity: Optional[str] = "medium"
    is_read: bool
    created_at: Optional[datetime] = None
