from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class DecisionType(str, Enum):
    RESOURCE_REALLOCATION = "RESOURCE_REALLOCATION"
    CROSS_PM_RESOURCE_REQUEST = "CROSS_PM_RESOURCE_REQUEST"
    SCHEDULE_COMPRESSION = "SCHEDULE_COMPRESSION"
    SPRINT_RESCOPE = "SPRINT_RESCOPE"
    BUDGET_INVESTIGATION = "BUDGET_INVESTIGATION"
    QUALITY_ESCALATION = "QUALITY_ESCALATION"
    RISK_MITIGATION = "RISK_MITIGATION"
    PROJECT_SCOPE_CHANGE = "PROJECT_SCOPE_CHANGE"
    OTHER = "OTHER"


class DecisionStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"


class DecisionPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionSourceType(str, Enum):
    RECOMMENDATION = "recommendation"
    RESOURCE_OPTIMIZATION = "resource_optimization"
    CROSS_PM_REQUEST = "cross_pm_request"
    PREDICTION = "prediction"
    ISSUE = "issue"
    TASK = "task"
    PROJECT_RISK = "project_risk"
    MANUAL = "manual"


class DecisionAlternative(BaseModel):
    id: Optional[str] = None
    title: str
    description: Optional[str] = None
    is_selected: bool = False


class ObservedFact(BaseModel):
    category: str
    fact: str
    severity: Optional[str] = None
    impact_score: Optional[float] = None


class DecisionAuditEntry(BaseModel):
    action: str
    performed_by_id: str
    performed_by_name: str
    timestamp: datetime
    previous_status: Optional[str] = None
    new_status: str
    notes: Optional[str] = None


class DecisionCreate(BaseModel):
    project_id: str
    title: str
    decision_type: DecisionType = DecisionType.OTHER
    description: Optional[str] = None
    priority: DecisionPriority = DecisionPriority.MEDIUM
    decision_status: DecisionStatus = DecisionStatus.PENDING
    selected_action: Optional[str] = None
    decision_rationale: Optional[str] = None
    source_type: Optional[str] = "manual"
    source_reference_id: Optional[str] = None
    source_recommendation_id: Optional[str] = None
    source_prediction_id: Optional[str] = None
    source_issue_id: Optional[str] = None
    source_task_id: Optional[str] = None
    source_resource_request_id: Optional[str] = None
    observed_facts: List[Dict[str, Any]] = Field(default_factory=list)
    prediction_summary: Optional[Dict[str, Any]] = None
    recommendation_summary: Optional[Dict[str, Any]] = None
    alternatives: List[Dict[str, Any]] = Field(default_factory=list)
    affected_entities: List[Dict[str, Any]] = Field(default_factory=list)
    expected_impact: Optional[str] = None


class DecisionActionRequest(BaseModel):
    rationale: str
    selected_action: Optional[str] = None
    selected_alternative_id: Optional[str] = None
    notes: Optional[str] = None


class DecisionResponse(BaseModel):
    id: str
    project_id: str
    project_name: Optional[str] = None
    title: str
    decision_type: str
    description: Optional[str] = None
    decision_status: str
    priority: str
    created_by: str
    created_by_name: Optional[str] = None
    decision_maker_id: Optional[str] = None
    decision_maker_name: Optional[str] = None
    created_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    source_type: Optional[str] = None
    source_reference_id: Optional[str] = None
    source_recommendation_id: Optional[str] = None
    source_prediction_id: Optional[str] = None
    source_issue_id: Optional[str] = None
    source_task_id: Optional[str] = None
    source_resource_request_id: Optional[str] = None
    observed_facts: List[Dict[str, Any]] = Field(default_factory=list)
    prediction_summary: Optional[Dict[str, Any]] = None
    recommendation_summary: Optional[Dict[str, Any]] = None
    alternatives: List[Dict[str, Any]] = Field(default_factory=list)
    selected_action: Optional[str] = None
    decision_rationale: Optional[str] = None
    affected_entities: List[Dict[str, Any]] = Field(default_factory=list)
    expected_impact: Optional[str] = None
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)
