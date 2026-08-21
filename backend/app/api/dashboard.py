from fastapi import APIRouter, Depends, HTTPException
from app.core.deps import get_current_user
from app.db.database import get_database
from datetime import datetime
# pyrefly: ignore [missing-import]
from bson import ObjectId

router = APIRouter()


@router.get("/summary")
async def get_dashboard_summary(
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Return live dashboard metrics from MongoDB."""
    # Project counts
    total_projects = await db.projects.count_documents({})
    active_projects = await db.projects.count_documents({"status": "active"})
    completed_projects = await db.projects.count_documents({"status": "completed"})
    on_hold = await db.projects.count_documents({"status": "on_hold"})

    # Risk overview from latest predictions
    predictions = await db.project_predictions.find({}).to_list(200)
    high_risk = sum(1 for p in predictions if p.get("risk_class") == "HIGH")
    medium_risk = sum(1 for p in predictions if p.get("risk_class") == "MEDIUM")
    low_risk = sum(1 for p in predictions if p.get("risk_class") == "LOW")

    # Employee stats
    total_employees = await db.employees.count_documents({"status": "active"})
    burnout_preds = await db.employee_risk_predictions.find({}).to_list(200)
    high_burnout = sum(1 for p in burnout_preds if p.get("risk_level") == "HIGH")
    medium_burnout = sum(1 for p in burnout_preds if p.get("risk_level") == "MEDIUM")

    # Issue stats
    open_issues = await db.issues.count_documents({"status": "open"})
    critical_issues = await db.issues.count_documents({"severity": "critical", "status": "open"})

    # Budget at-risk projects
    all_projects = await db.projects.find({"status": "active"}).to_list(200)
    budget_risk_count = 0
    total_budget = 0
    total_expenditure = 0
    for p in all_projects:
        budget = p.get("budget", 0)
        expenditure = p.get("current_expenditure", 0)
        total_budget += budget
        total_expenditure += expenditure
        if budget > 0 and expenditure / budget > 0.85:
            budget_risk_count += 1

    # Task stats
    total_tasks = await db.tasks.count_documents({})
    overdue_tasks = await db.tasks.count_documents({
        "status": {"$nin": ["done"]},
        "due_date": {"$lt": datetime.utcnow().strftime("%Y-%m-%d")}
    })

    # Recent recommendations
    recent_recs = await db.recommendations.find({}).sort("created_at", -1).to_list(5)
    for r in recent_recs:
        r["id"] = str(r["_id"])
        del r["_id"]

    # Recent issues
    recent_issues = await db.issues.find({"status": "open"}).sort("created_at", -1).to_list(5)
    for i in recent_issues:
        i["id"] = str(i["_id"])
        del i["_id"]

    # Notifications
    unread_notifications = await db.notifications.count_documents({"read": False})

    return {
        "projects": {
            "total": total_projects,
            "active": active_projects,
            "completed": completed_projects,
            "on_hold": on_hold,
            "high_risk": high_risk,
            "medium_risk": medium_risk,
            "low_risk": low_risk,
        },
        "employees": {
            "total": total_employees,
            "high_burnout_risk": high_burnout,
            "medium_burnout_risk": medium_burnout,
        },
        "issues": {
            "open": open_issues,
            "critical": critical_issues,
        },
        "budget": {
            "total_allocated": total_budget,
            "total_spent": total_expenditure,
            "budget_risk_projects": budget_risk_count,
            "utilization_percent": (total_expenditure / total_budget * 100) if total_budget > 0 else 0,
        },
        "tasks": {
            "total": total_tasks,
            "overdue": overdue_tasks,
        },
        "notifications": {
            "unread": unread_notifications,
        },
        "recent_recommendations": recent_recs,
        "recent_issues": recent_issues,
    }


@router.get("/risk-overview")
async def get_risk_overview(
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Get project risk overview for all projects."""
    projects = await db.projects.find({}).to_list(200)
    result = []
    for p in projects:
        pid = str(p["_id"])
        pred = await db.project_predictions.find_one({"project_id": pid})
        result.append({
            "project_id": pid,
            "project_name": p.get("name"),
            "status": p.get("status"),
            "priority": p.get("priority"),
            "progress": p.get("progress", 0),
            "risk_class": pred.get("risk_class") if pred else "UNKNOWN",
            "risk_probability": pred.get("risk_probability") if pred else None,
            "health_score": pred.get("health_score") if pred else None,
            "delay_days": pred.get("delay_days") if pred else None,
        })
    return result


@router.get("/notifications")
async def get_notifications(
    unread_only: bool = False,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    user_id = str(current_user["_id"])
    query = {"$or": [{"userId": user_id}, {"user_id": user_id}]}
    if unread_only:
        query["$and"] = [{"$or": [{"isRead": False}, {"read": False}]}]
    notifications = await db.notifications.find(query).sort("createdAt", -1).to_list(100)
    result = []
    for n in notifications:
        result.append({
            "id": str(n["_id"]),
            "type": n.get("type"),
            "title": n.get("title"),
            "message": n.get("message"),
            "related_project_id": str(n.get("relatedProjectId") or n.get("related_project_id", "") or ""),
            "severity": n.get("severity", "medium"),
            "is_read": n.get("isRead") or n.get("read") or False,
            "created_at": n.get("createdAt") or n.get("created_at"),
        })
    return result


@router.get("/notifications/unread-count")
async def get_unread_count(
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    user_id = str(current_user["_id"])
    count = await db.notifications.count_documents({
        "$or": [{"userId": user_id}, {"user_id": user_id}],
        "$or": [{"isRead": False}, {"read": False}],
    })
    return {"unread_count": count}


@router.put("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    try:
        await db.notifications.update_one(
            {"_id": ObjectId(notification_id)},
            {"$set": {"isRead": True, "read": True}}
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid notification ID")
    return {"message": "Marked as read"}


@router.put("/notifications/read-all")
async def mark_all_read(
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    user_id = str(current_user["_id"])
    await db.notifications.update_many(
        {"$or": [{"userId": user_id}, {"user_id": user_id}]},
        {"$set": {"isRead": True, "read": True}}
    )
    return {"message": "All notifications marked as read"}


@router.get("/velocity")
async def get_team_velocity(
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Aggregate actual story points from completed tasks per sprint."""
    sprints = await db.sprints.find({}).sort("start_date", 1).to_list(10)
    velocity_data = []
    
    for sprint in sprints:
        sprint_id = str(sprint["_id"])
        # Find all completed tasks in this sprint
        tasks = await db.tasks.find({
            "sprint_id": sprint_id,
            "status": "done"
        }).to_list(100)
        
        # Calculate total story points (estimated_hours acting as points here)
        points = sum(task.get("estimated_hours", 0) for task in tasks)
        
        velocity_data.append({
            "sprint": sprint.get("name", f"Sprint {sprint_id[:4]}"),
            "points": points
        })
        
    return velocity_data

