from fastapi import APIRouter, Depends, HTTPException, Query
from app.models.task import TaskCreate, TaskUpdate, TaskResponse
from app.core.deps import get_current_user
from app.db.database import get_database
from app.services.activity_service import create_activity
from app.services.notification_service import create_notification
# pyrefly: ignore [missing-import]
from bson import ObjectId
from datetime import datetime
from typing import List, Optional

router = APIRouter()


def serialize_task(t: dict, assignee_name: str = None) -> dict:
    return {
        "id": str(t["_id"]),
        "title": t.get("title", ""),
        "description": t.get("description"),
        "project_id": t.get("project_id", ""),
        "sprint_id": t.get("sprint_id"),
        "assignee_id": t.get("assignee_id"),
        "assignee_name": assignee_name,
        "status": t.get("status", "todo"),
        "priority": t.get("priority", "medium"),
        "story_points": t.get("story_points", 0),
        "estimated_hours": t.get("estimated_hours", 0.0),
        "actual_hours": t.get("actual_hours", 0.0),
        "completion_percentage": t.get("completion_percentage", 0.0),
        "due_date": t.get("due_date"),
        "task_type": t.get("task_type", "feature"),
        "labels": t.get("labels", []),
        "created_at": t.get("created_at"),
        "updated_at": t.get("updated_at"),
    }


async def _resolve_assignee_name(db, assignee_id: str) -> Optional[str]:
    try:
        emp = await db.employees.find_one({"_id": ObjectId(assignee_id)})
        return emp.get("name") if emp else None
    except Exception:
        return None


async def _resolve_project_name(db, project_id: str) -> str:
    try:
        proj = await db.projects.find_one({"_id": ObjectId(project_id)})
        return proj.get("name", "") if proj else ""
    except Exception:
        return ""


