"""
Activity Service — Phase 6
Records project-level activity events to the `project_activities` MongoDB collection.

This is a NEW service, separate from notification_service.
It does NOT replace or modify any existing notification infrastructure.
"""
from datetime import datetime
from typing import Optional

ACTIVITY_TYPES = {
    "PROJECT_CREATED",
    "PM_ASSIGNED",
    "MEMBER_ADDED",
    "MEMBER_REMOVED",
    "TASK_CREATED",
    "TASK_ASSIGNED",
    "TASK_REASSIGNED",
    "TASK_STATUS_CHANGED",
    "ISSUE_CREATED",
    "ISSUE_ASSIGNED",
    "ISSUE_RESOLVED",
    "ISSUE_STATUS_CHANGED",
}


async def create_activity(
    db,
    project_id: str,
    activity_type: str,
    message: str,
    actor_user_id: Optional[str] = None,
    actor_name: Optional[str] = None,
    related_entity_id: Optional[str] = None,
) -> None:
    """
    Persist a single activity event to project_activities.
    Called by projects.py, tasks.py, and issues.py after real DB operations.
    """
    if not project_id:
        return

    doc = {
        "project_id": project_id,
        "actor_user_id": actor_user_id or "",
        "actor_name": actor_name or "System",
        "activity_type": activity_type,
        "message": message,
        "related_entity_id": related_entity_id or "",
        "timestamp": datetime.utcnow(),
    }
    try:
        await db.project_activities.insert_one(doc)
    except Exception:
        pass  # Activity recording must never break the primary operation




