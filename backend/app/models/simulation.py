from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum


class ScenarioType(str, Enum):
    RESOURCE_ADD = "RESOURCE_ADD"
    RESOURCE_REMOVE = "RESOURCE_REMOVE"
    RESOURCE_REALLOCATION = "RESOURCE_REALLOCATION"
    TASK_REALLOCATION = "TASK_REALLOCATION"
    SCOPE_REDUCTION = "SCOPE_REDUCTION"
    SCHEDULE_CAPACITY_CHANGE = "SCHEDULE_CAPACITY_CHANGE"
    BUDGET_RESOURCE_CHANGE = "BUDGET_RESOURCE_CHANGE"


class SimulationRequest(BaseModel):
    project_id: str
    scenario_type: ScenarioType
    parameters: Dict[str, Any] = Field(default_factory=dict)


class SimulationComparisonMetric(BaseModel):
    metric_key: str
    label: str
    baseline_value: Any
    simulated_value: Any
    delta: Any
    unit: str = ""
    sentiment: str = "neutral"  # "positive", "negative", "neutral", "warning"
    description: Optional[str] = None


class SimulationStateSnapshot(BaseModel):
    team_size: int
    team_workload_pct: float
    total_capacity_hours: float
    total_assigned_hours: float
    total_tasks: int
    remaining_tasks: int
    overdue_tasks: int
    critical_issues: int
    open_issues: int
    progress: float
    budget: float
    current_expenditure: float
    budget_utilization_pct: float
    risk_class: str
    risk_probability: float
    delay_days: int
    delay_probability: float
    raw_delay_days: Optional[float] = None
    health_score: float
    health_status: str
    budget_overrun_amount: float
    budget_overrun_risk: str
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    employee_loads: List[Dict[str, Any]] = Field(default_factory=list)


class SimulationExplanation(BaseModel):
    what_changed: str
    why_it_changed: str
    what_improved: List[str] = Field(default_factory=list)
    what_worsened: List[str] = Field(default_factory=list)
    remaining_risks: List[str] = Field(default_factory=list)
    recommendations_resolved: List[str] = Field(default_factory=list)


class SimulationResult(BaseModel):
    simulation_id: str
    project_id: str
    project_name: str
    scenario_type: ScenarioType
    scenario_title: str
    scenario_description: str
    parameters_applied: Dict[str, Any]
    simulated_at: datetime
    baseline: SimulationStateSnapshot
    simulated: SimulationStateSnapshot
    comparison: List[SimulationComparisonMetric]
    explanation: SimulationExplanation
    warnings: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    is_live_mutation: bool = False  # Strictly False: In-memory simulation only


class SimulationProjectOptions(BaseModel):
    project_id: str
    project_name: str
    current_team_size: int
    current_workload_pct: float
    current_health_score: float
    team_members: List[Dict[str, Any]]
    active_tasks: List[Dict[str, Any]]
    detected_gaps: List[Dict[str, Any]]
    available_candidates: List[Dict[str, Any]]
