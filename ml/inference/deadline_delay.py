"""
Deadline Delay Prediction Inference Module
"""
from typing import Dict, Any
from datetime import datetime


def predict_deadline_delay(features: Dict[str, Any], project: dict) -> Dict[str, Any]:
    """
    Predict deadline delay using heuristic analysis of project metrics.
    Can be replaced with a trained ML model.
    """
    progress = features.get("progress", 0)
    task_completion = features.get("task_completion_rate", 0)
    overdue_tasks = features.get("overdue_tasks", 0)
    remaining_work = features.get("remaining_work", 100)
    workload = features.get("team_workload", 50)
    critical_issues = features.get("critical_issues", 0)

    # Parse project dates
    start_date_str = project.get("start_date")
    end_date_str = project.get("end_date")

    delay_days = 0
    delay_probability = 0.0
    factors = []

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
            today = datetime.utcnow()
            days_remaining = max(0, (end_date - today).days)
            total_days = 1

            if start_date_str:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
                total_days = max(1, (end_date - start_date).days)

            # Progress vs schedule
            schedule_progress = max(0, min(100, ((total_days - days_remaining) / total_days) * 100))
            progress_gap = schedule_progress - progress

            if progress_gap > 20:
                delay_factor = progress_gap / 100
                delay_days += int(days_remaining * delay_factor * 1.2)
                factors.append(f"Progress {progress:.0f}% behind schedule ({schedule_progress:.0f}% expected)")

            if overdue_tasks > 0:
                delay_days += overdue_tasks * 2
                factors.append(f"{overdue_tasks} overdue tasks contributing to delay")

            if critical_issues > 0:
                delay_days += critical_issues * 3
                factors.append(f"{critical_issues} critical issues impacting timeline")

            if workload > 110:
                delay_days += int((workload - 100) / 10)
                factors.append(f"Team overloaded ({workload:.0f}% capacity)")

            # Probability based on multiple factors
            delay_probability = min(0.95, max(0.05,
                (delay_days / max(1, days_remaining)) * 0.5 +
                (overdue_tasks * 0.05) +
                (critical_issues * 0.08) +
                (max(0, progress_gap) / 200)
            ))

        except Exception as e:
            # Fallback without dates
            delay_days = overdue_tasks * 2 + critical_issues * 3
            delay_probability = min(0.9, overdue_tasks * 0.08 + critical_issues * 0.1)
            factors.append("Schedule analysis unavailable (date format issue)")
    else:
        # No end date set
        delay_days = overdue_tasks * 2
        delay_probability = min(0.5, overdue_tasks * 0.1)
        factors.append("No project deadline set — delay risk is estimated")

    if not factors:
        factors.append("Project appears on schedule")

    return {
        "delay_days": max(0, int(delay_days)),
        "delay_probability": round(delay_probability, 3),
        "contributing_factors": factors,
        "model_name": "HeuristicDelayEstimator",
        "is_demo": True,
        "inference_note": "Heuristic estimation. Replace with trained regression model for production.",
    }
