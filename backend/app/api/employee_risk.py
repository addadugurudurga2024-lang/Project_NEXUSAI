from fastapi import APIRouter, Depends, HTTPException
from app.core.deps import get_current_user
from app.db.database import get_database
# pyrefly: ignore [missing-import]
from bson import ObjectId
from datetime import datetime
router = APIRouter()

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))


async def _gather_employee_features(employee_id: str, db) -> dict:
    """Gather workload features for an employee from MongoDB."""
    try:
        employee = await db.employees.find_one({"_id": ObjectId(employee_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid employee ID")
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # All tasks assigned to employee
    tasks = await db.tasks.find({"assignee_id": employee_id}).to_list(500)
    active_tasks = [t for t in tasks if t.get("status") not in ["done"]]
    completed_tasks = [t for t in tasks if t.get("status") == "done"]
    overdue_tasks = [
        t for t in active_tasks
        if t.get("due_date") and t.get("due_date") < datetime.utcnow().strftime("%Y-%m-%d")
    ]
    high_priority_tasks = [t for t in active_tasks if t.get("priority") in ["high", "critical"]]

    # Hours
    estimated_hours = sum(t.get("estimated_hours", 0) for t in active_tasks)
    actual_hours = sum(t.get("actual_hours", 0) for t in tasks)
    weekly_capacity = employee.get("weekly_capacity_hours", 40)
    overtime_hours = max(0, estimated_hours - weekly_capacity)
    workload_ratio = (estimated_hours / weekly_capacity * 100) if weekly_capacity > 0 else 0

    # Active projects
    active_project_ids = list(set(t.get("project_id") for t in active_tasks if t.get("project_id")))
    assigned_project_ids = employee.get("assigned_project_ids", [])

    # Sprint load
    sprint_tasks = [t for t in active_tasks if t.get("sprint_id")]
    sprint_story_points = sum(t.get("story_points", 0) for t in sprint_tasks)

    # Completion rate
    total_all = len(tasks)
    completion_rate = (len(completed_tasks) / total_all * 100) if total_all > 0 else 100

    features = {
        "workload_ratio": float(workload_ratio),
        "estimated_hours": float(estimated_hours),
        "overtime_hours": float(overtime_hours),
        "active_projects": len(active_project_ids),
        "active_task_count": len(active_tasks),
        "overdue_task_count": len(overdue_tasks),
        "sprint_story_points": float(sprint_story_points),
        "completion_rate": float(completion_rate),
        "high_priority_task_count": len(high_priority_tasks),
        "weekly_capacity": float(weekly_capacity),
    }

    return {
        "employee": employee,
        "features": features,
        "workload_stats": {
            "weekly_capacity": weekly_capacity,
            "estimated_hours": estimated_hours,
            "actual_hours": actual_hours,
            "overtime_hours": overtime_hours,
            "workload_ratio": workload_ratio,
            "active_tasks": len(active_tasks),
            "completed_tasks": len(completed_tasks),
            "overdue_tasks": len(overdue_tasks),
            "active_projects": len(active_project_ids),
            "completion_rate": completion_rate,
            "high_priority_tasks": len(high_priority_tasks),
        }
    }


@router.get("/workload")
async def get_all_employee_workload(
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Get workload summary for all active employees."""
    employees = await db.employees.find({"status": "active"}).to_list(200)
    result = []
    for emp in employees:
        emp_id = str(emp["_id"])
        try:
            gathered = await _gather_employee_features(emp_id, db)
            result.append({
                "employee_id": emp_id,
                "name": emp.get("name"),
                "role": emp.get("role"),
                "specialization": emp.get("specialization"),
                "skills": emp.get("skills", []),
                **gathered["workload_stats"],
            })
        except Exception:
            pass
    result.sort(key=lambda x: x["workload_ratio"], reverse=True)
    return result


@router.post("/employee/{employee_id}")
async def predict_employee_burnout(
    employee_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Run burnout risk prediction for an employee."""
    from ml.inference.burnout_risk import predict_burnout_risk

    gathered = await _gather_employee_features(employee_id, db)
    features = gathered["features"]
    employee = gathered["employee"]
    workload_stats = gathered["workload_stats"]

    # Run inference
    burnout_result = predict_burnout_risk(features)

    # Persist
    prediction_doc = {
        "employee_id": employee_id,
        "employee_name": employee.get("name"),
        "risk_level": burnout_result["risk_level"],
        "risk_probability": burnout_result["risk_probability"],
        "contributing_factors": burnout_result["contributing_factors"],
        "workload_stats": workload_stats,
        "features_used": features,
        "model_name": burnout_result.get("model_name", "RandomForest"),
        "model_version": burnout_result.get("model_version", "1.0"),
        "is_demo": burnout_result.get("is_demo", True),
        "disclaimer": "This is a workload-based burnout risk indicator. It is NOT a medical or psychological diagnosis.",
        "created_at": datetime.utcnow(),
    }

    await db.employee_risk_predictions.replace_one(
        {"employee_id": employee_id},
        prediction_doc,
        upsert=True,
    )

    # Generate notification if high risk
    if burnout_result["risk_level"] == "HIGH":
        await db.notifications.insert_one({
            "type": "high_burnout_risk",
            "title": f"Burnout Risk Alert: {employee.get('name')}",
            "message": f"{employee.get('name')} has been flagged with HIGH burnout risk (workload: {workload_stats['workload_ratio']:.0f}%).",
            "employee_id": employee_id,
            "severity": "high",
            "read": False,
            "created_at": datetime.utcnow(),
        })

    return prediction_doc


@router.get("/employee/{employee_id}/latest")
async def get_employee_prediction(
    employee_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    pred = await db.employee_risk_predictions.find_one({"employee_id": employee_id})
    if not pred:
        raise HTTPException(status_code=404, detail="No prediction found. Run prediction first.")
    pred["id"] = str(pred["_id"])
    del pred["_id"]
    return pred


@router.get("/employee/{employee_id}/workload")
async def get_employee_workload(
    employee_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Get detailed workload for a specific employee."""
    gathered = await _gather_employee_features(employee_id, db)
    employee = gathered["employee"]
    return {
        "employee_id": employee_id,
        "name": employee.get("name"),
        "role": employee.get("role"),
        "specialization": employee.get("specialization"),
        "skills": employee.get("skills", []),
        **gathered["workload_stats"],
        "features": gathered["features"],
    }
