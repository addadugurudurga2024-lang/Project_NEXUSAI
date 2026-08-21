from fastapi import APIRouter, Depends, HTTPException, Query
from app.models.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.core.deps import get_current_user, require_manager_or_admin
from app.db.database import get_database
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


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    query = {}
    if status:
        query["status"] = status
    if priority:
        query["priority"] = priority
    projects = await db.projects.find(query).sort("created_at", -1).to_list(200)
    result = []
    for p in projects:
        manager_name = None
        if p.get("manager_id"):
            try:
                mgr = await db.users.find_one({"_id": ObjectId(p["manager_id"])})
                if mgr:
                    manager_name = mgr.get("name")
            except Exception:
                pass
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
    result = await db.projects.insert_one(doc)
    doc["_id"] = result.inserted_id
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
    manager_name = None
    if p.get("manager_id"):
        try:
            mgr = await db.users.find_one({"_id": ObjectId(p["manager_id"])})
            if mgr:
                manager_name = mgr.get("name")
        except Exception:
            pass
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
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    await db.projects.update_one({"_id": ObjectId(project_id)}, {"$set": update_data})
    updated = await db.projects.find_one({"_id": ObjectId(project_id)})
    return serialize_project(updated)


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
