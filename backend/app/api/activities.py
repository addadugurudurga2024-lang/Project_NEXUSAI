"""
Activities API — Phase 6
Provides read-only access to project activity timeline and employee work history.

Routes:
  GET /activities/project/{project_id}   — Project activity timeline (all authenticated users with access)
  GET /activities/employee/me            — Current user's own task/project/issue history (team members)
  GET /activities/employee/{employee_id} — Specific employee's history (admin/manager only)
"""
from fastapi import APIRouter, Depends, HTTPException
from app.core.deps import get_current_user, require_manager_or_admin
from app.db.database import get_database
# pyrefly: ignore [missing-import]
from bson import ObjectId
from datetime import datetime
from typing import Optional

router = APIRouter()


def _serialize_activity(a: dict) -> dict:
    return {
        "id": str(a["_id"]),
        "project_id": a.get("project_id", ""),
        "actor_user_id": a.get("actor_user_id", ""),
        "actor_name": a.get("actor_name", "System"),
        "activity_type": a.get("activity_type", ""),
        "message": a.get("message", ""),
        "related_entity_id": a.get("related_entity_id", ""),
        "timestamp": a.get("timestamp"),
    }


async def _get_employee_for_user(db, user_id: str) -> Optional[dict]:
    """Find the employee record linked to the given user_id."""
    return await db.employees.find_one({"user_id": user_id})


