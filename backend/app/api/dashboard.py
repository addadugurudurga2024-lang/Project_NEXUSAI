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
    """Return live dashboard metrics from MongoDB scoped to current user."""
    role = current_user.get("role", "team_member")
    uid = str(current_user["_id"])
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # Scoped projects matching authoritative scoping logic
    from app.services.project_scoping_service import get_authorized_projects, get_authorized_employee_ids
    projects = await get_authorized_projects(db, current_user)
    project_ids = [str(p["_id"]) for p in projects]

    # Project counts
    total_projects = len(projects)
    active_projects = sum(1 for p in projects if p.get("status") == "active")
    completed_projects = sum(1 for p in projects if p.get("status") == "completed")
    on_hold = sum(1 for p in projects if p.get("status") == "on_hold")

    # Risk overview from latest predictions
    valid_obj_ids = [ObjectId(x) for x in project_ids if ObjectId.is_valid(x)]
    pred_query = {
        "$or": [
            {"project_id": {"$in": project_ids}},
            {"project_id": {"$in": valid_obj_ids}},
        ]
    } if project_ids else {"_id": None}
    predictions = await db.project_predictions.find(pred_query).to_list(500)
    high_risk = sum(1 for p in predictions if p.get("risk_class") == "HIGH" or p.get("risk_level") == "HIGH")
    medium_risk = sum(1 for p in predictions if p.get("risk_class") == "MEDIUM" or p.get("risk_level") == "MEDIUM")
    low_risk = sum(1 for p in predictions if p.get("risk_class") == "LOW" or p.get("risk_level") == "LOW")

    # Employee stats
    if role == "admin":
        total_employees = await db.employees.count_documents({"status": "active"})
        burnout_preds = await db.employee_risk_predictions.find({}).to_list(200)
        high_burnout = sum(1 for p in burnout_preds if p.get("risk_level") == "HIGH")
        medium_burnout = sum(1 for p in burnout_preds if p.get("risk_level") == "MEDIUM")
    elif role == "project_manager":
        # Scoped strictly to PM's line-managed active Team Capacity members (Authoritative)
        active_mems = await db.team_memberships.find({"pm_user_id": uid, "status": "active"}).to_list(200)
        scoped_eids = [m["employee_id"] for m in active_mems]

        total_employees = len(scoped_eids)
        if scoped_eids:
            burnout_preds = await db.employee_risk_predictions.find({"employee_id": {"$in": scoped_eids}}).to_list(200)
            high_burnout = sum(1 for p in burnout_preds if p.get("risk_level") == "HIGH")
            medium_burnout = sum(1 for p in burnout_preds if p.get("risk_level") == "MEDIUM")
        else:
            high_burnout = 0
            medium_burnout = 0
    else:
        emp_ids = await get_authorized_employee_ids(db, current_user)
        total_employees = len(emp_ids)
        if emp_ids:
            burnout_preds = await db.employee_risk_predictions.find({"employee_id": {"$in": emp_ids}}).to_list(200)
            high_burnout = sum(1 for p in burnout_preds if p.get("risk_level") == "HIGH")
            medium_burnout = sum(1 for p in burnout_preds if p.get("risk_level") == "MEDIUM")
        else:
            high_burnout = 0
            medium_burnout = 0

    # Issue stats
    if role == "team_member":
        emp = await db.employees.find_one({"$or": [{"user_id": uid}, {"email": current_user.get("email")}]})
        possible_ids = [uid] + ([str(emp["_id"])] if emp else [])
        open_issues = await db.issues.count_documents({"assignee_id": {"$in": possible_ids}, "status": "open"})
        critical_issues = await db.issues.count_documents({"assignee_id": {"$in": possible_ids}, "severity": "critical", "status": "open"})
    elif project_ids or role == "admin":
        issue_query = {"project_id": {"$in": project_ids}} if project_ids else {}
        open_issues = await db.issues.count_documents({**issue_query, "status": "open"})
        critical_issues = await db.issues.count_documents({**issue_query, "severity": "critical", "status": "open"})
    else:
        open_issues = 0
        critical_issues = 0

    # Budget at-risk projects (only for Admin/PM, not exposed to Team Members)
    budget_risk_count = 0
    total_budget = 0
    total_expenditure = 0
    if role in ("admin", "project_manager"):
        active_projects_list = [p for p in projects if p.get("status") == "active"]
        for p in active_projects_list:
            b = p.get("budget", 0)
            e = p.get("current_expenditure", 0)
            total_budget += b
            total_expenditure += e
            if b > 0 and e / b > 0.85:
                budget_risk_count += 1

    # Task stats
    if role == "team_member":
        emp = await db.employees.find_one({"$or": [{"user_id": uid}, {"email": current_user.get("email")}]})
        possible_ids = [uid] + ([str(emp["_id"])] if emp else [])
        total_tasks = await db.tasks.count_documents({"assignee_id": {"$in": possible_ids}})
        overdue_tasks = await db.tasks.count_documents({
            "assignee_id": {"$in": possible_ids},
            "status": {"$nin": ["done"]},
            "due_date": {"$lt": today}
        })
    elif project_ids or role == "admin":
        task_query = {"project_id": {"$in": project_ids}} if project_ids else {}
        total_tasks = await db.tasks.count_documents(task_query)
        overdue_tasks = await db.tasks.count_documents({
            **task_query,
            "status": {"$nin": ["done"]},
            "due_date": {"$lt": today}
        })
    else:
        total_tasks = 0
        overdue_tasks = 0

    # Recent recommendations (scoped)
    rec_query = {"project_id": {"$in": project_ids}} if project_ids else ({} if role == "admin" else {"_id": None})
    recent_recs = await db.recommendations.find(rec_query).sort("created_at", -1).to_list(5)
    for r in recent_recs:
        r["id"] = str(r["_id"])
        del r["_id"]

    # Recent issues (scoped)
    if role == "team_member":
        emp = await db.employees.find_one({"$or": [{"user_id": uid}, {"email": current_user.get("email")}]})
        possible_ids = [uid] + ([str(emp["_id"])] if emp else [])
        recent_issues = await db.issues.find({"assignee_id": {"$in": possible_ids}, "status": "open"}).sort("created_at", -1).to_list(5)
    elif project_ids or role == "admin":
        issue_query = {"project_id": {"$in": project_ids}} if project_ids else {}
        recent_issues = await db.issues.find({**issue_query, "status": "open"}).sort("created_at", -1).to_list(5)
    else:
        recent_issues = []
    for i in recent_issues:
        i["id"] = str(i["_id"])
        del i["_id"]

    # Notifications (scoped to user_id or linked emp_id)
    emp = await db.employees.find_one({"$or": [{"user_id": uid}, {"email": current_user.get("email")}]})
    emp_id = str(emp["_id"]) if emp else None
    notif_uids = [uid] + ([emp_id] if emp_id else [])
    unread_notifications = await db.notifications.count_documents({
        "$and": [
            {"$or": [{"userId": {"$in": notif_uids}}, {"user_id": {"$in": notif_uids}}]},
            {"$or": [{"isRead": False}, {"read": False}]}
        ]
    })

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
    """Get project risk overview for authorized projects."""
    from app.services.project_scoping_service import get_authorized_projects
    projects = await get_authorized_projects(db, current_user)
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
    emp = await db.employees.find_one({"$or": [{"user_id": user_id}, {"email": current_user.get("email")}]})
    emp_id = str(emp["_id"]) if emp else None
    id_list = [user_id] + ([emp_id] if emp_id else [])

    query = {"$or": [{"userId": {"$in": id_list}}, {"user_id": {"$in": id_list}}]}
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
            "related_issue_id": str(n.get("relatedIssueId") or n.get("related_issue_id", "") or ""),
            "assigned_by": str(n.get("assigned_by") or ""),
            "assigned_by_name": n.get("assigned_by_name"),
            "severity": n.get("severity", "medium"),
            "is_read": n.get("isRead") if "isRead" in n else (n.get("read") if "read" in n else False),
            "created_at": n.get("createdAt") or n.get("created_at"),
        })
    return result


