"""
Authoritative Project Scoping Service for NexusAI
Unifies project authorization across Projects, Analytics, Dashboard, AI Assistant, and Reporting.
"""
from typing import List, Dict, Any, Optional
# pyrefly: ignore [missing-import]
from bson import ObjectId


def _str_id(doc: dict) -> str:
    return str(doc["_id"])


async def get_authorized_projects(db, current_user: dict) -> List[dict]:
    """
    Returns the authoritative list of project documents authorized for the current user.
    RBAC Rules:
    - admin: Org-wide access to all projects
    - project_manager: Management access to all organization projects (consistent with Projects & Tasks APIs)
    - team_member: Scoped strictly to projects where their linked employee profile is in team_member_ids
    """
    role = current_user.get("role", "team_member")
    uid = str(current_user["_id"])
    email = current_user.get("email")

    if role in ("admin", "project_manager"):
        return await db.projects.find({}).to_list(500)

    # team_member: must resolve linked employee
    emp = await db.employees.find_one({"$or": [{"user_id": uid}, {"email": email}]})
    if not emp:
        return []

    emp_id = str(emp["_id"])
    possible_ids = [uid, emp_id]

    return await db.projects.find({
        "team_member_ids": {"$in": possible_ids}
    }).to_list(500)


async def get_authorized_project_ids(db, current_user: dict) -> List[str]:
    """Returns list of string project IDs authorized for the current user."""
    projects = await get_authorized_projects(db, current_user)
    return [_str_id(p) for p in projects]


async def get_authorized_employee_ids(db, current_user: dict, projects: Optional[List[dict]] = None) -> List[str]:
    """
    Returns list of string employee IDs authorized in the user's scope.
    - admin & project_manager: all active employees in organization
    - team_member: only their own employee profile
    """
    role = current_user.get("role", "team_member")
    uid = str(current_user["_id"])
    email = current_user.get("email")

    if role in ("admin", "project_manager"):
        emps = await db.employees.find({"status": "active"}).to_list(500)
        return [_str_id(e) for e in emps]

    emp = await db.employees.find_one({"$or": [{"user_id": uid}, {"email": email}]})
    return [_str_id(emp)] if emp else []
