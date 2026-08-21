from fastapi import APIRouter, Depends, HTTPException, Query
from app.models.task import TaskCreate, TaskUpdate, TaskResponse
from app.core.deps import get_current_user
from app.db.database import get_database
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


@router.get("/", response_model=List[TaskResponse])
async def list_tasks(
    project_id: Optional[str] = None,
    sprint_id: Optional[str] = None,
    assignee_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    query = {}
    if project_id:
        query["project_id"] = project_id
    if sprint_id:
        query["sprint_id"] = sprint_id
    if assignee_id:
        query["assignee_id"] = assignee_id
    if status:
        query["status"] = status
    tasks = await db.tasks.find(query).sort("created_at", -1).to_list(500)
    result = []
    for t in tasks:
        assignee_name = None
        if t.get("assignee_id"):
            try:
                emp = await db.employees.find_one({"_id": ObjectId(t["assignee_id"])})
                if emp:
                    assignee_name = emp.get("name")
            except Exception:
                pass
        result.append(serialize_task(t, assignee_name))
    return result


@router.post("/", response_model=TaskResponse)
async def create_task(
    data: TaskCreate,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    doc = data.model_dump()
    doc["created_at"] = datetime.utcnow()
    doc["updated_at"] = datetime.utcnow()
    result = await db.tasks.insert_one(doc)
    doc["_id"] = result.inserted_id
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
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    await db.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": update_data})
    updated = await db.tasks.find_one({"_id": ObjectId(task_id)})
    return serialize_task(updated)


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    try:
        result = await db.tasks.delete_one({"_id": ObjectId(task_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid task ID")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted successfully"}
