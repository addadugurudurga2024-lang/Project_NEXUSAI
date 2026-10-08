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


async def get_authorized_pm_team_member_ids(db, pm_user_id: str) -> List[str]:
    """
    Authoritative Source of Truth:
    Returns the list of string employee IDs who have an ACTIVE direct Team Capacity
    membership under the specified Project Manager.
    Only active memberships count. Inactive, pending, rejected, orphaned, or reassigned
    memberships are excluded.
    """
    active_mems = await db.team_memberships.find(
        {"pm_user_id": str(pm_user_id), "status": "active"}
    ).to_list(100)
    return [str(m["employee_id"]) for m in active_mems]


async def get_authorized_employee_ids(db, current_user: dict, projects: Optional[List[dict]] = None) -> List[str]:
    """
    Returns list of string employee IDs authorized in the user's scope.
    - admin: all active employees in organization
    - project_manager: active direct Team Capacity memberships for that PM (Authoritative)
    - team_member: only their own employee profile
    """
    role = current_user.get("role", "team_member")
    uid = str(current_user["_id"])
    email = current_user.get("email")

    if role == "admin":
        emps = await db.employees.find({"status": "active"}).to_list(6000)
        return [_str_id(e) for e in emps]

    if role == "project_manager":
        return await get_authorized_pm_team_member_ids(db, uid)

    emp = await db.employees.find_one({"$or": [{"user_id": uid}, {"email": email}]})
    return [_str_id(emp)] if emp else []


async def is_employee_authorized_for_pm(
    db, pm_user_id: str, employee_id: str, project_id: Optional[str] = None
) -> bool:
    """
    Validates whether an employee is authorized for a PM.
    Rule:
    1. Active direct Team Capacity member -> Authorized
    2. If project_id provided: approved cross-PM allocation on that project -> Authorized
    Otherwise -> Denied
    """
    pm_team_ids = await get_authorized_pm_team_member_ids(db, pm_user_id)
    if str(employee_id) in pm_team_ids:
        return True

    if project_id:
        cross_alloc = await db.cross_pm_allocations.find_one({
            "project_id": str(project_id),
            "candidate_employee_id": str(employee_id),
            "status": "approved",
        })
        if cross_alloc:
            return True

    return False


async def is_employee_eligible_for_task(
    db, current_user: dict, project_id: str, employee_id: str
) -> bool:
    """
    Validates whether an employee is eligible to be assigned a task in a project.
    Rule:
    1. Employee MUST be a member of the project team (in project.team_member_ids).
    2. If role == 'project_manager':
       Employee MUST belong to PM's active Team Capacity OR have an approved cross-PM allocation.
    3. If role == 'team_member':
       Must be their own employee profile AND belong to the project.
    """
    role = current_user.get("role", "team_member")
    uid = str(current_user["_id"])

    # Fetch project
    p = await db.projects.find_one({
        "_id": ObjectId(project_id) if ObjectId.is_valid(project_id) else project_id
    })
    if not p:
        return False

    project_member_ids = [str(x) for x in p.get("team_member_ids", p.get("team_ids", []))]
    if str(employee_id) not in project_member_ids:
        return False

    if role == "admin":
        return True

    if role == "project_manager":
        # Project must be managed by this PM
        mgr_id = str(p.get("manager_id") or p.get("project_manager_id") or p.get("created_by") or "")
        if mgr_id != uid:
            return False
        return await is_employee_authorized_for_pm(db, uid, employee_id, project_id=project_id)

    if role == "team_member":
        emp = await db.employees.find_one({
            "$or": [{"user_id": uid}, {"email": current_user.get("email")}]
        })
        if not emp:
            return False
        return str(emp["_id"]) == str(employee_id)

    return False