# ─────────────────────────────────────────────────────────────────────────────
# GET /activities/project/{project_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/project/{project_id}")
async def get_project_activities(
    project_id: str,
    limit: int = 50,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """
    Return the activity timeline for a project.
    RBAC: team_member must be a member of the project to view its activities.
    Admin and project_manager can view any project's activities.
    """
    role = current_user.get("role", "team_member")

    # Verify project exists
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # RBAC check for team_member
    if role == "team_member":
        emp = await _get_employee_for_user(db, str(current_user["_id"]))
        if not emp:
            raise HTTPException(status_code=403, detail="No employee profile linked to your account")
        emp_id = str(emp["_id"])
        if emp_id not in project.get("team_member_ids", []):
            raise HTTPException(status_code=403, detail="You are not a member of this project")

    activities = await db.project_activities.find(
        {"project_id": project_id}
    ).sort("timestamp", -1).to_list(limit)

    return [_serialize_activity(a) for a in activities]


# ─────────────────────────────────────────────────────────────────────────────
# GET /activities/employee/me
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/employee/me")
async def get_my_history(
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """
    Returns the current user's own work history:
    - Assigned projects
    - All tasks (grouped by status)
    - Assigned/resolved issues
    """
    user_id = str(current_user["_id"])
    emp = await _get_employee_for_user(db, user_id)

    if not emp:
        # Return empty history if no employee profile
        return {
            "employee_id": None,
            "projects": [],
            "tasks": {"todo": [], "in_progress": [], "done": [], "overdue": []},
            "issues": [],
        }

    emp_id = str(emp["_id"])
    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    # Assigned projects
    project_ids = emp.get("assigned_project_ids", [])
    # Also check team_member_ids in projects (in case assigned_project_ids is stale)
    extra_projects = await db.projects.find(
        {"team_member_ids": emp_id}
    ).to_list(100)
    extra_ids = [str(p["_id"]) for p in extra_projects]
    all_project_ids = list(set(project_ids + extra_ids))

    projects_data = []
    for pid in all_project_ids:
        try:
            proj = await db.projects.find_one({"_id": ObjectId(pid)})
            if proj:
                projects_data.append({
                    "id": str(proj["_id"]),
                    "name": proj.get("name", ""),
                    "status": proj.get("status", ""),
                    "priority": proj.get("priority", ""),
                    "progress": proj.get("progress", 0),
                    "end_date": proj.get("end_date"),
                })
        except Exception:
            pass

    # All tasks assigned to this employee
    all_tasks = await db.tasks.find({"assignee_id": emp_id}).to_list(300)
    tasks_grouped: dict = {"todo": [], "in_progress": [], "done": [], "overdue": []}

    for t in all_tasks:
        status = t.get("status", "todo")
        due_date = t.get("due_date")
        is_overdue = (
            status not in ("done",)
            and due_date is not None
            and due_date < today_str
        )

        task_obj = {
            "id": str(t["_id"]),
            "title": t.get("title", ""),
            "project_id": t.get("project_id", ""),
            "priority": t.get("priority", "medium"),
            "status": status,
            "due_date": due_date,
            "created_at": t.get("created_at"),
            "story_points": t.get("story_points", 0),
        }

        # Enrich with project name
        if t.get("project_id"):
            try:
                proj = await db.projects.find_one({"_id": ObjectId(t["project_id"])})
                if proj:
                    task_obj["project_name"] = proj.get("name", "")
            except Exception:
                pass

        if is_overdue:
            tasks_grouped["overdue"].append(task_obj)
        elif status in tasks_grouped:
            tasks_grouped[status].append(task_obj)
        else:
            tasks_grouped.setdefault(status, []).append(task_obj)

    # Issues assigned to or resolved by this employee
    assigned_issues = await db.issues.find({"assignee_id": emp_id}).to_list(100)
    issues_data = []
    for i in assigned_issues:
        issue_obj = {
            "id": str(i["_id"]),
            "title": i.get("title", ""),
            "project_id": i.get("project_id", ""),
            "severity": i.get("severity", "medium"),
            "status": i.get("status", "open"),
            "created_at": i.get("created_at"),
            "resolved_at": i.get("resolved_at"),
        }
        if i.get("project_id"):
            try:
                proj = await db.projects.find_one({"_id": ObjectId(i["project_id"])})
                if proj:
                    issue_obj["project_name"] = proj.get("name", "")
            except Exception:
                pass
        issues_data.append(issue_obj)

    return {
        "employee_id": emp_id,
        "employee_name": emp.get("name", ""),
        "projects": projects_data,
        "tasks": tasks_grouped,
        "issues": issues_data,
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /activities/employee/{employee_id}  — Admin/Manager only
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/employee/{employee_id}")
async def get_employee_history(
    employee_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    Returns work history for a specific employee.
    Only accessible to admins and project managers.
    """
    try:
        emp = await db.employees.find_one({"_id": ObjectId(employee_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid employee ID")
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    project_ids = emp.get("assigned_project_ids", [])
    extra_projects = await db.projects.find({"team_member_ids": employee_id}).to_list(100)
    extra_ids = [str(p["_id"]) for p in extra_projects]
    all_project_ids = list(set(project_ids + extra_ids))

    projects_data = []
    for pid in all_project_ids:
        try:
            proj = await db.projects.find_one({"_id": ObjectId(pid)})
            if proj:
                projects_data.append({
                    "id": str(proj["_id"]),
                    "name": proj.get("name", ""),
                    "status": proj.get("status", ""),
                    "priority": proj.get("priority", ""),
                    "progress": proj.get("progress", 0),
                    "end_date": proj.get("end_date"),
                })
        except Exception:
            pass

    all_tasks = await db.tasks.find({"assignee_id": employee_id}).to_list(300)
    tasks_grouped: dict = {"todo": [], "in_progress": [], "done": [], "overdue": []}

    for t in all_tasks:
        status = t.get("status", "todo")
        due_date = t.get("due_date")
        is_overdue = (
            status not in ("done",)
            and due_date is not None
            and due_date < today_str
        )
        task_obj = {
            "id": str(t["_id"]),
            "title": t.get("title", ""),
            "project_id": t.get("project_id", ""),
            "priority": t.get("priority", "medium"),
            "status": status,
            "due_date": due_date,
            "created_at": t.get("created_at"),
        }
        if t.get("project_id"):
            try:
                proj = await db.projects.find_one({"_id": ObjectId(t["project_id"])})
                if proj:
                    task_obj["project_name"] = proj.get("name", "")
            except Exception:
                pass

        if is_overdue:
            tasks_grouped["overdue"].append(task_obj)
        elif status in tasks_grouped:
            tasks_grouped[status].append(task_obj)
        else:
            tasks_grouped.setdefault(status, []).append(task_obj)

    assigned_issues = await db.issues.find({"assignee_id": employee_id}).to_list(100)
    issues_data = []
    for i in assigned_issues:
        issue_obj = {
            "id": str(i["_id"]),
            "title": i.get("title", ""),
            "project_id": i.get("project_id", ""),
            "severity": i.get("severity", "medium"),
            "status": i.get("status", "open"),
            "resolved_at": i.get("resolved_at"),
        }
        if i.get("project_id"):
            try:
                proj = await db.projects.find_one({"_id": ObjectId(i["project_id"])})
                if proj:
                    issue_obj["project_name"] = proj.get("name", "")
            except Exception:
                pass
        issues_data.append(issue_obj)

    return {
        "employee_id": employee_id,
        "employee_name": emp.get("name", ""),
        "projects": projects_data,
        "tasks": tasks_grouped,
        "issues": issues_data,
    }
