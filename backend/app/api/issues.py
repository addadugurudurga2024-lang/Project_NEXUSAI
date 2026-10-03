from fastapi import APIRouter, Depends, HTTPException, Query
from app.models.issue import IssueCreate, IssueUpdate, IssueResponse
from app.core.deps import get_current_user
from app.db.database import get_database
from app.services.activity_service import create_activity
# pyrefly: ignore [missing-import]
from bson import ObjectId
from datetime import datetime
from typing import List, Optional

router = APIRouter()


def serialize_issue(i: dict, assignee_name: str = None) -> dict:
    return {
        "id": str(i["_id"]),
        "title": i.get("title", ""),
        "description": i.get("description"),
        "project_id": i.get("project_id", ""),
        "task_id": i.get("task_id"),
        "category": i.get("category", "bug"),
        "severity": i.get("severity", "medium"),
        "priority": i.get("priority", "medium"),
        "status": i.get("status", "open"),
        "assignee_id": i.get("assignee_id"),
        "assignee_name": assignee_name,
        "resolution": i.get("resolution"),
        "resolved_at": i.get("resolved_at"),
        "created_at": i.get("created_at"),
        "updated_at": i.get("updated_at"),
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


@router.get("/", response_model=List[IssueResponse])
async def list_issues(
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """
    RBAC:
    - admin / project_manager → see all issues (or filtered)
    - team_member → see only issues assigned to them
    """
    role = current_user.get("role", "team_member")
    query = {}
    if project_id:
        query["project_id"] = project_id
    if status:
        query["status"] = status
    if severity:
        query["severity"] = severity

    if role == "team_member":
        emp = await db.employees.find_one({"user_id": str(current_user["_id"])})
        if emp:
            query["assignee_id"] = str(emp["_id"])
        else:
            return []

    issues = await db.issues.find(query).sort("created_at", -1).to_list(500)
    result = []
    for i in issues:
        name = await _resolve_assignee_name(db, i["assignee_id"]) if i.get("assignee_id") else None
        result.append(serialize_issue(i, name))
    return result


@router.post("/", response_model=IssueResponse)
async def create_issue(
    data: IssueCreate,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    doc = data.model_dump()
    doc["created_at"] = datetime.utcnow()
    doc["updated_at"] = datetime.utcnow()
    result = await db.issues.insert_one(doc)
    doc["_id"] = result.inserted_id
    issue_id = str(result.inserted_id)
    actor_name = current_user.get("name", current_user.get("email", "Unknown"))

    # Phase 6: ISSUE_CREATED activity
    if doc.get("project_id"):
        await create_activity(
            db=db,
            project_id=doc["project_id"],
            activity_type="ISSUE_CREATED",
            message=f"Issue '{doc.get('title')}' ({doc.get('severity', 'medium')} severity) reported by {actor_name}",
            actor_user_id=str(current_user["_id"]),
            actor_name=actor_name,
            related_entity_id=issue_id,
        )

        # Phase 6: ISSUE_ASSIGNED activity if assignee set at creation
        if doc.get("assignee_id"):
            try:
                emp = await db.employees.find_one({"_id": ObjectId(doc["assignee_id"])})
                emp_name = emp.get("name", doc["assignee_id"]) if emp else doc["assignee_id"]
                await create_activity(
                    db=db,
                    project_id=doc["project_id"],
                    activity_type="ISSUE_ASSIGNED",
                    message=f"Issue '{doc.get('title')}' assigned to {emp_name}",
                    actor_user_id=str(current_user["_id"]),
                    actor_name=actor_name,
                    related_entity_id=issue_id,
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
                        notification_type="issue_assignment",
                        title="New Issue Assigned",
                        message=f"You have been assigned to issue '{doc.get('title')}'. Severity: {doc.get('severity', 'medium')}.",
                        related_project_id=doc.get("project_id"),
                        severity="high" if doc.get("severity") in ("critical", "high") else "medium",
                    )
            except Exception:
                pass

        if doc.get("severity") == "critical":
            try:
                from app.services.notification_service import notify_project_stakeholders
                await notify_project_stakeholders(
                    db=db,
                    project_id=doc["project_id"],
                    notification_type="critical_issue",
                    title=f"Critical Issue Logged: {doc.get('title')}",
                    message=f"A critical severity issue '{doc.get('title')}' was reported by {actor_name}.",
                    severity="critical",
                )
            except Exception:
                pass

    return serialize_issue(doc)


@router.get("/{issue_id}", response_model=IssueResponse)
async def get_issue(
    issue_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    try:
        i = await db.issues.find_one({"_id": ObjectId(issue_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid issue ID")
    if not i:
        raise HTTPException(status_code=404, detail="Issue not found")

    # RBAC: team_member can only see issues assigned to them
    if current_user.get("role") == "team_member":
        emp = await db.employees.find_one({"user_id": str(current_user["_id"])})
        if not emp or str(emp["_id"]) != i.get("assignee_id"):
            raise HTTPException(status_code=403, detail="Access denied")

    name = await _resolve_assignee_name(db, i["assignee_id"]) if i.get("assignee_id") else None
    return serialize_issue(i, name)


@router.put("/{issue_id}", response_model=IssueResponse)
async def update_issue(
    issue_id: str,
    data: IssueUpdate,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    try:
        i = await db.issues.find_one({"_id": ObjectId(issue_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid issue ID")
    if not i:
        raise HTTPException(status_code=404, detail="Issue not found")

    role = current_user.get("role", "team_member")
    old_assignee = i.get("assignee_id")
    old_status = i.get("status", "open")

    # RBAC: team_member can only update status/resolution on their own issues
    if role == "team_member":
        emp = await db.employees.find_one({"user_id": str(current_user["_id"])})
        if not emp or str(emp["_id"]) != old_assignee:
            raise HTTPException(status_code=403, detail="You can only update issues assigned to you")
        allowed_fields = {"status", "resolution"}
        update_data = {
            k: v for k, v in data.model_dump().items()
            if v is not None and k in allowed_fields
        }
    else:
        update_data = {k: v for k, v in data.model_dump().items() if v is not None}

    if update_data.get("status") == "resolved" and not i.get("resolved_at"):
        update_data["resolved_at"] = datetime.utcnow()
    update_data["updated_at"] = datetime.utcnow()
    await db.issues.update_one({"_id": ObjectId(issue_id)}, {"$set": update_data})
    updated = await db.issues.find_one({"_id": ObjectId(issue_id)})

    actor_name = current_user.get("name", current_user.get("email", "Unknown"))
    project_id = updated.get("project_id", "")
    new_assignee = updated.get("assignee_id")
    new_status = updated.get("status", old_status)

    if project_id:
        # Phase 6: ISSUE_ASSIGNED (reassignment)
        if new_assignee and new_assignee != old_assignee:
            try:
                emp = await db.employees.find_one({"_id": ObjectId(new_assignee)})
                emp_name = emp.get("name", new_assignee) if emp else new_assignee
                await create_activity(
                    db=db,
                    project_id=project_id,
                    activity_type="ISSUE_ASSIGNED",
                    message=f"Issue '{updated.get('title')}' assigned to {emp_name}",
                    actor_user_id=str(current_user["_id"]),
                    actor_name=actor_name,
                    related_entity_id=issue_id,
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
                        notification_type="issue_assignment",
                        title="Issue Reassigned",
                        message=f"You have been assigned to issue '{updated.get('title')}'. Severity: {updated.get('severity', 'medium')}.",
                        related_project_id=project_id,
                        severity="high" if updated.get("severity") in ("critical", "high") else "medium",
                    )
            except Exception:
                pass

        # Phase 6: ISSUE_RESOLVED or ISSUE_STATUS_CHANGED
        if new_status != old_status:
            if new_status == "resolved":
                await create_activity(
                    db=db,
                    project_id=project_id,
                    activity_type="ISSUE_RESOLVED",
                    message=f"Issue '{updated.get('title')}' resolved by {actor_name}",
                    actor_user_id=str(current_user["_id"]),
                    actor_name=actor_name,
                    related_entity_id=issue_id,
                )
            else:
                await create_activity(
                    db=db,
                    project_id=project_id,
                    activity_type="ISSUE_STATUS_CHANGED",
                    message=f"Issue '{updated.get('title')}' status changed from '{old_status}' to '{new_status}' by {actor_name}",
                    actor_user_id=str(current_user["_id"]),
                    actor_name=actor_name,
                    related_entity_id=issue_id,
                )

    name = await _resolve_assignee_name(db, new_assignee) if new_assignee else None
    return serialize_issue(updated, name)


@router.delete("/{issue_id}")
async def delete_issue(
    issue_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    try:
        result = await db.issues.delete_one({"_id": ObjectId(issue_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid issue ID")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Issue not found")
    return {"message": "Issue deleted successfully"}
