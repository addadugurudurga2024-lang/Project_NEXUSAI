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
        "start_date": p.get("start_date"),
        "end_date": p.get("end_date"),
        "budget": p.get("budget", 0.0),
        "current_expenditure": p.get("current_expenditure", 0.0),
        "progress": p.get("progress", 0.0),
        "manager_id": p.get("manager_id"),
        "manager_name": manager_name,
        "team_member_ids": p.get("team_member_ids", []),
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
    - admin / project_manager → see all projects
    - team_member → see only projects where their employee_id is in team_member_ids
    """
    role = current_user.get("role", "team_member")
    query = {}
    if status:
        query["status"] = status
    if priority:
        query["priority"] = priority

    if role == "team_member":
        # Find the employee profile linked to this user
        emp = await db.employees.find_one({"user_id": str(current_user["_id"])})
        if emp:
            emp_id = str(emp["_id"])
            query["team_member_ids"] = emp_id
        else:
            # No employee profile → return empty list
            return []

    projects = await db.projects.find(query).sort("created_at", -1).to_list(200)
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
            target_uid = emp.get("user_id") if emp else None
            if not target_uid and emp and emp.get("email"):
                u = await db.users.find_one({"email": emp["email"]})
                if u:
                    target_uid = str(u["_id"])
            if not target_uid and emp:
                target_uid = str(emp["_id"])
            if target_uid:
                from app.services.notification_service import create_notification
                await create_notification(
                    db=db,
                    user_id=target_uid,
                    notification_type="project_assignment",
                    title="Added to Project",
                    message=f"You have been added to project '{doc.get('name')}'.",
                    related_project_id=project_id,
                    severity="medium",
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

    # RBAC: team_member can only view their own projects
    role = current_user.get("role", "team_member")
    if role == "team_member":
        emp = await db.employees.find_one({"user_id": str(current_user["_id"])})
        if not emp or str(emp["_id"]) not in p.get("team_member_ids", []):
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

    old_manager_id = p.get("manager_id")
    old_team_ids = set(p.get("team_member_ids", []))

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
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
            # Also notify the added member
            target_uid = emp.get("user_id") if emp else None
            if not target_uid and emp and emp.get("email"):
                u = await db.users.find_one({"email": emp["email"]})
                if u:
                    target_uid = str(u["_id"])
            if not target_uid and emp:
                target_uid = str(emp["_id"])
            if target_uid:
                from app.services.notification_service import create_notification
                await create_notification(
                    db=db,
                    user_id=target_uid,
                    notification_type="project_assignment",
                    title="Added to Project",
                    message=f"You have been added to project '{project_name}'.",
                    related_project_id=project_id,
                    severity="medium",
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
        result = await db.projects.delete_one({"_id": ObjectId(project_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"message": "Project deleted successfully"}
