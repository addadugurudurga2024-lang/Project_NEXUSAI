from fastapi import APIRouter, Depends, HTTPException, Query
from app.models.sprint import SprintCreate, SprintUpdate, SprintResponse
from app.core.deps import get_current_user, require_manager_or_admin
from app.db.database import get_database
# pyrefly: ignore [missing-import]
from bson import ObjectId
from datetime import datetime
from typing import List, Optional

router = APIRouter()


def serialize_sprint(s: dict, task_count: int = 0) -> dict:
    return {
        "id": str(s["_id"]),
        "name": s.get("name", ""),
        "project_id": s.get("project_id", ""),
        "goal": s.get("goal"),
        "status": s.get("status", "planning"),
        "start_date": s.get("start_date"),
        "end_date": s.get("end_date"),
        "capacity_hours": s.get("capacity_hours", 0.0),
        "planned_story_points": s.get("planned_story_points", 0),
        "completed_story_points": s.get("completed_story_points", 0),
        "velocity": s.get("velocity", 0.0),
        "task_count": task_count,
        "created_at": s.get("created_at"),
    }


@router.get("/", response_model=List[SprintResponse])
async def list_sprints(
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    query = {}
    if project_id:
        query["project_id"] = project_id
    if status:
        query["status"] = status
    sprints = await db.sprints.find(query).sort("created_at", -1).to_list(200)
    result = []
    for s in sprints:
        task_count = await db.tasks.count_documents({"sprint_id": str(s["_id"])})
        result.append(serialize_sprint(s, task_count))
    return result


@router.post("/", response_model=SprintResponse)
async def create_sprint(
    data: SprintCreate,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    doc = data.model_dump()
    doc["completed_story_points"] = 0
    doc["velocity"] = 0.0
    doc["created_at"] = datetime.utcnow()
    result = await db.sprints.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_sprint(doc)


@router.get("/{sprint_id}", response_model=SprintResponse)
async def get_sprint(
    sprint_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    try:
        s = await db.sprints.find_one({"_id": ObjectId(sprint_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid sprint ID")
    if not s:
        raise HTTPException(status_code=404, detail="Sprint not found")
    task_count = await db.tasks.count_documents({"sprint_id": sprint_id})
    return serialize_sprint(s, task_count)


@router.put("/{sprint_id}", response_model=SprintResponse)
async def update_sprint(
    sprint_id: str,
    data: SprintUpdate,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    try:
        s = await db.sprints.find_one({"_id": ObjectId(sprint_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid sprint ID")
    if not s:
        raise HTTPException(status_code=404, detail="Sprint not found")
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    await db.sprints.update_one({"_id": ObjectId(sprint_id)}, {"$set": update_data})
    updated = await db.sprints.find_one({"_id": ObjectId(sprint_id)})
    task_count = await db.tasks.count_documents({"sprint_id": sprint_id})
    return serialize_sprint(updated, task_count)
