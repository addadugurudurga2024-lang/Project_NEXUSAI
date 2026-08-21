from fastapi import APIRouter, Depends, HTTPException, Query
from app.models.issue import IssueCreate, IssueUpdate, IssueResponse
from app.core.deps import get_current_user
from app.db.database import get_database
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


@router.get("/", response_model=List[IssueResponse])
async def list_issues(
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    query = {}
    if project_id:
        query["project_id"] = project_id
    if status:
        query["status"] = status
    if severity:
        query["severity"] = severity
    issues = await db.issues.find(query).sort("created_at", -1).to_list(500)
    result = []
    for i in issues:
        assignee_name = None
        if i.get("assignee_id"):
            try:
                emp = await db.employees.find_one({"_id": ObjectId(i["assignee_id"])})
                if emp:
                    assignee_name = emp.get("name")
            except Exception:
                pass
        result.append(serialize_issue(i, assignee_name))
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
    assignee_name = None
    if i.get("assignee_id"):
        try:
            emp = await db.employees.find_one({"_id": ObjectId(i["assignee_id"])})
            if emp:
                assignee_name = emp.get("name")
        except Exception:
            pass
    return serialize_issue(i, assignee_name)


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
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if update_data.get("status") == "resolved" and not i.get("resolved_at"):
        update_data["resolved_at"] = datetime.utcnow()
    update_data["updated_at"] = datetime.utcnow()
    await db.issues.update_one({"_id": ObjectId(issue_id)}, {"$set": update_data})
    updated = await db.issues.find_one({"_id": ObjectId(issue_id)})
    return serialize_issue(updated)


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
