"""
Notification Service for NexusAI
Handles event-driven notifications across projects, tasks, risk alerts, and recommendations.
"""
# pyrefly: ignore [missing-import]
from bson import ObjectId
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any


async def create_notification(
    db,
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    related_project_id: Optional[str] = None,
    severity: str = "medium",
) -> Optional[Dict[str, Any]]:
    """
    Creates a notification for a user, avoiding duplicate spam within a 1-hour window.
    """
    if not user_id:
        return None

    # Check for recent duplicate unread notification
    cutoff = datetime.utcnow() - timedelta(hours=1)
    existing = await db.notifications.find_one({
        "userId": user_id,
        "type": notification_type,
        "title": title,
        "isRead": False,
        "createdAt": {"$gte": cutoff},
    })
    if existing:
        return None

    # Authoritative schema document
    doc = {
        "userId": user_id,
        "user_id": user_id,  # compatibility
        "type": notification_type,
        "title": title,
        "message": message,
        "relatedProjectId": related_project_id,
        "related_project_id": related_project_id,  # compatibility
        "severity": severity,
        "isRead": False,
        "read": False,  # compatibility
        "createdAt": datetime.utcnow(),
        "created_at": datetime.utcnow(),
    }

    result = await db.notifications.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc["_id"] = str(result.inserted_id)
    return doc


async def notify_project_stakeholders(
    db,
    project_id: str,
    notification_type: str,
    title: str,
    message: str,
    severity: str = "medium",
):
    """
    Notifies the project manager and admins about a project-level event.
    """
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id)})
    except Exception:
        project = None

    recipients = set()

    # Add project manager
    if project and project.get("manager_id"):
        recipients.add(str(project["manager_id"]))
    elif project and project.get("projectManagerId"):
        recipients.add(str(project["projectManagerId"]))

    # Also notify all admin users
    admins = await db.users.find({"role": "admin"}).to_list(50)
    for a in admins:
        recipients.add(str(a["_id"]))

    for uid in recipients:
        await create_notification(
            db=db,
            user_id=uid,
            notification_type=notification_type,
            title=title,
            message=message,
            related_project_id=project_id,
            severity=severity,
        )
