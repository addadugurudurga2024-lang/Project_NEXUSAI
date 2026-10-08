"""
Employee Risk API — Burnout & Workload Risk prediction endpoints.
Routes align with what the frontend actually calls.
"""
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


def _build_recommendation(risk_level: str, workload_stats: dict, employee_name: str) -> str:
    """Generate dynamic text recommendation based on risk level and workload stats."""
    wl = workload_stats
    utilization = wl.get("workload_ratio", 0)
    available_hours = max(0, wl.get("weekly_capacity", 40) - wl.get("estimated_hours", 0))
    overdue = wl.get("overdue_tasks", 0)
    active = wl.get("active_tasks", 0)

    if risk_level == "HIGH":
        return (
            f"{employee_name} is showing high workload stress ({utilization:.0f}% utilization, "
            f"{overdue} overdue task(s)). Immediately reassign non-critical tasks and consider "
            f"blocking new assignments until workload drops below 90%."
        )
    elif risk_level == "MEDIUM":
        if available_hours > 0:
            return (
                f"{employee_name} can accept limited additional work ({available_hours:.1f}h available), "
                f"but avoid assigning multiple high-priority tasks simultaneously. Monitor weekly."
            )
        else:
            return (
                f"{employee_name} is near full capacity ({utilization:.0f}%). "
                f"Avoid adding new tasks this sprint. Review {overdue} overdue item(s) first."
            )
    else:
        return (
            f"{employee_name} has manageable workload ({utilization:.0f}% utilization, "
            f"{available_hours:.1f}h available). Suitable for additional task assignment "
            f"matching their skill set."
        )


async def _run_and_persist_prediction(employee_id: str, db) -> dict:
    """Core prediction logic shared by all prediction endpoints."""
    from ml.inference.burnout_risk import predict_burnout_risk

    gathered = await _gather_employee_features(employee_id, db)
    features = gathered["features"]
    employee = gathered["employee"]
    workload_stats = gathered["workload_stats"]

    # Run ML inference
    burnout_result = predict_burnout_risk(features)
    employee_name = employee.get("name", "Employee")

    recommendation = _build_recommendation(
        burnout_result["risk_level"], workload_stats, employee_name
    )

    prediction_doc = {
        "employee_id": employee_id,
        "employee_name": employee_name,
        "risk_level": burnout_result["risk_level"],
        "risk_probability": burnout_result["risk_probability"],
        "contributing_factors": burnout_result["contributing_factors"],
        "workload_stats": workload_stats,
        "features_used": features,
        "model_name": burnout_result.get("model_name", "RandomForestClassifier"),
        "model_version": burnout_result.get("model_version", "1.0"),
        "is_demo": burnout_result.get("is_demo", True),
        "recommendation": recommendation,
        "disclaimer": (
            "This is a workload-based burnout risk indicator. "
            "It is NOT a medical or psychological diagnosis."
        ),
        "created_at": datetime.utcnow(),
    }

    await db.employee_risk_predictions.replace_one(
        {"employee_id": employee_id},
        prediction_doc,
        upsert=True,
    )

    # Record immutable prediction snapshot for outcome tracking & ML performance evaluation
    try:
        from app.services.prediction_tracking_service import record_prediction_snapshot
        await record_prediction_snapshot(
            db=db,
            prediction_type="EMPLOYEE_BURNOUT",
            model_name=burnout_result.get("model_name", "RandomForestClassifier"),
            model_version=burnout_result.get("model_version", "1.0"),
            prediction_value=burnout_result["risk_level"],
            prediction_class=burnout_result["risk_level"],
            prediction_numeric_value=burnout_result.get("risk_probability"),
            prediction_unit="category",
            features=features,
            entity_id=employee_id,
            entity_name=employee_name,
            context={"factors": burnout_result.get("contributing_factors", []), "workload_stats": workload_stats},
        )
    except Exception as snap_err:
        print(f"Warning: employee burnout snapshot recording failed: {snap_err}")

    # Generate notification for high risk (notify managers/admins)
    if burnout_result["risk_level"] == "HIGH":
        await db.notifications.insert_one({
            "type": "high_burnout_risk",
            "title": f"Burnout Risk Alert: {employee_name}",
            "message": (
                f"{employee_name} has been flagged with HIGH burnout risk "
                f"(workload: {workload_stats['workload_ratio']:.0f}%)."
            ),
            "employee_id": employee_id,
            "severity": "high",
            "isRead": False,
            "read": False,
            "createdAt": datetime.utcnow(),
            "created_at": datetime.utcnow(),
        })

    return prediction_doc


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES
async def _check_employee_access(db, employee_id: str, current_user: dict):
    """Enforces authoritative PM / Team Member scoping on employee risk operations."""
    role = current_user.get("role", "team_member")
    if role in ("project_manager", "team_member"):
        from app.services.project_scoping_service import get_authorized_employee_ids
        authorized_eids = await get_authorized_employee_ids(db, current_user)
        if str(employee_id) not in authorized_eids:
            raise HTTPException(
                status_code=403,
                detail="Access denied: Employee not in your authorized scope"
            )


