from fastapi import APIRouter, Depends, HTTPException, Query
from app.models.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.core.deps import get_current_user, require_manager_or_admin
from app.db.database import get_database
from app.services.activity_service import create_activity
# pyrefly: ignore [missing-import]
from bson import ObjectId
from datetime import datetime
from typing import List, Optional

router = APIRouter()


def serialize_project(p: dict, manager_name: str = None) -> dict:
    return {
        "id": str(p["_id"]),
        "name": p.get("name", ""),
        "description": p.get("description"),
        "client": p.get("client"),
        "domain": p.get("domain"),
        "status": p.get("status", "planning"),
        "priority": p.get("priority", "medium"),
        "start_date": str(p.get("start_date"))[:10] if p.get("start_date") is not None else None,
        "end_date": str(p.get("end_date"))[:10] if p.get("end_date") is not None else None,
        "budget": float(p.get("budget", 0.0)),
        "current_expenditure": float(p.get("current_expenditure", 0.0)),
        "progress": float(p.get("progress", 0.0)),
        "manager_id": str(p["manager_id"]) if p.get("manager_id") else None,
        "manager_name": manager_name,
        "team_member_ids": [str(x) for x in p.get("team_member_ids", p.get("team_ids", []))],
        "requirements": p.get("requirements"),
        "tech_stack": p.get("tech_stack", []),
        "created_at": p.get("created_at"),
        "updated_at": p.get("updated_at"),
    }


async def _get_manager_name(db, manager_id: str) -> Optional[str]:
    try:
        mgr = await db.users.find_one({"_id": ObjectId(manager_id)})
        return mgr.get("name") if mgr else None
    except Exception:
        return None


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """
    RBAC:
    - admin → see all projects
    - project_manager → see only their managed projects
    - team_member → see only projects where their employee_id is in team_member_ids
    """
    role = current_user.get("role", "team_member")
    uid = str(current_user["_id"])
    query = {}
    if status:
        query["status"] = status
    if priority:
        query["priority"] = priority

    if role == "admin":
        pass
    elif role == "project_manager":
        valid_obj_ids = [ObjectId(uid)] if ObjectId.is_valid(uid) else []
        query["$or"] = [
            {"manager_id": uid},
            {"manager_id": {"$in": valid_obj_ids}},
            {"project_manager_id": uid},
            {"created_by": uid},
        ]
    elif role == "team_member":
        emp = await db.employees.find_one({"$or": [{"user_id": uid}, {"email": current_user.get("email")}]})
        if emp:
            emp_id = str(emp["_id"])
            valid_emp_objs = [emp["_id"]] if isinstance(emp["_id"], ObjectId) else []
            query["team_member_ids"] = {"$in": [uid, emp_id] + valid_emp_objs}
        else:
            return []

    projects = await db.projects.find(query).sort("created_at", -1).to_list(500)
    result = []
    for p in projects:
        manager_name = await _get_manager_name(db, p["manager_id"]) if p.get("manager_id") else None
        result.append(serialize_project(p, manager_name))
    return result


