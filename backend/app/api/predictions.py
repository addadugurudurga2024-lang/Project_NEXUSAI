from fastapi import APIRouter, Depends, HTTPException
from app.core.deps import get_current_user
from app.db.database import get_database
# pyrefly: ignore [missing-import]
from bson import ObjectId
from datetime import datetime
import sys
import os

# Add parent directory to path for ML module access
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

router = APIRouter()


async def _gather_project_features(project_id: str, db) -> dict:
    """Gather features from MongoDB for ML inference."""
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Gather task statistics
    tasks = await db.tasks.find({"project_id": project_id}).to_list(1000)
    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t.get("status") == "done")
    overdue_tasks = sum(1 for t in tasks if t.get("due_date") and t.get("status") not in ["done"] and t.get("due_date") < datetime.utcnow().strftime("%Y-%m-%d"))
    high_priority_tasks = sum(1 for t in tasks if t.get("priority") in ["high", "critical"])

    # Sprint statistics
    sprints = await db.sprints.find({"project_id": project_id}).to_list(100)
    completed_sprints = [s for s in sprints if s.get("status") == "completed"]
    avg_velocity = 0.0
    if completed_sprints:
        velocities = [s.get("velocity", 0) for s in completed_sprints]
        avg_velocity = sum(velocities) / len(velocities) if velocities else 0

    # Issue statistics
    issues = await db.issues.find({"project_id": project_id}).to_list(500)
    total_bugs = len(issues)
    critical_issues = sum(1 for i in issues if i.get("severity") == "critical")
    open_issues = sum(1 for i in issues if i.get("status") == "open")

    # Budget metrics
    budget = project.get("budget", 1)
    expenditure = project.get("current_expenditure", 0)
    budget_utilization = (expenditure / budget * 100) if budget > 0 else 0

    # Schedule metrics
    progress = project.get("progress", 0)
    task_completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    remaining_work = 100 - progress

    # Team workload (from employees assigned)
    team_ids = project.get("team_member_ids", [])
    total_assigned_hours = 0.0
    total_capacity_hours = 0.0
    for emp_id in team_ids:
        try:
            emp = await db.employees.find_one({"_id": ObjectId(emp_id)})
            if emp:
                total_capacity_hours += emp.get("weekly_capacity_hours", 40)
        except Exception:
            pass
    emp_tasks = await db.tasks.find({"project_id": project_id, "status": {"$nin": ["done"]}}).to_list(500)
    for t in emp_tasks:
        total_assigned_hours += t.get("estimated_hours", 0)
    team_workload = (total_assigned_hours / total_capacity_hours * 100) if total_capacity_hours > 0 else 50

    return {
        "project": project,
        "features": {
            "progress": float(progress),
            "task_completion_rate": float(task_completion_rate),
            "overdue_tasks": int(overdue_tasks),
            "avg_sprint_velocity": float(avg_velocity),
            "total_bugs": int(total_bugs),
            "critical_issues": int(critical_issues),
            "open_issues": int(open_issues),
            "team_workload": float(team_workload),
            "budget_utilization": float(budget_utilization),
            "remaining_work": float(remaining_work),
            "high_priority_tasks": int(high_priority_tasks),
            "total_tasks": int(total_tasks),
            "team_size": len(team_ids),
        }
    }


@router.post("/project/{project_id}")
async def predict_project_risk(
    project_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Run full project intelligence pipeline: risk, delay, budget, health."""
    from ml.inference.project_risk import predict_project_risk_inference
    from ml.inference.deadline_delay import predict_deadline_delay
    from ml.inference.budget_overrun import predict_budget_overrun
    from ml.inference.project_health import calculate_project_health

    gathered = await _gather_project_features(project_id, db)
    features = gathered["features"]
    project = gathered["project"]

    # Run inference
    risk_result = predict_project_risk_inference(features)
    delay_result = predict_deadline_delay(features, project)
    budget_result = predict_budget_overrun(features, project)
    health_result = calculate_project_health(features, project, risk_result, delay_result, budget_result)

    # Persist prediction
    prediction_doc = {
        "project_id": project_id,
        "project_name": project.get("name"),
        "risk_class": risk_result["risk_class"],
        "risk_probability": risk_result["risk_probability"],
        "risk_factors": risk_result["contributing_factors"],
        "delay_days": delay_result["delay_days"],
        "delay_probability": delay_result["delay_probability"],
        "delay_factors": delay_result["contributing_factors"],
        "budget_overrun_amount": budget_result["overrun_amount"],
        "budget_overrun_risk": budget_result["overrun_risk"],
        "predicted_final_cost": budget_result["predicted_final_cost"],
        "budget_factors": budget_result["contributing_factors"],
        "health_score": health_result["health_score"],
        "health_status": health_result["health_status"],
        "health_breakdown": health_result["breakdown"],
        "features_used": features,
        "model_name": risk_result.get("model_name", "RandomForest"),
        "model_version": risk_result.get("model_version", "1.0"),
        "is_demo": risk_result.get("is_demo", True),
        "created_at": datetime.utcnow(),
    }

    await db.project_predictions.replace_one(
        {"project_id": project_id},
        prediction_doc,
        upsert=True,
    )

    # Generate notifications for high risk
    if risk_result["risk_class"] == "HIGH":
        await db.notifications.insert_one({
            "type": "high_risk_project",
            "title": f"High Risk Alert: {project.get('name')}",
            "message": f"Project {project.get('name')} has been flagged as HIGH RISK ({risk_result['risk_probability']:.0%} probability).",
            "project_id": project_id,
            "severity": "critical",
            "read": False,
            "created_at": datetime.utcnow(),
        })

    return prediction_doc


@router.get("/project/{project_id}/latest")
async def get_project_prediction(
    project_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    pred = await db.project_predictions.find_one({"project_id": project_id})
    if not pred:
        raise HTTPException(status_code=404, detail="No prediction found. Run prediction first.")
    pred["id"] = str(pred["_id"])
    del pred["_id"]
    return pred
