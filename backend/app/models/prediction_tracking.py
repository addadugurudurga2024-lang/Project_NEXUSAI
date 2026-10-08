from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum


class PredictionType(str, Enum):
    PROJECT_RISK = "PROJECT_RISK"
    DEADLINE_DELAY = "DEADLINE_DELAY"
    BUDGET_OVERRUN = "BUDGET_OVERRUN"
    EMPLOYEE_BURNOUT = "EMPLOYEE_BURNOUT"


class OutcomeStatus(str, Enum):
    PENDING = "PENDING"
    AVAILABLE = "AVAILABLE"
    EVALUATED = "EVALUATED"
    UNAVAILABLE = "UNAVAILABLE"


class PredictionAuditEntry(BaseModel):
    action: str
    performed_by_id: str
    performed_by_name: str
    timestamp: datetime
    previous_status: Optional[str] = None
    new_status: str
    source: Optional[str] = None
    notes: Optional[str] = None
    previous_actual_value: Optional[Any] = None
    new_actual_value: Optional[Any] = None


class OutcomeRecordRequest(BaseModel):
    actual_value: Optional[Any] = None
    actual_class: Optional[str] = None
    actual_numeric_value: Optional[float] = None
    actual_unit: Optional[str] = None
    source: Optional[str] = "manual_observation"
    notes: Optional[str] = None
    observed_at: Optional[datetime] = None
    status: Optional[OutcomeStatus] = OutcomeStatus.EVALUATED


class PredictionRecord(BaseModel):
    id: Optional[str] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None
    prediction_type: str
    model_name: str
    model_version: str
    prediction_timestamp: datetime
    prediction_value: Any
    prediction_unit: Optional[str] = None
    prediction_class: Optional[str] = None
    prediction_numeric_value: Optional[float] = None
    prediction_features_snapshot: Dict[str, Any] = Field(default_factory=dict)
    prediction_context_snapshot: Optional[Dict[str, Any]] = None
    target_date: Optional[str] = None
    outcome_status: str = OutcomeStatus.PENDING.value
    outcome_id: Optional[str] = None
    outcome_recorded_at: Optional[datetime] = None
    actual_value: Optional[Any] = None
    actual_class: Optional[str] = None
    actual_numeric_value: Optional[float] = None
    actual_unit: Optional[str] = None
    error_value: Optional[float] = None
    absolute_error: Optional[float] = None
    percentage_error: Optional[float] = None
    evaluation_status: str = OutcomeStatus.PENDING.value
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ModelPerformanceMetrics(BaseModel):
    model_name: str
    prediction_type: str
    total_predictions: int = 0
    evaluated_count: int = 0
    pending_count: int = 0
    unavailable_count: int = 0
    # Numeric regression metrics
    mae: Optional[float] = None
    median_absolute_error: Optional[float] = None
    rmse: Optional[float] = None
    mean_error_bias: Optional[float] = None
    # Classification metrics
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    # Sample safety
    sample_size_status: str = "NO_EVALUATED_DATA"  # "SUFFICIENT", "LIMITED_SAMPLE", "NO_EVALUATED_DATA"
    sample_size_warning: Optional[str] = None
    evaluation_note: Optional[str] = None


class TrajectoryPoint(BaseModel):
    id: str
    timestamp: datetime
    prediction_value: Any
    prediction_class: Optional[str] = None
    prediction_numeric_value: Optional[float] = None
    actual_value: Optional[Any] = None
    actual_class: Optional[str] = None
    evaluation_status: str
    error_value: Optional[float] = None


class TrajectoryResponse(BaseModel):
    project_id: str
    project_name: Optional[str] = None
    prediction_type: str
    trajectory_direction: str  # "IMPROVING", "DETERIORATING", "STABLE", "INSUFFICIENT_DATA"
    history: List[TrajectoryPoint] = Field(default_factory=list)
