"""
Notification Service for NexusAI
Handles event-driven operational notifications:
1. PROJECT_ASSIGNED: Team Member assigned to a new project
2. ISSUE_ASSIGNED: Team Member assigned a new issue for resolution
3. ISSUE_RESOLVED: Assigned issue is resolved -> notified to the responsible Project Manager
"""

# pyrefly: ignore [missing-import]
from bson import ObjectId
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any


async def get_user_id_for_employee(db, emp_id: str) -> Optional[str]:
    """Resolves an employee _id (or string) to the corresponding authenticated user _id string."""
    if not emp_id:
        return None
    try:
        if ObjectId.is_valid(emp_id):
            emp = await db.employees.find_one({"_id": ObjectId(emp_id)})
        else:
            emp = await db.employees.find_one({"_id": emp_id})
        if not emp:
            emp = await db.employees.find_one({"id": emp_id})
            
        if emp:
            # 1. If linked user_id is directly present
            if emp.get("user_id"):
                u = await db.users.find_one({"_id": ObjectId(emp["user_id"]) if ObjectId.is_valid(emp["user_id"]) else emp["user_id"]})
                if u:
                    return str(u["_id"])
            # 2. Try matching user by email
            if emp.get("email"):
                u = await db.users.find_one({"email": emp["email"]})
                if u:
                    return str(u["_id"])
            # Fallback to employee ObjectId string so employee-scoped queries still resolve
            return str(emp["_id"])
    except Exception:
        pass
    return str(emp_id)


async def create_notification(
    db,
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    related_project_id: Optional[str] = None,
    related_issue_id: Optional[str] = None,
    assigned_by: Optional[str] = None,
    assigned_by_name: Optional[str] = None,
    severity: str = "medium",
) -> Optional[Dict[str, Any]]:
    """
    Creates an authoritative notification record in MongoDB with duplicate prevention.
    Prevents duplicate unread notifications for identical (recipient, type, entity) combinations.
    """
    if not user_id:
        return None

    user_id_str = str(user_id)
    now_utc = datetime.now(timezone.utc)

    # -------------------------------------------------------------
    # Duplicate Prevention Query: Check for active unread notification
    # -------------------------------------------------------------
    dup_query: Dict[str, Any] = {
        "$and": [
            {"$or": [{"userId": user_id_str}, {"user_id": user_id_str}]},
            {"type": notification_type},
            {"$or": [{"isRead": False}, {"read": False}]},
        ]
    }

    if related_issue_id:
        dup_query["$and"].append({"$or": [{"relatedIssueId": str(related_issue_id)}, {"related_issue_id": str(related_issue_id)}]})
    elif related_project_id:
        dup_query["$and"].append({"$or": [{"relatedProjectId": str(related_project_id)}, {"related_project_id": str(related_project_id)}]})

    existing = await db.notifications.find_one(dup_query)
    if existing:
        return existing

    doc = {
        "userId": user_id_str,
        "user_id": user_id_str,  # compatibility
        "type": notification_type,
        "title": title,
        "message": message,
        "relatedProjectId": str(related_project_id) if related_project_id else None,
        "related_project_id": str(related_project_id) if related_project_id else None,
        "relatedIssueId": str(related_issue_id) if related_issue_id else None,
        "related_issue_id": str(related_issue_id) if related_issue_id else None,
        "assigned_by": str(assigned_by) if assigned_by else None,
        "assigned_by_name": assigned_by_name,
        "severity": severity,
        "isRead": False,
        "read": False,
        "createdAt": now_utc,
        "created_at": now_utc,
    }

    result = await db.notifications.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc["_id"] = result.inserted_id
    return doc


async def notify_project_assigned(
    db,
    project_id: str,
    project_name: str,
    member_emp_id: str,
    assigned_by_user: dict,
) -> Optional[Dict[str, Any]]:
    """
    EVENT 1: Triggered when a Team Member is newly assigned to a project.
    Recipient: The assigned Team Member.
    """
    target_uid = await get_user_id_for_employee(db, member_emp_id)
    if not target_uid:
        return None

    actor_name = assigned_by_user.get("name") or assigned_by_user.get("email") or "Project Manager"
    actor_id = str(assigned_by_user.get("_id", ""))

    title = "New Project Assignment"
    message = (
        f"You have been assigned to a new project:\n\n"
        f"Project: {project_name}\n"
        f"Assigned by: {actor_name}\n\n"
        f"Please review the project details and your assigned work."
    )

    return await create_notification(
        db=db,
        user_id=target_uid,
        notification_type="PROJECT_ASSIGNED",
        title=title,
        message=message,
        related_project_id=project_id,
        assigned_by=actor_id,
        assigned_by_name=actor_name,
        severity="medium",
    )