@router.get("/notifications/unread-count")
async def get_unread_count(
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    user_id = str(current_user["_id"])
    emp = await db.employees.find_one({"$or": [{"user_id": user_id}, {"email": current_user.get("email")}]})
    emp_id = str(emp["_id"]) if emp else None
    id_list = [user_id] + ([emp_id] if emp_id else [])

    count = await db.notifications.count_documents({
        "$and": [
            {"$or": [{"userId": {"$in": id_list}}, {"user_id": {"$in": id_list}}]},
            {"$or": [{"isRead": False}, {"read": False}]}
        ]
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
    emp = await db.employees.find_one({"$or": [{"user_id": user_id}, {"email": current_user.get("email")}]})
    emp_id = str(emp["_id"]) if emp else None
    id_list = [user_id] + ([emp_id] if emp_id else [])

    await db.notifications.update_many(
        {"$or": [{"userId": {"$in": id_list}}, {"user_id": {"$in": id_list}}]},
        {"$set": {"isRead": True, "read": True}}
    )
    return {"message": "All notifications marked as read"}


@router.get("/velocity")
async def get_team_velocity(
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Aggregate actual story points from completed tasks per sprint in authorized projects."""
    from app.services.project_scoping_service import get_authorized_project_ids
    role = current_user.get("role", "team_member")
    if role == "admin":
        sprints = await db.sprints.find({}).sort("start_date", 1).to_list(10)
    else:
        authorized_pids = await get_authorized_project_ids(db, current_user)
        valid_pids = [ObjectId(p) for p in authorized_pids if ObjectId.is_valid(p)]
        sprints = await db.sprints.find({"project_id": {"$in": authorized_pids + valid_pids}}).sort("start_date", 1).to_list(10)

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

