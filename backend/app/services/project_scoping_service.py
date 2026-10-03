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
    - project_manager: Strictly scoped to projects managed by this Project Manager (manager_id / project_manager_id == user._id)
    - team_member: Scoped strictly to projects where their linked employee profile is in team_member_ids
    """
    role = current_user.get("role", "team_member")
    uid = str(current_user["_id"])
    email = current_user.get("email")

    if role == "admin":
        return await db.projects.find({}).to_list(2000)

    if role == "project_manager":
        valid_obj_ids = [ObjectId(uid)] if ObjectId.is_valid(uid) else []
        return await db.projects.find({
            "$or": [
                {"manager_id": uid},
                {"manager_id": {"$in": valid_obj_ids}},
                {"project_manager_id": uid},
                {"created_by": uid},
            ]
        }).to_list(2000)

    # team_member: must resolve linked employee
    emp = await db.employees.find_one({"$or": [{"user_id": uid}, {"email": email}]})
    if not emp:
        return []

    emp_id = str(emp["_id"])
    valid_emp_objs = [emp["_id"]] if isinstance(emp["_id"], ObjectId) else []
    possible_ids = [uid, emp_id] + valid_emp_objs

    return await db.projects.find({
        "team_member_ids": {"$in": possible_ids}
    }).to_list(2000)


async def get_authorized_project_ids(db, current_user: dict) -> List[str]:
    """Returns list of string project IDs authorized for the current user."""
    projects = await get_authorized_projects(db, current_user)
    return [_str_id(p) for p in projects]


async def get_authorized_employee_ids(db, current_user: dict, projects: Optional[List[dict]] = None) -> List[str]:
    """
    Returns list of string employee IDs authorized in the user's scope.
    - admin: all active employees in organization
    - project_manager: employees assigned to any of the PM's managed projects
    - team_member: only their own employee profile
    """
    role = current_user.get("role", "team_member")
    uid = str(current_user["_id"])
    email = current_user.get("email")

    if role == "admin":
        emps = await db.employees.find({"status": "active"}).to_list(6000)
        return [_str_id(e) for e in emps]

    if role == "project_manager":
        if projects is None:
            projects = await get_authorized_projects(db, current_user)
        scoped_emp_ids = set()
        for p in projects:
            for tid in p.get("team_member_ids", p.get("team_ids", [])):
                scoped_emp_ids.add(str(tid))
        # Also include PM's own employee profile if linked
        pm_emp = await db.employees.find_one({"$or": [{"user_id": uid}, {"email": email}]})
        if pm_emp:
            scoped_emp_ids.add(str(pm_emp["_id"]))
        return list(scoped_emp_ids)

    emp = await db.employees.find_one({"$or": [{"user_id": uid}, {"email": email}]})
    return [_str_id(emp)] if emp else []
