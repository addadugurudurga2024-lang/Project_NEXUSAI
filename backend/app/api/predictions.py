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
@router.post("/analyze/project/{project_id}")
async def predict_project_risk(
    project_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Run full project intelligence pipeline: risk, delay, budget, health, recommendations & notifications."""
    from ml.inference.project_risk import predict_project_risk_inference
    from ml.inference.deadline_delay import predict_deadline_delay
    from ml.inference.budget_overrun import predict_budget_overrun
    from ml.inference.project_health import calculate_project_health
    from app.services.notification_service import notify_project_stakeholders
    from app.services.recommendation_service import generate_project_recommendations
    from app.services.activity_service import create_activity

    gathered = await _gather_project_features(project_id, db)
    features = gathered["features"]
    project = gathered["project"]

    role = current_user.get("role", "team_member")
    uid = str(current_user["_id"])
    if role == "project_manager":
        mgr_id = str(project.get("manager_id") or project.get("project_manager_id") or project.get("created_by") or "")
        if mgr_id != uid:
            raise HTTPException(status_code=403, detail="Access denied: You do not manage this project")
    elif role == "team_member":
        emp = await db.employees.find_one({"$or": [{"user_id": uid}, {"email": current_user.get("email")}]})
        emp_id = str(emp["_id"]) if emp else ""
        team_ids = [str(x) for x in project.get("team_member_ids", [])]
        if uid not in team_ids and emp_id not in team_ids:
            raise HTTPException(status_code=403, detail="Access denied: You are not assigned to this project")

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

    # Record immutable prediction snapshots for outcome tracking & ML performance evaluation
    try:
        from app.services.prediction_tracking_service import record_prediction_snapshot
        # 1. Project Risk Snapshot
        await record_prediction_snapshot(
            db=db,
            prediction_type="PROJECT_RISK",
            model_name=risk_result.get("model_name", "RandomForestClassifier"),
            model_version=risk_result.get("model_version", "1.0"),
            prediction_value=risk_result["risk_class"],
            prediction_class=risk_result["risk_class"],
            prediction_numeric_value=risk_result.get("risk_probability"),
            prediction_unit="category",
            features=features,
            project_id=project_id,
            project_name=project.get("name"),
            context={"risk_factors": risk_result.get("contributing_factors", []), "risk_probability": risk_result.get("risk_probability")},
        )
        # 2. Deadline Delay Snapshot
        await record_prediction_snapshot(
            db=db,
            prediction_type="DEADLINE_DELAY",
            model_name=delay_result.get("model_name", "GradientBoostingRegressor"),
            model_version=delay_result.get("model_version", "1.0"),
            prediction_value=f"{delay_result['delay_days']} days",
            prediction_numeric_value=float(delay_result["delay_days"]),
            prediction_unit="days",
            features=features,
            project_id=project_id,
            project_name=project.get("name"),
            target_date=project.get("end_date"),
            context={"delay_factors": delay_result.get("contributing_factors", []), "delay_probability": delay_result.get("delay_probability")},
        )
        # 3. Budget Overrun Snapshot
        await record_prediction_snapshot(
            db=db,
            prediction_type="BUDGET_OVERRUN",
            model_name=budget_result.get("model_name", "GradientBoostingRegressor"),
            model_version=budget_result.get("model_version", "1.0"),
            prediction_value=f"${budget_result['overrun_amount']:,.2f}",
            prediction_numeric_value=float(budget_result["overrun_amount"]),
            prediction_class=budget_result.get("overrun_risk"),
            prediction_unit="USD",
            features=features,
            project_id=project_id,
            project_name=project.get("name"),
            context={"budget_factors": budget_result.get("contributing_factors", []), "predicted_final_cost": budget_result.get("predicted_final_cost")},
        )
    except Exception as snap_err:
        print(f"Warning: prediction snapshot recording failed: {snap_err}")

    # Automatically generate / refresh actionable explainable recommendations
    try:
        await generate_project_recommendations(project_id, db)
    except Exception as e:
        print(f"Warning: recommendation generation failed: {e}")

    # Generate authoritative database notifications for high risk
    if risk_result["risk_class"] == "HIGH":
        await notify_project_stakeholders(
            db=db,
            project_id=project_id,
            notification_type="high_risk_project",
            title=f"High Risk Alert: {project.get('name')}",
            message=f"Project {project.get('name')} has been flagged as HIGH RISK ({risk_result['risk_probability']:.0%} probability). Delay: {delay_result['delay_days']} days.",
            severity="critical",
        )
    elif budget_result["overrun_risk"] == "HIGH":
        await notify_project_stakeholders(
            db=db,
            project_id=project_id,
            notification_type="budget_overrun_risk",
            title=f"Budget Risk Alert: {project.get('name')}",
            message=f"Project {project.get('name')} has high forecasted budget overrun of ${budget_result['overrun_amount']:,.2f}.",
            severity="high",
        )

    # Record activity in timeline
    try:
        actor_name = current_user.get("name") if current_user else "System"
        actor_id = str(current_user["_id"]) if current_user else "system"
        await create_activity(
            db=db,
            project_id=project_id,
            activity_type="AI_ANALYSIS_COMPLETED",
            message=f"AI Analysis completed for '{project.get('name')}': Health Score {health_result['health_score']}/100 ({health_result['health_status']}), Risk {risk_result['risk_class']}",
            actor_user_id=actor_id,
            actor_name=actor_name,
            related_entity_id=project_id,
        )
    except Exception:
        pass

    return prediction_doc


@router.get("/project/{project_id}/latest")
@router.get("/projects/{project_id}/latest")
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