async def notify_issue_assigned(
    db,
    project_id: str,
    project_name: str,
    issue_id: str,
    issue_title: str,
    severity: str,
    assignee_emp_id: str,
    assigned_by_user: dict,
) -> Optional[Dict[str, Any]]:
    """
    EVENT 2: Triggered when a Team Member is assigned to a new issue for resolution.
    Recipient: The assigned Team Member.
    """
    target_uid = await get_user_id_for_employee(db, assignee_emp_id)
    if not target_uid:
        return None

    actor_name = assigned_by_user.get("name") or assigned_by_user.get("email") or "Project Manager"
    actor_id = str(assigned_by_user.get("_id", ""))

    title = "New Issue Assigned"
    message = (
        f"You have been assigned a new issue for resolution.\n\n"
        f"Issue: {issue_title}\n"
        f"Project: {project_name}\n"
        f"Assigned by: {actor_name}\n"
        f"Severity: {severity.capitalize()}\n\n"
        f"Please review the issue and resolve it."
    )

    return await create_notification(
        db=db,
        user_id=target_uid,
        notification_type="ISSUE_ASSIGNED",
        title=title,
        message=message,
        related_project_id=project_id,
        related_issue_id=issue_id,
        assigned_by=actor_id,
        assigned_by_name=actor_name,
        severity="high" if severity in ("critical", "high") else "medium",
    )


async def notify_issue_resolved(
    db,
    project_id: str,
    project_name: str,
    issue_id: str,
    issue_title: str,
    assignee_emp_id: Optional[str],
    assigning_manager_id: Optional[str],
    resolved_by_user: dict,
) -> Optional[Dict[str, Any]]:
    """
    EVENT 3: Triggered when an assigned issue is resolved.
    Recipient: The responsible Project Manager who assigned the issue.
    """
    manager_uid = None

    # 1. First check if assigning_manager_id is a valid user
    if assigning_manager_id:
        try:
            if ObjectId.is_valid(assigning_manager_id):
                u = await db.users.find_one({"_id": ObjectId(assigning_manager_id)})
            else:
                u = await db.users.find_one({"_id": assigning_manager_id})
            if u:
                manager_uid = str(u["_id"])
        except Exception:
            pass

    # 2. Fallback to the project's manager_id if assigning_manager was not directly a user
    if not manager_uid and project_id:
        try:
            if ObjectId.is_valid(project_id):
                proj = await db.projects.find_one({"_id": ObjectId(project_id)})
            else:
                proj = await db.projects.find_one({"_id": project_id})
            if proj:
                manager_uid = str(proj.get("manager_id") or proj.get("project_manager_id") or proj.get("created_by") or "")
        except Exception:
            pass

    if not manager_uid:
        return None

    resolver_name = resolved_by_user.get("name") or resolved_by_user.get("email") or "Team Member"
    assignee_name = "the assignee"
    if assignee_emp_id:
        try:
            if ObjectId.is_valid(assignee_emp_id):
                emp = await db.employees.find_one({"_id": ObjectId(assignee_emp_id)})
            else:
                emp = await db.employees.find_one({"_id": assignee_emp_id})
            if emp:
                assignee_name = emp.get("name", "the assignee")
        except Exception:
            pass

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    title = "Issue Resolved"
    message = (
        f"The issue assigned to {assignee_name} has been resolved.\n\n"
        f"Issue: {issue_title}\n"
        f"Project: {project_name}\n"
        f"Resolved by: {resolver_name}\n"
        f"Resolved at: {now_str}\n\n"
        f"The issue has been marked as resolved."
    )

    return await create_notification(
        db=db,
        user_id=manager_uid,
        notification_type="ISSUE_RESOLVED",
        title=title,
        message=message,
        related_project_id=project_id,
        related_issue_id=issue_id,
        assigned_by=str(resolved_by_user.get("_id", "")),
        assigned_by_name=resolver_name,
        severity="medium",
    )


async def notify_project_stakeholders(
    db,
    project_id: str,
    notification_type: str,
    title: str,
    message: str,
    severity: str = "medium",
):
    """
    Notifies the specific project manager for high-severity project-level events.
    Does NOT broadcast globally across unrelated PMs.
    """
    try:
        if ObjectId.is_valid(project_id):
            project = await db.projects.find_one({"_id": ObjectId(project_id)})
        else:
            project = await db.projects.find_one({"_id": project_id})
    except Exception:
        project = None

    if not project:
        return

    mgr_id = project.get("manager_id") or project.get("project_manager_id") or project.get("created_by")
    if mgr_id:
        await create_notification(
            db=db,
            user_id=str(mgr_id),
            notification_type=notification_type,
            title=title,
            message=message,
            related_project_id=project_id,
            severity=severity,
        )


