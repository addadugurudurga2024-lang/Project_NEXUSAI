"""
Analytics API — Phase 7: Advanced Analytics & Executive Intelligence

Routes (all RBAC-enforced at backend):
  GET /analytics/executive   — Executive summary (admin/manager only)
  GET /analytics/projects    — Project performance analytics (admin/manager only)
  GET /analytics/team        — Team/employee analytics (admin/manager only)
  GET /analytics/risks       — Consolidated ML risk analytics (admin/manager only)
  GET /analytics/trends      — Time-based trend data (admin/manager only)
  GET /analytics/insights    — Dynamically computed insights (admin/manager only)

RBAC:
  - admin: org-wide access
  - project_manager: their projects/team members only
  - team_member: 403 on all endpoints (enforce at backend, not just frontend)
"""
from fastapi import APIRouter, Depends, HTTPException
from app.core.deps import get_current_user, require_manager_or_admin
from app.db.database import get_database
# pyrefly: ignore [missing-import]
from bson import ObjectId
from datetime import datetime, timedelta
from typing import List

router = APIRouter()


def _str_id(doc: dict) -> str:
    return str(doc["_id"])


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


from app.services.project_scoping_service import (
    get_authorized_projects,
    get_authorized_project_ids,
    get_authorized_employee_ids,
)


async def _get_manager_project_ids(db, user_id: str) -> List[str]:
    """Return list of project ID strings managed by this PM."""
    projects = await db.projects.find(
        {"$or": [{"project_manager_id": user_id}, {"manager_id": user_id}]}
    ).to_list(500)
    return [str(p["_id"]) for p in projects]


async def _get_scoped_projects(db, current_user: dict):
    """Return projects visible to the current user via authoritative scoping service."""
    return await get_authorized_projects(db, current_user)


async def _get_scoped_employee_ids(db, current_user: dict, projects: list) -> List[str]:
    """Return employee IDs belonging to authorized scope."""
    return await get_authorized_employee_ids(db, current_user, projects)



