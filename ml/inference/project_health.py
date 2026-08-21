"""
Project Health Calculation Module
Composite health score derived from meaningful project indicators.

Formula:
health_score = (
    progress_score * 0.25
    + schedule_score * 0.20
    + budget_score * 0.20
    + issue_score * 0.20
    + risk_score * 0.15
)
"""
from typing import Dict, Any


def calculate_project_health(
    features: Dict[str, Any],
    project: dict,
    risk_result: dict,
    delay_result: dict,
    budget_result: dict,
) -> Dict[str, Any]:

    progress = features.get("progress", 0)
    task_completion = features.get("task_completion_rate", 0)
    overdue_tasks = features.get("overdue_tasks", 0)
    critical_issues = features.get("critical_issues", 0)
    open_issues = features.get("open_issues", 0)
    budget_utilization = features.get("budget_utilization", 0)
    remaining_work = features.get("remaining_work", 100)

    # 1. Progress Score (0–100): actual vs expected progress
    progress_score = min(100, max(0, progress))
    if task_completion < progress:
        progress_score = progress_score * 0.8  # penalize task lag

    # 2. Schedule Score (0–100): based on delay probability
    delay_prob = delay_result.get("delay_probability", 0)
    delay_days = delay_result.get("delay_days", 0)
    schedule_score = max(0, 100 - (delay_prob * 60) - min(30, delay_days * 1.5))

    # 3. Budget Score (0–100): based on overrun risk and utilization
    budget_score = 100
    overrun_risk = budget_result.get("overrun_risk", "LOW")
    if overrun_risk == "HIGH":
        budget_score = max(20, 100 - budget_utilization * 0.8)
    elif overrun_risk == "MEDIUM":
        budget_score = max(40, 100 - budget_utilization * 0.4)
    else:
        budget_score = max(60, 100 - max(0, budget_utilization - 80) * 1.5)

    # 4. Issue Score (0–100): penalize open and critical issues
    issue_score = max(0, 100 - critical_issues * 15 - min(25, open_issues * 3))

    # 5. Risk Score (0–100): from ML risk probability
    risk_prob = risk_result.get("risk_probability", 0)
    risk_class = risk_result.get("risk_class", "LOW")
    if risk_class == "HIGH":
        risk_score = max(10, 50 - risk_prob * 40)
    elif risk_class == "MEDIUM":
        risk_score = max(40, 80 - risk_prob * 30)
    else:
        risk_score = max(70, 100 - risk_prob * 20)

    # Weighted composite
    health_score = (
        progress_score * 0.25
        + schedule_score * 0.20
        + budget_score * 0.20
        + issue_score * 0.20
        + risk_score * 0.15
    )
    health_score = round(max(0, min(100, health_score)), 1)

    # Health status label
    if health_score >= 80:
        health_status = "EXCELLENT"
    elif health_score >= 65:
        health_status = "GOOD"
    elif health_score >= 45:
        health_status = "FAIR"
    elif health_score >= 25:
        health_status = "AT RISK"
    else:
        health_status = "CRITICAL"

    return {
        "health_score": health_score,
        "health_status": health_status,
        "breakdown": {
            "progress_score": round(progress_score, 1),
            "schedule_score": round(schedule_score, 1),
            "budget_score": round(budget_score, 1),
            "issue_score": round(issue_score, 1),
            "risk_score": round(risk_score, 1),
        },
        "formula_note": "health = progress×0.25 + schedule×0.20 + budget×0.20 + issues×0.20 + risk×0.15",
    }
