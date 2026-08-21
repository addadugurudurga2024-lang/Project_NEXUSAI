from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class ReportCreate(BaseModel):
    project_id: str = Field(..., alias="projectId")
    report_type: str = Field("executive_summary", alias="reportType")
    title: Optional[str] = None

    class Config:
        populate_by_name = True


class ReportResponse(BaseModel):
    id: str
    project_id: str
    project_name: Optional[str] = None
    generated_by: str
    generated_by_name: Optional[str] = None
    report_type: str
    title: str
    content: str
    created_at: Optional[datetime] = None
