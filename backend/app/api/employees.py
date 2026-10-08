from fastapi import APIRouter, Depends, HTTPException, Query
from app.models.employee import EmployeeCreate, EmployeeUpdate, EmployeeResponse
from app.core.deps import get_current_user, require_manager_or_admin
from app.db.database import get_database
# pyrefly: ignore [missing-import]
from bson import ObjectId
from datetime import datetime
from typing import List, Optional

router = APIRouter()


def serialize_employee(e: dict) -> dict:
    return {
        "id": str(e["_id"]),
        "name": e.get("name", ""),
        "email": e.get("email", ""),
        "role": e.get("role", ""),
        "specialization": e.get("specialization"),
        "skills": e.get("skills", []),
        "experience_years": float(e.get("experience_years", 0.0)),
        "weekly_capacity_hours": float(e.get("weekly_capacity_hours", 40.0)),
        "availability_percentage": float(e.get("availability_percentage", 100.0)),
        "status": e.get("status", "active"),
        "user_id": str(e["user_id"]) if e.get("user_id") else None,
        "assigned_project_ids": [str(x) for x in e.get("assigned_project_ids", [])],
        "created_at": e.get("created_at"),
    }


@router.get("/", response_model=List[EmployeeResponse])
async def list_employees(
    status: Optional[str] = None,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    role = current_user.get("role", "team_member")
    query = {}
    if status:
        query["status"] = status

    if role == "admin":
        pass
    elif role in ("project_manager", "team_member"):
        from app.services.project_scoping_service import get_authorized_employee_ids
        authorized_eids = await get_authorized_employee_ids(db, current_user)
        valid_objs = [ObjectId(x) for x in authorized_eids if ObjectId.is_valid(x)]
        query["_id"] = {"$in": valid_objs} if valid_objs else {"_id": None}

    employees = await db.employees.find(query).sort("name", 1).to_list(500)
    return [serialize_employee(e) for e in employees]


@router.post("/", response_model=EmployeeResponse)
async def create_employee(
    data: EmployeeCreate,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    existing = await db.employees.find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Employee with this email already exists")
    doc = data.model_dump()
    doc["assigned_project_ids"] = []
    doc["created_at"] = datetime.utcnow()
    result = await db.employees.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_employee(doc)


@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    try:
        e = await db.employees.find_one({"_id": ObjectId(employee_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid employee ID")
    if not e:
        raise HTTPException(status_code=404, detail="Employee not found")

    role = current_user.get("role", "team_member")
    if role in ("project_manager", "team_member"):
        from app.services.project_scoping_service import get_authorized_employee_ids
        authorized_eids = await get_authorized_employee_ids(db, current_user)
        if employee_id not in authorized_eids:
            raise HTTPException(status_code=403, detail="Access denied: Employee not in your authorized scope")

    return serialize_employee(e)


@router.put("/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: str,
    data: EmployeeUpdate,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    try:
        e = await db.employees.find_one({"_id": ObjectId(employee_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid employee ID")
    if not e:
        raise HTTPException(status_code=404, detail="Employee not found")
    role = current_user.get("role", "team_member")
    if role == "project_manager":
        from app.services.project_scoping_service import get_authorized_employee_ids
        authorized_eids = await get_authorized_employee_ids(db, current_user)
        if employee_id not in authorized_eids:
            raise HTTPException(status_code=403, detail="Access denied: Employee not in your authorized scope")

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    await db.employees.update_one({"_id": ObjectId(employee_id)}, {"$set": update_data})
    updated = await db.employees.find_one({"_id": ObjectId(employee_id)})
    return serialize_employee(updated)


@router.delete("/{employee_id}")
async def delete_employee(
    employee_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    role = current_user.get("role", "team_member")
    if role != "admin":
        raise HTTPException(status_code=403, detail="Access denied: Only administrators can delete employee profiles")

    try:
        result = await db.employees.delete_one({"_id": ObjectId(employee_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid employee ID")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Employee not found")
    return {"message": "Employee deleted successfully"}


@router.post("/{employee_id}/assign-project/{project_id}")
async def assign_project(
    employee_id: str,
    project_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    role = current_user.get("role", "team_member")
    uid = str(current_user["_id"])

    if role == "project_manager":
        from app.services.project_scoping_service import get_authorized_project_ids, is_employee_authorized_for_pm
        authorized_pids = await get_authorized_project_ids(db, current_user)
        if project_id not in authorized_pids:
            raise HTTPException(status_code=403, detail="Access denied: You do not manage this project")
        is_auth = await is_employee_authorized_for_pm(db, uid, employee_id, project_id=project_id)
        if not is_auth:
            raise HTTPException(status_code=403, detail="Access denied: Employee is not in your authorized team capacity")

    try:
        await db.employees.update_one(
            {"_id": ObjectId(employee_id)},
            {"$addToSet": {"assigned_project_ids": project_id}},
        )
        await db.projects.update_one(
            {"_id": ObjectId(project_id)},
            {"$addToSet": {"team_member_ids": employee_id}},
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")
    return {"message": "Employee assigned to project"}