# ─────────────────────────────────────────────────────────────────────────────

@router.get("/workload")
async def get_all_employee_workload(
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Get workload summary for active employees scoped to current user."""
    role = current_user.get("role", "team_member")
    query = {"status": "active"}

    if role in ("project_manager", "team_member"):
        from app.services.project_scoping_service import get_authorized_employee_ids
        authorized_eids = await get_authorized_employee_ids(db, current_user)
        valid_objs = [ObjectId(x) for x in authorized_eids if ObjectId.is_valid(x)]
        query["_id"] = {"$in": valid_objs} if valid_objs else {"_id": None}

    employees = await db.employees.find(query).to_list(500)
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
    """Run burnout risk prediction for an employee (canonical endpoint)."""
    await _check_employee_access(db, employee_id, current_user)
    return await _run_and_persist_prediction(employee_id, db)


@router.post("/analyze/{employee_id}")
async def analyze_workload_risk(
    employee_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """
    Analyze workload risk for an employee.
    Frontend-facing alias for POST /employee/{employee_id}.
    Returns richer response including workload details for the UI panel.
    """
    await _check_employee_access(db, employee_id, current_user)
    prediction = await _run_and_persist_prediction(employee_id, db)

    # Return the full enriched response for the frontend workload panel
    ws = prediction["workload_stats"]
    return {
        **prediction,
        "workload": {
            "assigned_hours": ws.get("estimated_hours", 0),
            "weekly_capacity": ws.get("weekly_capacity", 40),
            "utilization_pct": round(ws.get("workload_ratio", 0), 1),
            "available_hours": max(0, ws.get("weekly_capacity", 40) - ws.get("estimated_hours", 0)),
            "overtime_hours": ws.get("overtime_hours", 0),
        },
        "tasks": {
            "total": ws.get("active_tasks", 0) + ws.get("completed_tasks", 0),
            "active": ws.get("active_tasks", 0),
            "completed": ws.get("completed_tasks", 0),
            "overdue": ws.get("overdue_tasks", 0),
            "high_priority": ws.get("high_priority_tasks", 0),
        },
        "risk": {
            "level": prediction["risk_level"],
            "probability": prediction["risk_probability"],
        },
    }


@router.get("/employee/{employee_id}/latest")
async def get_employee_prediction(
    employee_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Get the latest stored prediction for an employee."""
    await _check_employee_access(db, employee_id, current_user)
    pred = await db.employee_risk_predictions.find_one({"employee_id": employee_id})
    if not pred:
        raise HTTPException(
            status_code=404,
            detail="No prediction found. Click 'Analyze Workload Risk' to run analysis."
        )
    pred["id"] = str(pred["_id"])
    del pred["_id"]
    return pred


@router.get("/{employee_id}/latest")
async def get_employee_prediction_alias(
    employee_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """
    Alias: GET /{employee_id}/latest
    Frontend calls this URL; maps to the canonical /employee/{employee_id}/latest.
    """
    await _check_employee_access(db, employee_id, current_user)
    pred = await db.employee_risk_predictions.find_one({"employee_id": employee_id})
    if not pred:
        raise HTTPException(
            status_code=404,
            detail="No prediction found. Click 'Analyze Workload Risk' to run analysis."
        )
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
    await _check_employee_access(db, employee_id, current_user)
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