@router.get("/", response_model=List[TaskResponse])
async def list_tasks(
    project_id: Optional[str] = None,
    sprint_id: Optional[str] = None,
    assignee_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """
    RBAC:
    - admin / project_manager → see all tasks (or filtered)
    - team_member → see only tasks assigned to their employee profile
    """
    role = current_user.get("role", "team_member")
    query = {}
    if project_id:
        query["project_id"] = project_id
    if sprint_id:
        query["sprint_id"] = sprint_id
    if status:
        query["status"] = status

    if role == "team_member":
        # Override assignee_id filter — team members can only see their own tasks
        emp = await db.employees.find_one({"user_id": str(current_user["_id"])})
        if emp:
            query["assignee_id"] = str(emp["_id"])
        else:
            return []
    elif assignee_id:
        query["assignee_id"] = assignee_id

    tasks = await db.tasks.find(query).sort("created_at", -1).to_list(500)
    result = []
    for t in tasks:
        name = await _resolve_assignee_name(db, t["assignee_id"]) if t.get("assignee_id") else None
        result.append(serialize_task(t, name))
    return result


@router.post("/", response_model=TaskResponse)
async def create_task(
    data: TaskCreate,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    # RBAC: team_members cannot create tasks
    if current_user.get("role") == "team_member":
        raise HTTPException(status_code=403, detail="Team members cannot create tasks")

    doc = data.model_dump()
    doc["created_at"] = datetime.utcnow()
    doc["updated_at"] = datetime.utcnow()
    result = await db.tasks.insert_one(doc)
    doc["_id"] = result.inserted_id
    task_id = str(result.inserted_id)

    actor_name = current_user.get("name", current_user.get("email", "Unknown"))
    project_name = await _resolve_project_name(db, doc.get("project_id", ""))

    # Phase 6: TASK_CREATED activity
    if doc.get("project_id"):
        await create_activity(
            db=db,
            project_id=doc["project_id"],
            activity_type="TASK_CREATED",
            message=f"Task '{doc.get('title')}' created by {actor_name}",
            actor_user_id=str(current_user["_id"]),
            actor_name=actor_name,
            related_entity_id=task_id,
        )

    # Notification + activity for assignment
    if doc.get("assignee_id"):
        try:
            emp = await db.employees.find_one({"_id": ObjectId(doc["assignee_id"])})
            emp_name = emp.get("name", doc["assignee_id"]) if emp else doc["assignee_id"]

            # Phase 6: TASK_ASSIGNED activity
            if doc.get("project_id"):
                await create_activity(
                    db=db,
                    project_id=doc["project_id"],
                    activity_type="TASK_ASSIGNED",
                    message=f"Task '{doc.get('title')}' assigned to {emp_name}",
                    actor_user_id=str(current_user["_id"]),
                    actor_name=actor_name,
                    related_entity_id=task_id,
                )

            # Notification for assignee
            target_uid = emp.get("user_id") if emp else None
            if not target_uid and emp and emp.get("email"):
                u = await db.users.find_one({"email": emp["email"]})
                if u:
                    target_uid = str(u["_id"])
            if not target_uid and emp:
                target_uid = str(emp["_id"])
            if target_uid:
                await create_notification(
                    db=db,
                    user_id=target_uid,
                    notification_type="task_assignment",
                    title="New Task Assigned",
                    message=f"You have been assigned to task '{doc.get('title')}' in {project_name or 'a project'}. Priority: {doc.get('priority', 'medium')}.",
                    related_project_id=doc.get("project_id"),
                    severity="medium",
                )
        except Exception:
            pass

    return serialize_task(doc)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    data: TaskUpdate,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    try:
        t = await db.tasks.find_one({"_id": ObjectId(task_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")

    role = current_user.get("role", "team_member")
    old_assignee = t.get("assignee_id")
    old_status = t.get("status", "todo")

    # RBAC: team_member can only update their own task status — no reassignment
    if role == "team_member":
        emp = await db.employees.find_one({"user_id": str(current_user["_id"])})
        if not emp or str(emp["_id"]) != old_assignee:
            raise HTTPException(status_code=403, detail="You can only update your own tasks")
        # Strip fields team_members cannot change
        allowed_fields = {"status", "actual_hours", "completion_percentage"}
        update_data = {
            k: v for k, v in data.model_dump().items()
            if v is not None and k in allowed_fields
        }
    else:
        update_data = {k: v for k, v in data.model_dump().items() if v is not None}

    update_data["updated_at"] = datetime.utcnow()
    await db.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": update_data})
    updated = await db.tasks.find_one({"_id": ObjectId(task_id)})

    actor_name = current_user.get("name", current_user.get("email", "Unknown"))
    project_id = updated.get("project_id", "")
    project_name = await _resolve_project_name(db, project_id) if project_id else ""
    new_assignee = updated.get("assignee_id")
    new_status = updated.get("status", old_status)

    # Phase 6: TASK_REASSIGNED activity + notification
    if new_assignee and new_assignee != old_assignee and project_id:
        try:
            emp = await db.employees.find_one({"_id": ObjectId(new_assignee)})
            emp_name = emp.get("name", new_assignee) if emp else new_assignee

            await create_activity(
                db=db,
                project_id=project_id,
                activity_type="TASK_REASSIGNED",
                message=f"Task '{updated.get('title')}' reassigned to {emp_name}",
                actor_user_id=str(current_user["_id"]),
                actor_name=actor_name,
                related_entity_id=task_id,
            )

            # Notification for new assignee
            target_uid = emp.get("user_id") if emp else None
            if not target_uid and emp and emp.get("email"):
                u = await db.users.find_one({"email": emp["email"]})
                if u:
                    target_uid = str(u["_id"])
            if not target_uid and emp:
                target_uid = str(emp["_id"])
            if target_uid:
                await create_notification(
                    db=db,
                    user_id=target_uid,
                    notification_type="task_assignment",
                    title="Task Reassigned",
                    message=f"You have been assigned to task '{updated.get('title')}' in {project_name or 'a project'}. Priority: {updated.get('priority', 'medium')}.",
                    related_project_id=project_id,
                    severity="medium",
                )
        except Exception:
            pass

    # Phase 6: TASK_STATUS_CHANGED activity
    if new_status != old_status and project_id:
        await create_activity(
            db=db,
            project_id=project_id,
            activity_type="TASK_STATUS_CHANGED",
            message=f"Task '{updated.get('title')}' status changed from '{old_status}' to '{new_status}' by {actor_name}",
            actor_user_id=str(current_user["_id"]),
            actor_name=actor_name,
            related_entity_id=task_id,
        )

    assignee_name = await _resolve_assignee_name(db, new_assignee) if new_assignee else None
    return serialize_task(updated, assignee_name)


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    # Only managers/admins can delete tasks
    if current_user.get("role") == "team_member":
        raise HTTPException(status_code=403, detail="Team members cannot delete tasks")
    try:
        result = await db.tasks.delete_one({"_id": ObjectId(task_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted successfully"}