async def notify_team_member_requested(
    db,
    pm_user_id: str,
    candidate_name: str,
    candidate_role: str,
    candidate_skills: List[str],
    active_capacity: int,
    max_capacity: int = 18,
) -> Optional[Dict[str, Any]]:
    """
    Triggered when a Team Member requests association with a Project Manager.
    Recipient: The requested Project Manager.
    """
    skills_str = ", ".join(candidate_skills) if candidate_skills else "None specified"
    title = "NEW TEAM MEMBER REQUEST"
    message = (
        f"{candidate_name} has requested to join your team.\n\n"
        f"Role: {candidate_role}\n"
        f"Skills: {skills_str}\n"
        f"Team Capacity: {active_capacity} / {max_capacity}\n\n"
        f"Please review the candidate."
    )
    return await create_notification(
        db=db,
        user_id=pm_user_id,
        notification_type="TEAM_MEMBER_REQUESTED",
        title=title,
        message=message,
        severity="medium",
    )


async def notify_team_member_assigned(
    db,
    member_emp_id: str,
    pm_name: str,
    role_name: str,
) -> Optional[Dict[str, Any]]:
    """
    Triggered when a Team Member's PM request is approved.
    Recipient: The assigned Team Member.
    """
    target_uid = await get_user_id_for_employee(db, member_emp_id)
    if not target_uid:
        return None

    title = "TEAM ASSIGNMENT"
    message = (
        f"You have been assigned to {pm_name}'s team.\n\n"
        f"Role: {role_name}"
    )
    return await create_notification(
        db=db,
        user_id=target_uid,
        notification_type="TEAM_MEMBER_ASSIGNED",
        title=title,
        message=message,
        severity="medium",
    )


async def notify_team_member_rejected(
    db,
    member_emp_id: str,
    pm_name: str,
    reason: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Triggered when a Team Member's PM request is rejected.
    Recipient: The Team Member.
    """
    target_uid = await get_user_id_for_employee(db, member_emp_id)
    if not target_uid:
        return None

    title = "TEAM REQUEST UPDATE"
    reason_str = f"\n\nReason: {reason}" if reason else ""
    message = f"Your request to join {pm_name}'s team was not approved.{reason_str}"
    return await create_notification(
        db=db,
        user_id=target_uid,
        notification_type="TEAM_MEMBER_REQUEST_REJECTED",
        title=title,
        message=message,
        severity="medium",
    )


async def notify_cross_pm_resource_requested(
    db,
    home_pm_user_id: str,
    requesting_pm_name: str,
    project_name: str,
    candidate_name: str,
    candidate_role: str,
    task_title: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Triggered when PM1 requests a cross-PM candidate from PM2's direct team.
    Recipient: Candidate's Home Project Manager (PM2).
    """
    task_info = f" for task '{task_title}'" if task_title else ""
    title = "CROSS-PM RESOURCE ALLOCATION REQUEST"
    message = (
        f"{requesting_pm_name} has requested {candidate_name} ({candidate_role}) "
        f"to contribute to project '{project_name}'{task_info}.\n\n"
        f"Please review and approve or reject this project allocation."
    )
    return await create_notification(
        db=db,
        user_id=home_pm_user_id,
        notification_type="CROSS_PM_RESOURCE_REQUESTED",
        title=title,
        message=message,
        severity="medium",
    )


async def notify_cross_pm_resource_approved(
    db,
    requesting_pm_user_id: str,
    candidate_name: str,
    project_name: str,
    approver_name: str,
) -> Optional[Dict[str, Any]]:
    """
    Triggered when Home PM2 approves cross-PM resource allocation request.
    Recipient: Requesting Project Manager (PM1).
    """
    title = "CROSS-PM RESOURCE APPROVED"
    message = (
        f"{approver_name} has approved the allocation of {candidate_name} "
        f"for your project '{project_name}'."
    )
    return await create_notification(
        db=db,
        user_id=requesting_pm_user_id,
        notification_type="CROSS_PM_RESOURCE_APPROVED",
        title=title,
        message=message,
        severity="medium",
    )


async def notify_cross_pm_resource_rejected(
    db,
    requesting_pm_user_id: str,
    candidate_name: str,
    project_name: str,
    approver_name: str,
) -> Optional[Dict[str, Any]]:
    """
    Triggered when Home PM2 rejects cross-PM resource allocation request.
    Recipient: Requesting Project Manager (PM1).
    """
    title = "CROSS-PM RESOURCE REJECTED"
    message = (
        f"{approver_name} was unable to approve the allocation of {candidate_name} "
        f"for project '{project_name}' due to team capacity constraints."
    )
    return await create_notification(
        db=db,
        user_id=requesting_pm_user_id,
        notification_type="CROSS_PM_RESOURCE_REJECTED",
        title=title,
        message=message,
        severity="medium",
    )