# ─────────────────────────────────────────────────────────────────────────────
# GET /analytics/executive
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/executive")
async def get_executive_analytics(
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    High-level org (admin) or PM-scoped executive metrics.
    Strictly forbidden for team_member role.
    """
    role = current_user.get("role")
    today = _today()
    projects = await _get_scoped_projects(db, current_user)
    project_ids = [str(p["_id"]) for p in projects]

    # Project counts
    total_projects = len(projects)
    active_projects = sum(1 for p in projects if p.get("status") == "active")
    completed_projects = sum(1 for p in projects if p.get("status") == "completed")
    on_hold = sum(1 for p in projects if p.get("status") == "on_hold")
    overdue_projects = sum(
        1 for p in projects
        if p.get("status") not in ("completed",) and p.get("end_date") and p["end_date"] < today
    )

    avg_progress = (
        sum(p.get("progress", 0) for p in projects) / total_projects
        if total_projects else 0
    )

    # Budget
    total_budget = sum(p.get("budget", 0) for p in projects)
    total_spent = sum(p.get("current_expenditure", 0) for p in projects)
    budget_util = (total_spent / total_budget * 100) if total_budget > 0 else 0

    # Tasks (scoped)
    if not project_ids and role != "admin":
        total_tasks = 0
        completed_tasks = 0
        inprog_tasks = 0
        overdue_tasks = 0
        open_issues = 0
        critical_issues = 0
        high_risk = 0
        medium_risk = 0
        low_risk = 0
    else:
        task_query = {"project_id": {"$in": project_ids}} if project_ids else {}
        total_tasks = await db.tasks.count_documents(task_query)
        completed_tasks = await db.tasks.count_documents({**task_query, "status": "done"})
        inprog_tasks = await db.tasks.count_documents({**task_query, "status": "in_progress"})
        overdue_tasks = await db.tasks.count_documents({
            **task_query,
            "status": {"$nin": ["done"]},
            "due_date": {"$lt": today}
        })

        # Issues (scoped)
        issue_query = {"project_id": {"$in": project_ids}} if project_ids else {}
        open_issues = await db.issues.count_documents({**issue_query, "status": "open"})
        critical_issues = await db.issues.count_documents({**issue_query, "severity": "critical", "status": "open"})

        # ML predictions (scoped to project_ids)
        valid_obj_ids = [ObjectId(x) for x in project_ids if ObjectId.is_valid(x)]
        pred_query = {
            "$or": [
                {"project_id": {"$in": project_ids}},
                {"project_id": {"$in": valid_obj_ids}},
            ]
        } if project_ids else {"_id": None}
        preds = await db.project_predictions.find(pred_query).to_list(500)
        high_risk = sum(1 for p in preds if p.get("risk_class") == "HIGH" or p.get("risk_level") == "HIGH")
        medium_risk = sum(1 for p in preds if p.get("risk_class") == "MEDIUM" or p.get("risk_level") == "MEDIUM")
        low_risk = sum(1 for p in preds if p.get("risk_class") == "LOW" or p.get("risk_level") == "LOW")


    # Employee burnout (scoped)
    emp_ids = await _get_scoped_employee_ids(db, current_user, projects)
    if emp_ids or role == "admin":
        emp_query = {"employee_id": {"$in": emp_ids}} if emp_ids else {}
        burnout_preds = await db.employee_risk_predictions.find(emp_query).to_list(500)
    else:
        burnout_preds = []
    high_burnout = sum(1 for b in burnout_preds if b.get("risk_level") == "HIGH")
    medium_burnout = sum(1 for b in burnout_preds if b.get("risk_level") == "MEDIUM")
    total_employees = len(emp_ids)

    return {
        "projects": {
            "total": total_projects,
            "active": active_projects,
            "completed": completed_projects,
            "on_hold": on_hold,
            "overdue": overdue_projects,
            "avg_progress": round(avg_progress, 1),
            "high_risk": high_risk,
            "medium_risk": medium_risk,
            "low_risk": low_risk,
        },
        "tasks": {
            "total": total_tasks,
            "completed": completed_tasks,
            "in_progress": inprog_tasks,
            "overdue": overdue_tasks,
        },
        "issues": {
            "open": open_issues,
            "critical": critical_issues,
        },
        "budget": {
            "total_allocated": total_budget,
            "total_spent": total_spent,
            "utilization_percent": round(budget_util, 1),
        },
        "employees": {
            "total": total_employees,
            "high_burnout_risk": high_burnout,
            "medium_burnout_risk": medium_burnout,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /analytics/projects
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/projects")
async def get_project_analytics(
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    Per-project performance metrics including task completion, issue stats,
    budget utilization, and existing ML prediction outputs.
    """
    today = _today()
    projects = await _get_scoped_projects(db, current_user)
    if not projects:
        return []

    pids = [str(p["_id"]) for p in projects]
    pid_objs = [ObjectId(p) for p in pids if ObjectId.is_valid(p)]

    # Batch task aggregation
    task_agg = await db.tasks.aggregate([
        {"$match": {"$or": [{"project_id": {"$in": pids}}, {"project_id": {"$in": pid_objs}}]}},
        {"$group": {
            "_id": "$project_id",
            "total": {"$sum": 1},
            "done": {"$sum": {"$cond": [{"$eq": ["$status", "done"]}, 1, 0]}},
            "in_progress": {"$sum": {"$cond": [{"$eq": ["$status", "in_progress"]}, 1, 0]}},
            "overdue": {"$sum": {"$cond": [
                {"$and": [
                    {"$ne": ["$status", "done"]},
                    {"$lt": ["$due_date", today]}
                ]},
                1, 0
            ]}}
        }}
    ]).to_list(len(pids) + 50)
    task_map = {str(item["_id"]): item for item in task_agg}

    # Batch issue aggregation
    issue_agg = await db.issues.aggregate([
        {"$match": {"$or": [{"project_id": {"$in": pids}}, {"project_id": {"$in": pid_objs}}]}},
        {"$group": {
            "_id": "$project_id",
            "open": {"$sum": {"$cond": [{"$eq": ["$status", "open"]}, 1, 0]}},
            "resolved": {"$sum": {"$cond": [{"$eq": ["$status", "resolved"]}, 1, 0]}}
        }}
    ]).to_list(len(pids) + 50)
    issue_map = {str(item["_id"]): item for item in issue_agg}

    # Batch predictions
    preds = await db.project_predictions.find({
        "$or": [{"project_id": {"$in": pids}}, {"project_id": {"$in": pid_objs}}]
    }).to_list(len(pids) + 50)
    pred_map = {str(pr.get("project_id")): pr for pr in preds}

    result = []
    for p in projects:
        pid = str(p["_id"])
        t_stat = task_map.get(pid, {})
        i_stat = issue_map.get(pid, {})
        pred = pred_map.get(pid)

        total_tasks = t_stat.get("total", 0)
        done_tasks = t_stat.get("done", 0)
        inprog_tasks = t_stat.get("in_progress", 0)
        overdue_tasks = t_stat.get("overdue", 0)

        open_issues = i_stat.get("open", 0)
        resolved_issues = i_stat.get("resolved", 0)

        budget = float(p.get("budget", 0) or 0)
        spent = float(p.get("current_expenditure", 0) or 0)
        budget_util = round((spent / budget * 100), 1) if budget > 0 else 0

        completion_rate = round((done_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0

        risk_val = (pred.get("risk_class") or pred.get("risk_level")) if pred else None
        delay_val = (pred.get("delay_days") if pred.get("delay_days") is not None else pred.get("predicted_delay_days")) if pred else None
        budget_risk_val = (pred.get("budget_overrun_risk") or pred.get("budget_risk")) if pred else None

        result.append({
            "project_id": pid,
            "name": p.get("name", ""),
            "status": p.get("status", ""),
            "priority": p.get("priority", ""),
            "progress": p.get("progress", 0),
            "start_date": p.get("start_date"),
            "end_date": p.get("end_date"),
            "tasks": {
                "total": total_tasks,
                "completed": done_tasks,
                "in_progress": inprog_tasks,
                "overdue": overdue_tasks,
                "completion_rate": completion_rate,
            },
            "issues": {
                "open": open_issues,
                "resolved": resolved_issues,
            },
            "budget": {
                "allocated": budget,
                "spent": spent,
                "utilization_percent": budget_util,
            },
            "ml": {
                "risk_class": risk_val,
                "risk_probability": pred.get("risk_probability") if pred else None,
                "health_score": pred.get("health_score") if pred else None,
                "delay_days": delay_val,
                "delay_probability": pred.get("delay_probability") if pred else None,
                "budget_overrun_risk": budget_risk_val,
                "budget_overrun_amount": pred.get("budget_overrun_amount") if pred else None,
            },
        })

    return result


# ─────────────────────────────────────────────────────────────────────────────
# GET /analytics/team
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/team")
async def get_team_analytics(
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    Team-level analytics: workload distribution, task completion per employee,
    burnout risk from existing ML predictions.
    Only admin/PM can access. Team member data is scoped to PM's projects.
    """
    today = _today()
    projects = await _get_scoped_projects(db, current_user)
    emp_ids = await _get_scoped_employee_ids(db, current_user, projects)

    if not emp_ids:
        return {"employees": [], "summary": {"total": 0, "above_capacity": 0, "high_risk": 0}}

    emps = await db.employees.find(
        {"_id": {"$in": [ObjectId(eid) for eid in emp_ids]}}
    ).to_list(len(emp_ids) + 50)

    eid_strs = [str(e["_id"]) for e in emps]
    eid_objs = [e["_id"] for e in emps]

    task_agg = await db.tasks.aggregate([
        {"$match": {"$or": [
            {"assignee_id": {"$in": eid_strs}},
            {"assignee_id": {"$in": eid_objs}},
            {"assigned_to": {"$in": eid_strs}},
            {"assigned_to": {"$in": eid_objs}},
        ]}},
        {"$group": {
            "_id": "$assignee_id",
            "total": {"$sum": 1},
            "done": {"$sum": {"$cond": [{"$eq": ["$status", "done"]}, 1, 0]}},
            "active": {"$sum": {"$cond": [{"$ne": ["$status", "done"]}, 1, 0]}},
            "overdue": {"$sum": {"$cond": [
                {"$and": [
                    {"$ne": ["$status", "done"]},
                    {"$lt": ["$due_date", today]}
                ]},
                1, 0
            ]}},
            "assigned_hours": {"$sum": {"$cond": [
                {"$ne": ["$status", "done"]},
                {"$ifNull": ["$estimated_hours", 0]},
                0
            ]}}
        }}
    ]).to_list(len(eid_strs) + 50)
    task_map = {str(item["_id"]): item for item in task_agg}

    burnout_preds = await db.employee_risk_predictions.find({
        "$or": [{"employee_id": {"$in": eid_strs}}, {"employee_id": {"$in": eid_objs}}]
    }).to_list(len(eid_strs) + 50)
    burnout_map = {str(b.get("employee_id")): b for b in burnout_preds}

    result = []
    above_capacity = 0
    high_risk_count = 0
    total_workload = 0

    for emp in emps:
        emp_id = str(emp["_id"])
        cap = emp.get("weekly_capacity_hours", 40) or 40
        t_stat = task_map.get(emp_id, {})
        total_tasks = t_stat.get("total", 0)
        done_tasks = t_stat.get("done", 0)
        active_tasks = t_stat.get("active", 0)
        overdue_tasks = t_stat.get("overdue", 0)
        assigned_hours = t_stat.get("assigned_hours", 0.0)

        workload_ratio = round((assigned_hours / cap * 100), 1) if cap > 0 else 0

        burnout = burnout_map.get(emp_id)
        risk_level = burnout.get("risk_level", "LOW") if burnout else ("HIGH" if workload_ratio > 110 else "LOW")
        risk_prob = burnout.get("risk_probability", None) if burnout else None

        if workload_ratio > 100:
            above_capacity += 1
        if risk_level == "HIGH":
            high_risk_count += 1
        total_workload += workload_ratio

        completion_rate = round((done_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0

        result.append({
            "employee_id": emp_id,
            "name": emp.get("name", ""),
            "email": emp.get("email", ""),
            "role": emp.get("role", ""),
            "specialization": emp.get("specialization", ""),
            "weekly_capacity_hours": cap,
            "assigned_hours": round(assigned_hours, 1),
            "workload_ratio": workload_ratio,
            "tasks": {
                "total": total_tasks,
                "completed": done_tasks,
                "active": active_tasks,
                "overdue": overdue_tasks,
                "completion_rate": completion_rate,
            },
            "burnout": {
                "risk_level": risk_level,
                "risk_probability": risk_prob,
            },
        })

    avg_workload = round(total_workload / len(result), 1) if result else 0

    return {
        "employees": result,
        "summary": {
            "total": len(result),
            "above_capacity": above_capacity,
            "high_risk": high_risk_count,
            "avg_workload_ratio": avg_workload,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /analytics/risks
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/risks")
async def get_risk_analytics(
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    Consolidated risk/prediction analytics from existing Phase 5.5 ML predictions.
    No new ML models — purely reads existing prediction collections.
    """
    projects = await _get_scoped_projects(db, current_user)
    project_ids = [str(p["_id"]) for p in projects]
    emp_ids = await _get_scoped_employee_ids(db, current_user, projects)

    # Project predictions
    valid_obj_ids = [ObjectId(x) for x in project_ids if ObjectId.is_valid(x)]
    pred_query = {
        "$or": [
            {"project_id": {"$in": project_ids}},
            {"project_id": {"$in": valid_obj_ids}},
        ]
    } if project_ids else {"_id": None}
    proj_preds = await db.project_predictions.find(pred_query).to_list(2000)

    # Group by risk class
    risk_groups = {"HIGH": [], "MEDIUM": [], "LOW": [], "UNKNOWN": []}
    delayed_projects = []
    budget_overrun_projects = []

    # Build a lookup of project names
    proj_name_map = {str(p["_id"]): p.get("name", "") for p in projects}

    for pred in proj_preds:
        pid = str(pred.get("project_id", ""))
        name = proj_name_map.get(pid, pid)
        rc = pred.get("risk_class") or pred.get("risk_level") or "UNKNOWN"
        risk_groups.setdefault(rc, []).append({"project_id": pid, "name": name, "risk_probability": pred.get("risk_probability")})

        delay_days = pred.get("delay_days") if pred.get("delay_days") is not None else pred.get("predicted_delay_days", 0)
        delay_days = int(delay_days or 0)
        if delay_days > 0:
            delayed_projects.append({
                "project_id": pid,
                "name": name,
                "delay_days": delay_days,
                "delay_probability": pred.get("delay_probability"),
            })

        overrun = float(pred.get("budget_overrun_amount", 0) or 0)
        overrun_risk = pred.get("budget_overrun_risk") or pred.get("budget_risk") or "LOW"
        if overrun > 0 or overrun_risk in ("HIGH", "MEDIUM"):
            budget_overrun_projects.append({
                "project_id": pid,
                "name": name,
                "overrun_risk": overrun_risk,
                "overrun_amount": overrun,
            })

    delayed_projects.sort(key=lambda x: x["delay_days"], reverse=True)
    budget_overrun_projects.sort(key=lambda x: x["overrun_amount"], reverse=True)

    delay_values = [d["delay_days"] for d in delayed_projects]
    overrun_values = [o["overrun_amount"] for o in budget_overrun_projects]

    # Employee burnout predictions (scoped)
    if emp_ids or current_user.get("role") == "admin":
        burnout_preds = await db.employee_risk_predictions.find(
            {"employee_id": {"$in": emp_ids}} if emp_ids else {}
        ).to_list(6000)
    else:
        burnout_preds = []

    emp_risk_groups = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for b in burnout_preds:
        lvl = b.get("risk_level", "LOW")
        emp_risk_groups[lvl] = emp_risk_groups.get(lvl, 0) + 1

    return {
        "project_risk": {
            "high": len(risk_groups.get("HIGH", [])),
            "medium": len(risk_groups.get("MEDIUM", [])),
            "low": len(risk_groups.get("LOW", [])),
            "unknown": len(risk_groups.get("UNKNOWN", [])),
            "distribution": [
                {"name": "High Risk", "value": len(risk_groups.get("HIGH", [])), "color": "#ef4444"},
                {"name": "Medium Risk", "value": len(risk_groups.get("MEDIUM", [])), "color": "#f59e0b"},
                {"name": "Low Risk", "value": len(risk_groups.get("LOW", [])), "color": "#10b981"},
            ],
            "high_risk_projects": risk_groups.get("HIGH", []),
        },
        "employee_burnout": {
            "high": emp_risk_groups.get("HIGH", 0),
            "medium": emp_risk_groups.get("MEDIUM", 0),
            "low": emp_risk_groups.get("LOW", 0),
            "distribution": [
                {"name": "High Risk", "value": emp_risk_groups.get("HIGH", 0), "color": "#ef4444"},
                {"name": "Medium Risk", "value": emp_risk_groups.get("MEDIUM", 0), "color": "#f59e0b"},
                {"name": "Low Risk", "value": emp_risk_groups.get("LOW", 0), "color": "#10b981"},
            ],
        },
        "deadline": {
            "projects_with_delay": len(delayed_projects),
            "avg_delay_days": round(sum(delay_values) / len(delay_values), 1) if delay_values else 0,
            "max_delay_days": max(delay_values) if delay_values else 0,
            "details": delayed_projects[:10],
        },
        "budget_overrun": {
            "projects_at_risk": len(budget_overrun_projects),
            "avg_overrun_amount": round(sum(overrun_values) / len(overrun_values), 2) if overrun_values else 0,
            "max_overrun_amount": max(overrun_values) if overrun_values else 0,
            "details": budget_overrun_projects[:10],
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /analytics/trends
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/trends")
async def get_trend_analytics(
    days: int = 30,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    Time-series trend data from existing timestamped collections.
    Returns empty-state markers when data is insufficient — never fabricates data.
    """
    projects = await _get_scoped_projects(db, current_user)
    project_ids = [str(p["_id"]) for p in projects]

    now = datetime.utcnow()
    start_dt = now - timedelta(days=days)

    # Tasks completed over time (bucket by day)
    if not project_ids and current_user.get("role") != "admin":
        task_query = {"project_id": {"$in": []}}
        issue_query = {"project_id": {"$in": []}}
        activity_query = {"project_id": {"$in": []}}
    else:
        task_query = {"project_id": {"$in": project_ids}} if project_ids else {}
        issue_query = {"project_id": {"$in": project_ids}} if project_ids else {}
        activity_query = {"project_id": {"$in": project_ids}} if project_ids else {}

    all_done_tasks = await db.tasks.find({
        **task_query,
        "status": "done",
        "updated_at": {"$gte": start_dt}
    }).to_list(2000)

    # Tasks created over time
    all_created_tasks = await db.tasks.find({
        **task_query,
        "created_at": {"$gte": start_dt}
    }).to_list(2000)

    # Issues created/resolved over time
    all_created_issues = await db.issues.find({
        **issue_query,
        "created_at": {"$gte": start_dt}
    }).to_list(2000)
    all_resolved_issues = await db.issues.find({
        **issue_query,
        "status": "resolved",
        "resolved_at": {"$gte": start_dt}
    }).to_list(2000)

    # Activity events from project_activities
    activities = await db.project_activities.find({
        **activity_query,
        "timestamp": {"$gte": start_dt}
    }).to_list(2000)

    def bucket_by_day(docs, date_field: str) -> dict:
        """Count documents bucketed by date string."""
        buckets: dict = {}
        for doc in docs:
            val = doc.get(date_field)
            if not val:
                continue
            if isinstance(val, datetime):
                day_str = val.strftime("%Y-%m-%d")
            elif isinstance(val, str):
                day_str = val[:10]
            else:
                continue
            buckets[day_str] = buckets.get(day_str, 0) + 1
        return buckets

    # Build a continuous date range
    date_range = [(start_dt + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days + 1)]

    tasks_completed_map = bucket_by_day(all_done_tasks, "updated_at")
    tasks_created_map = bucket_by_day(all_created_tasks, "created_at")
    issues_created_map = bucket_by_day(all_created_issues, "created_at")
    issues_resolved_map = bucket_by_day(all_resolved_issues, "resolved_at")
    activities_map = bucket_by_day(activities, "timestamp")

    trend_series = []
    for day in date_range:
        trend_series.append({
            "date": day,
            "tasks_completed": tasks_completed_map.get(day, 0),
            "tasks_created": tasks_created_map.get(day, 0),
            "issues_created": issues_created_map.get(day, 0),
            "issues_resolved": issues_resolved_map.get(day, 0),
            "activities": activities_map.get(day, 0),
        })

    # Check whether there's meaningful data
    has_task_data = any(d["tasks_completed"] + d["tasks_created"] > 0 for d in trend_series)
    has_issue_data = any(d["issues_created"] + d["issues_resolved"] > 0 for d in trend_series)
    has_activity_data = any(d["activities"] > 0 for d in trend_series)

    return {
        "period_days": days,
        "start_date": start_dt.strftime("%Y-%m-%d"),
        "end_date": now.strftime("%Y-%m-%d"),
        "has_task_data": has_task_data,
        "has_issue_data": has_issue_data,
        "has_activity_data": has_activity_data,
        "series": trend_series,
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /analytics/insights
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/insights")
async def get_executive_insights(
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    Dynamically computed analytics-derived insight strings.
    All values sourced from live database — never hardcoded.
    """
    today = _today()
    projects = await _get_scoped_projects(db, current_user)
    project_ids = [str(p["_id"]) for p in projects]
    emp_ids = await _get_scoped_employee_ids(db, current_user, projects)
    proj_name_map = {str(p["_id"]): p.get("name", "Unnamed") for p in projects}

    insights = []
    timestamp_now = datetime.utcnow().isoformat()
    valid_obj_ids = [ObjectId(x) for x in project_ids if ObjectId.is_valid(x)]
    pred_query = {
        "$or": [
            {"project_id": {"$in": project_ids}},
            {"project_id": {"$in": valid_obj_ids}},
        ]
    } if project_ids else {"_id": None}

    # 1. High-risk projects
    high_risk_preds = await db.project_predictions.find({
        **pred_query,
        "$or": [{"risk_class": "HIGH"}, {"risk_level": "HIGH"}]
    }).to_list(100)
    if len(high_risk_preds) > 0:
        names = [proj_name_map.get(str(p.get("project_id", "")), str(p.get("project_id", ""))) for p in high_risk_preds[:3]]
        insights.append({
            "source": "ML_RISK_PREDICTIONS",
            "severity": "critical",
            "level": "critical",
            "entity_reference": names[0] if names else "Projects",
            "timestamp": timestamp_now,
            "text": f"{len(high_risk_preds)} project(s) are currently classified as high risk: {', '.join(names)}{'…' if len(high_risk_preds) > 3 else ''}.",
        })

    # 2. Overdue projects
    overdue_projs = [p for p in projects if p.get("status") not in ("completed",) and p.get("end_date") and str(p.get("end_date")) < today]
    if overdue_projs:
        pnames = [p.get("name", "Project") for p in overdue_projs[:2]]
        insights.append({
            "source": "PROJECT_SCHEDULE",
            "severity": "warning",
            "level": "warning",
            "entity_reference": pnames[0] if pnames else "Projects",
            "timestamp": timestamp_now,
            "text": f"{len(overdue_projs)} project(s) have passed their scheduled completion date ({', '.join(pnames)}).",
        })

    # 3. Severe workload overload (e.g. Alex Rodriguez at 300%)
    overloaded_emps = []
    task_load_agg = await db.tasks.aggregate([
        {"$match": {
            "$or": [
                {"assignee_id": {"$in": emp_ids}},
                {"assignee_id": {"$in": [ObjectId(eid) for eid in emp_ids if ObjectId.is_valid(eid)]}},
                {"assigned_to": {"$in": emp_ids}},
            ],
            "status": {"$nin": ["done"]}
        }},
        {"$group": {
            "_id": "$assignee_id",
            "total_hours": {"$sum": {"$ifNull": ["$estimated_hours", 0]}}
        }},
        {"$sort": {"total_hours": -1}},
        {"$limit": 20}
    ]).to_list(20)

    top_eids = [ObjectId(str(item["_id"])) for item in task_load_agg if ObjectId.is_valid(str(item["_id"]))]
    top_emps = await db.employees.find({"_id": {"$in": top_eids}}).to_list(len(top_eids))
    emp_map = {str(e["_id"]): e for e in top_emps}

    for item in task_load_agg:
        eid = str(item["_id"])
        emp = emp_map.get(eid)
        if not emp:
            continue
        cap = float(emp.get("weekly_capacity_hours", 40) or 40)
        hours = float(item["total_hours"])
        load_pct = (hours / cap * 100) if cap > 0 else 0
        if load_pct > 100:
            overloaded_emps.append({
                "name": emp.get("name", "Employee"),
                "hours": hours,
                "cap": cap,
                "load_pct": load_pct,
            })

    for o_emp in sorted(overloaded_emps, key=lambda x: x["load_pct"], reverse=True)[:2]:
        insights.append({
            "source": "RESOURCE_INTELLIGENCE",
            "severity": "critical" if o_emp["load_pct"] > 150 else "warning",
            "level": "critical" if o_emp["load_pct"] > 150 else "warning",
            "entity_reference": o_emp["name"],
            "timestamp": timestamp_now,
            "text": f"{o_emp['name']} is assigned at {o_emp['load_pct']:.0f}% of weekly capacity ({o_emp['hours']:.1f}h / {o_emp['cap']:.0f}h).",
        })

    # 4. Highest predicted delay (e.g. Gamma Data Warehouse at 24 days)
    delay_preds = await db.project_predictions.find({
        **pred_query,
        "$or": [{"delay_days": {"$gt": 0}}, {"predicted_delay_days": {"$gt": 0}}]
    }).sort([("delay_days", -1), ("predicted_delay_days", -1)]).to_list(5)

    if delay_preds:
        top_delay = delay_preds[0]
        dd = top_delay.get("delay_days") if top_delay.get("delay_days") is not None else top_delay.get("predicted_delay_days", 0)
        pname = proj_name_map.get(str(top_delay.get("project_id", "")), str(top_delay.get("project_id", "")))
        insights.append({
            "source": "ML_SCHEDULE_PREDICTOR",
            "severity": "warning",
            "level": "warning",
            "entity_reference": pname,
            "timestamp": timestamp_now,
            "text": f"{pname} has a predicted delay of {dd} days.",
        })

    # 5. Critical open issues
    issue_query = {"project_id": {"$in": project_ids}} if project_ids else {"_id": None}
    critical_issues = await db.issues.count_documents({
        **issue_query,
        "severity": "critical",
        "status": {"$nin": ["resolved", "closed"]},
    })
    if critical_issues > 0:
        insights.append({
            "source": "ISSUE_INTELLIGENCE",
            "severity": "critical",
            "level": "critical",
            "entity_reference": "System Issues",
            "timestamp": timestamp_now,
            "text": f"{critical_issues} critical issue(s) remain unresolved.",
        })

    # 6. Budget overruns
    overrun_preds = await db.project_predictions.find({
        **pred_query,
        "$or": [{"budget_overrun_risk": "HIGH"}, {"budget_risk": "HIGH"}]
    }).to_list(100)
    if overrun_preds:
        names = [proj_name_map.get(str(p.get("project_id", "")), str(p.get("project_id", ""))) for p in overrun_preds[:2]]
        insights.append({
            "source": "ML_BUDGET_PREDICTOR",
            "severity": "critical",
            "level": "critical",
            "entity_reference": names[0] if names else "Budget",
            "timestamp": timestamp_now,
            "text": f"{len(overrun_preds)} project(s) have HIGH predicted budget overrun risk: {', '.join(names)}.",
        })

    # 7. Positive insight — ONLY if truly all conditions are healthy
    has_critical_condition = bool(high_risk_preds or overloaded_emps or delay_preds or critical_issues > 0 or overrun_preds)
    if not insights and not has_critical_condition:
        insights.append({
            "source": "EXECUTIVE_SUMMARY",
            "severity": "info",
            "level": "info",
            "entity_reference": "All Projects",
            "timestamp": timestamp_now,
            "text": "All projects are within acceptable risk and schedule parameters.",
        })

    return {"insights": insights}
