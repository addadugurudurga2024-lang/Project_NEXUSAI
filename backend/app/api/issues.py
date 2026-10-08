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
        "project_id": str(i.get("project_id", "")),
        "task_id": str(i["task_id"]) if i.get("task_id") else None,
        "category": i.get("category", "bug"),
        "severity": i.get("severity", "medium"),
        "priority": i.get("priority", "medium"),
        "status": i.get("status", "open"),
        "assignee_id": str(i["assignee_id"]) if i.get("assignee_id") else None,
        "assignee_name": assignee_name,
        "assigned_by": str(i["assigned_by"]) if i.get("assigned_by") else None,
        "assigned_by_name": i.get("assigned_by_name"),
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
    - admin → see all issues (or filtered)
    - project_manager → see issues in their managed projects
    - team_member → see only issues assigned to them
    """
    role = current_user.get("role", "team_member")
    uid = str(current_user["_id"])
    query = {}
    if status:
        query["status"] = status
    if severity:
        query["severity"] = severity

    if role == "admin":
        if project_id:
            query["project_id"] = project_id
    elif role == "project_manager":
        from app.services.project_scoping_service import get_authorized_project_ids
        authorized_pids = await get_authorized_project_ids(db, current_user)
        if project_id:
            if project_id not in authorized_pids:
                return []
            query["project_id"] = project_id
        else:
            query["project_id"] = {"$in": authorized_pids}
    elif role == "team_member":
        emp = await db.employees.find_one({"$or": [{"user_id": uid}, {"email": current_user.get("email")}]})
        if emp:
            query["assignee_id"] = str(emp["_id"])
            if project_id:
                query["project_id"] = project_id
        else:
            return []

    issues = await db.issues.find(query).sort("created_at", -1).to_list(1000)
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
    actor_name = current_user.get("name", current_user.get("email", "Unknown"))
    doc = data.model_dump()
    doc["assigned_by"] = str(current_user["_id"])
    doc["assigned_by_name"] = actor_name
    doc["created_at"] = datetime.utcnow()
    doc["updated_at"] = datetime.utcnow()
    result = await db.issues.insert_one(doc)
    doc["_id"] = result.inserted_id
    issue_id = str(result.inserted_id)

    # Activity: ISSUE_CREATED
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

        # EVENT 2: ISSUE_ASSIGNED notification if assignee set at creation
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
                proj_name = await _resolve_project_name(db, doc.get("project_id", ""))
                from app.services.notification_service import notify_issue_assigned
                await notify_issue_assigned(
                    db=db,
                    project_id=doc.get("project_id", ""),
                    project_name=proj_name,
                    issue_id=issue_id,
                    issue_title=doc.get("title", "Issue"),
                    severity=doc.get("severity", "medium"),
                    assignee_emp_id=doc["assignee_id"],
                    assigned_by_user=current_user,
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

    role = current_user.get("role", "team_member")
    uid = str(current_user["_id"])
    project_id = str(i.get("project_id", ""))

    if role == "project_manager":
        from app.services.project_scoping_service import get_authorized_project_ids
        authorized_pids = await get_authorized_project_ids(db, current_user)
        if project_id not in authorized_pids:
            raise HTTPException(status_code=403, detail="Access denied: Issue belongs to another PM's project")
    elif role == "team_member":
        emp = await db.employees.find_one({"$or": [{"user_id": uid}, {"email": current_user.get("email")}]})
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
    uid = str(current_user["_id"])
    old_assignee = i.get("assignee_id")
    old_status = i.get("status", "open")
    project_id = str(i.get("project_id", ""))
    actor_name = current_user.get("name", current_user.get("email", "Unknown"))

    if role == "project_manager":
        from app.services.project_scoping_service import get_authorized_project_ids
        authorized_pids = await get_authorized_project_ids(db, current_user)
        if project_id not in authorized_pids:
            raise HTTPException(status_code=403, detail="Access denied: Cannot update another PM's issue")

    if role == "team_member":
        # Prioritize user_id match; fall back to email. old_assignee is the employee _id string.
        emp_by_uid = await db.employees.find_one({"user_id": uid})
        emp_by_email = await db.employees.find_one({"email": current_user.get("email")})
        # Collect unique employee _id strings this user could be
        candidate_emp_ids = set()
        if emp_by_uid:
            candidate_emp_ids.add(str(emp_by_uid["_id"]))
        if emp_by_email:
            candidate_emp_ids.add(str(emp_by_email["_id"]))
        if not candidate_emp_ids or old_assignee not in candidate_emp_ids:
            raise HTTPException(status_code=403, detail="You can only update issues assigned to you")
        allowed_fields = {"status", "resolution"}
        update_data = {
            k: v for k, v in data.model_dump().items()
            if v is not None and k in allowed_fields
        }
    else:
        update_data = {k: v for k, v in data.model_dump().items() if v is not None}

    # If assignee is updated, preserve the new assigner context
    if "assignee_id" in update_data and update_data["assignee_id"] != old_assignee:
        update_data["assigned_by"] = str(current_user["_id"])
        update_data["assigned_by_name"] = actor_name

    # Resolution timestamp tracking & reopening
    if update_data.get("status") == "resolved" and old_status != "resolved":
        update_data["resolved_at"] = datetime.utcnow()
    elif update_data.get("status") and update_data["status"] != "resolved" and old_status == "resolved":
        update_data["resolved_at"] = None

    update_data["updated_at"] = datetime.utcnow()
    await db.issues.update_one({"_id": ObjectId(issue_id)}, {"$set": update_data})
    updated = await db.issues.find_one({"_id": ObjectId(issue_id)})

    new_assignee = updated.get("assignee_id")
    new_status = updated.get("status", old_status)

    if project_id:
        proj_name = await _resolve_project_name(db, project_id)

        # EVENT 2: ISSUE_ASSIGNED notification if assignee changed
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
                from app.services.notification_service import notify_issue_assigned
                await notify_issue_assigned(
                    db=db,
                    project_id=project_id,
                    project_name=proj_name,
                    issue_id=issue_id,
                    issue_title=updated.get("title", "Issue"),
                    severity=updated.get("severity", "medium"),
                    assignee_emp_id=new_assignee,
                    assigned_by_user=current_user,
                )
            except Exception:
                pass

        # EVENT 3: ISSUE_RESOLVED notification if status transitioned to resolved
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
                try:
                    assigning_manager = updated.get("assigned_by") or updated.get("reporter_id") or i.get("assigned_by")
                    from app.services.notification_service import notify_issue_resolved
                    await notify_issue_resolved(
                        db=db,
                        project_id=project_id,
                        project_name=proj_name,
                        issue_id=issue_id,
                        issue_title=updated.get("title", "Issue"),
                        assignee_emp_id=updated.get("assignee_id"),
                        assigning_manager_id=assigning_manager,
                        resolved_by_user=current_user,
                    )
                except Exception:
                    pass
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
    role = current_user.get("role", "team_member")
    if role == "team_member":
        raise HTTPException(status_code=403, detail="Team members cannot delete issues")

    try:
        i = await db.issues.find_one({"_id": ObjectId(issue_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid issue ID")
    if not i:
        raise HTTPException(status_code=404, detail="Issue not found")

    project_id = str(i.get("project_id", ""))
    if role == "project_manager":
        from app.services.project_scoping_service import get_authorized_project_ids
        authorized_pids = await get_authorized_project_ids(db, current_user)
        if project_id not in authorized_pids:
            raise HTTPException(status_code=403, detail="Access denied: Cannot delete another PM's issue")

    result = await db.issues.delete_one({"_id": ObjectId(issue_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Issue not found")
    return {"message": "Issue deleted successfully"}