@router.post("/", response_model=ProjectResponse)
async def create_project(
    data: ProjectCreate,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    doc = data.model_dump()
    role = current_user.get("role", "team_member")
    uid = str(current_user["_id"])

    # Validate PM Team Capacity scoping
    if role == "project_manager":
        from app.services.project_scoping_service import is_employee_authorized_for_pm
        for member_id in doc.get("team_member_ids", []):
            is_auth = await is_employee_authorized_for_pm(db, uid, str(member_id))
            if not is_auth:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied: Employee {member_id} is not in your active Team Capacity"
                )

    doc["created_at"] = datetime.utcnow()
    doc["updated_at"] = datetime.utcnow()
    doc["created_by"] = str(current_user["_id"])
    if not doc.get("manager_id") and current_user.get("role") == "project_manager":
        doc["manager_id"] = str(current_user["_id"])
    result = await db.projects.insert_one(doc)
    doc["_id"] = result.inserted_id
    project_id = str(result.inserted_id)
    actor_name = current_user.get("name", current_user.get("email", "Unknown"))

    # Phase 6: Record PROJECT_CREATED activity
    await create_activity(
        db=db,
        project_id=project_id,
        activity_type="PROJECT_CREATED",
        message=f"Project '{doc.get('name')}' created by {actor_name}",
        actor_user_id=str(current_user["_id"]),
        actor_name=actor_name,
        related_entity_id=project_id,
    )

    # Phase 6: Record PM_ASSIGNED if manager set at creation
    if doc.get("manager_id"):
        mgr_name = await _get_manager_name(db, doc["manager_id"])
        await create_activity(
            db=db,
            project_id=project_id,
            activity_type="PM_ASSIGNED",
            message=f"Project Manager {mgr_name or doc['manager_id']} assigned to '{doc.get('name')}'",
            actor_user_id=str(current_user["_id"]),
            actor_name=actor_name,
            related_entity_id=doc["manager_id"],
        )

    # Record MEMBER_ADDED and send notifications for initial team members
    from app.services.notification_service import notify_project_assigned
    for member_id in doc.get("team_member_ids", []):
        try:
            emp = await db.employees.find_one({"_id": ObjectId(member_id)})
            emp_name = emp.get("name", member_id) if emp else member_id
            await create_activity(
                db=db,
                project_id=project_id,
                activity_type="MEMBER_ADDED",
                message=f"{emp_name} added to project team",
                actor_user_id=str(current_user["_id"]),
                actor_name=actor_name,
                related_entity_id=member_id,
            )
            await notify_project_assigned(
                db=db,
                project_id=project_id,
                project_name=doc.get("name", "Project"),
                member_emp_id=member_id,
                assigned_by_user=current_user,
            )
        except Exception:
            pass

    return serialize_project(doc)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    try:
        p = await db.projects.find_one({"_id": ObjectId(project_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    role = current_user.get("role", "team_member")
    uid = str(current_user["_id"])

    if role == "project_manager":
        mgr_id = str(p.get("manager_id") or p.get("project_manager_id") or p.get("created_by") or "")
        if mgr_id != uid:
            raise HTTPException(status_code=403, detail="Access denied: You do not manage this project")
    elif role == "team_member":
        emp = await db.employees.find_one({"$or": [{"user_id": uid}, {"email": current_user.get("email")}]})
        emp_id = str(emp["_id"]) if emp else ""
        team_ids = [str(x) for x in p.get("team_member_ids", [])]
        if uid not in team_ids and emp_id not in team_ids:
            raise HTTPException(status_code=403, detail="Access denied")

    manager_name = await _get_manager_name(db, p["manager_id"]) if p.get("manager_id") else None
    return serialize_project(p, manager_name)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    try:
        p = await db.projects.find_one({"_id": ObjectId(project_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    role = current_user.get("role", "team_member")
    uid = str(current_user["_id"])
    if role == "project_manager":
        mgr_id = str(p.get("manager_id") or p.get("project_manager_id") or p.get("created_by") or "")
        if mgr_id != uid:
            raise HTTPException(status_code=403, detail="Access denied: You cannot update another PM's project")

    old_manager_id = p.get("manager_id")
    old_team_ids = set(str(x) for x in p.get("team_member_ids", p.get("team_ids", [])))

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}

    # Validate PM Team Capacity scoping on team member changes
    if role == "project_manager" and "team_member_ids" in update_data:
        from app.services.project_scoping_service import is_employee_authorized_for_pm
        new_members = [str(x) for x in update_data["team_member_ids"]]
        for member_id in set(new_members) - old_team_ids:
            is_auth = await is_employee_authorized_for_pm(db, uid, member_id, project_id=project_id)
            if not is_auth:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied: Employee {member_id} is not in your active Team Capacity"
                )

    update_data["updated_at"] = datetime.utcnow()
    await db.projects.update_one({"_id": ObjectId(project_id)}, {"$set": update_data})
    updated = await db.projects.find_one({"_id": ObjectId(project_id)})

    actor_name = current_user.get("name", current_user.get("email", "Unknown"))
    project_name = updated.get("name", project_id)

    # Phase 6: PM change activity
    new_manager_id = updated.get("manager_id")
    if new_manager_id and new_manager_id != old_manager_id:
        mgr_name = await _get_manager_name(db, new_manager_id)
        await create_activity(
            db=db,
            project_id=project_id,
            activity_type="PM_ASSIGNED",
            message=f"Project Manager changed to {mgr_name or new_manager_id} for '{project_name}'",
            actor_user_id=str(current_user["_id"]),
            actor_name=actor_name,
            related_entity_id=new_manager_id,
        )

    # Phase 6: Team member added/removed activities
    new_team_ids = set(updated.get("team_member_ids", []))
    added_ids = new_team_ids - old_team_ids
    removed_ids = old_team_ids - new_team_ids

    for member_id in added_ids:
        try:
            emp = await db.employees.find_one({"_id": ObjectId(member_id)})
            emp_name = emp.get("name", member_id) if emp else member_id
            await create_activity(
                db=db,
                project_id=project_id,
                activity_type="MEMBER_ADDED",
                message=f"{emp_name} added to project '{project_name}'",
                actor_user_id=str(current_user["_id"]),
                actor_name=actor_name,
                related_entity_id=member_id,
            )
            await notify_project_assigned(
                db=db,
                project_id=project_id,
                project_name=project_name,
                member_emp_id=member_id,
                assigned_by_user=current_user,
            )
        except Exception:
            pass

    for member_id in removed_ids:
        try:
            emp = await db.employees.find_one({"_id": ObjectId(member_id)})
            emp_name = emp.get("name", member_id) if emp else member_id
            await create_activity(
                db=db,
                project_id=project_id,
                activity_type="MEMBER_REMOVED",
                message=f"{emp_name} removed from project '{project_name}'",
                actor_user_id=str(current_user["_id"]),
                actor_name=actor_name,
                related_entity_id=member_id,
            )
        except Exception:
            pass

    manager_name = await _get_manager_name(db, updated.get("manager_id")) if updated.get("manager_id") else None
    return serialize_project(updated, manager_name)


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    try:
        p = await db.projects.find_one({"_id": ObjectId(project_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    role = current_user.get("role", "team_member")
    uid = str(current_user["_id"])
    if role == "project_manager":
        mgr_id = str(p.get("manager_id") or p.get("project_manager_id") or p.get("created_by") or "")
        if mgr_id != uid:
            raise HTTPException(status_code=403, detail="Access denied: You cannot delete another PM's project")

    result = await db.projects.delete_one({"_id": ObjectId(project_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"message": "Project deleted successfully"}
