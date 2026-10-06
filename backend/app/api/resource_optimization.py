from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, Dict, Any
# pyrefly: ignore [missing-import]
from bson import ObjectId
from app.core.deps import get_current_user, require_manager_or_admin
from app.db.database import get_database

router = APIRouter()


def serialize_doc(doc: dict) -> dict:
    if not doc:
        return {}
    res = dict(doc)
    res["id"] = str(doc["_id"])
    res["_id"] = str(doc["_id"])
    if "requested_at" in res and res["requested_at"]:
        res["requested_at"] = res["requested_at"].isoformat()
    if "reviewed_at" in res and res["reviewed_at"]:
        res["reviewed_at"] = res["reviewed_at"].isoformat()
    return res


@router.get("/{project_id}")
async def get_resource_optimization(
    project_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Compute 3-Level resource optimization recommendations for a project."""
    from app.services.resource_optimizer import compute_resource_optimization

    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id) if ObjectId.is_valid(project_id) else project_id})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID")

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    role = current_user.get("role", "team_member")
    uid = str(current_user["_id"])

    if role == "project_manager":
        from app.services.project_scoping_service import get_authorized_project_ids
        authorized_pids = await get_authorized_project_ids(db, current_user)
        if project_id not in authorized_pids:
            raise HTTPException(status_code=403, detail="Access denied: You do not manage this project")

    result = await compute_resource_optimization(project_id, db, current_user=current_user)
    return result


@router.post("/apply/{allocation_id}")
async def apply_allocation(
    allocation_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Apply an internal resource reallocation suggestion."""
    from app.services.resource_optimizer import apply_resource_reallocation

    role = current_user.get("role", "team_member")
    uid = str(current_user["_id"])

    if role == "project_manager":
        try:
            alloc = await db.resource_allocations.find_one({"_id": ObjectId(allocation_id) if ObjectId.is_valid(allocation_id) else allocation_id})
        except Exception:
            alloc = None
        if not alloc:
            raise HTTPException(status_code=404, detail="Resource allocation recommendation not found")
        project_id = str(alloc.get("projectId") or alloc.get("project_id") or "")
        from app.services.project_scoping_service import get_authorized_project_ids
        authorized_pids = await get_authorized_project_ids(db, current_user)
        if project_id not in authorized_pids:
            raise HTTPException(status_code=403, detail="Access denied: Cannot apply allocation for another PM's project")

    try:
        result = await apply_resource_reallocation(allocation_id, db, applied_by_user_id=uid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reallocation failed: {str(e)}")

    return result


@router.post("/reject/{allocation_id}")
async def reject_allocation(
    allocation_id: str,
    reason: Optional[str] = Query(None),
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Reject or dismiss an internal resource reallocation suggestion."""
    from app.services.resource_optimizer import reject_resource_reallocation

    role = current_user.get("role", "team_member")
    uid = str(current_user["_id"])

    if role == "project_manager":
        try:
            alloc = await db.resource_allocations.find_one({"_id": ObjectId(allocation_id) if ObjectId.is_valid(allocation_id) else allocation_id})
        except Exception:
            alloc = None
        if not alloc:
            raise HTTPException(status_code=404, detail="Resource allocation recommendation not found")
        project_id = str(alloc.get("projectId") or alloc.get("project_id") or "")
        from app.services.project_scoping_service import get_authorized_project_ids
        authorized_pids = await get_authorized_project_ids(db, current_user)
        if project_id not in authorized_pids:
            raise HTTPException(status_code=403, detail="Access denied: Cannot reject allocation for another PM's project")

    try:
        result = await reject_resource_reallocation(allocation_id, db, user_id=uid, reason=reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rejection failed: {str(e)}")

    return result



@router.post("/request-cross-pm", response_model=Dict[str, Any])
async def submit_cross_pm_request(
    project_id: str = Query(...),
    candidate_employee_id: str = Query(...),
    task_id: Optional[str] = Query(None),
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Submits a cross-PM candidate resource request. Requires Home PM approval."""
    from app.services.resource_optimizer import request_cross_pm_resource

    # Check project ownership
    from app.services.project_scoping_service import get_authorized_project_ids
    role = current_user.get("role", "team_member")
    if role == "project_manager":
        authorized_pids = await get_authorized_project_ids(db, current_user)
        if project_id not in authorized_pids:
            raise HTTPException(status_code=403, detail="Access denied: Cannot request resource for a project you do not manage")

    try:
        doc = await request_cross_pm_resource(
            db=db,
            requesting_user=current_user,
            project_id=project_id,
            candidate_emp_id=candidate_employee_id,
            task_id=task_id,
        )
        return serialize_doc(doc)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cross-pm-requests/{request_id}/approve", response_model=Dict[str, Any])
async def approve_cross_pm_request(
    request_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Home PM or Admin approves cross-PM resource project allocation."""
    from app.services.resource_optimizer import approve_cross_pm_resource
    try:
        res = await approve_cross_pm_resource(db, request_id, current_user)
        return serialize_doc(res)
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cross-pm-requests/{request_id}/reject", response_model=Dict[str, Any])
async def reject_cross_pm_request(
    request_id: str,
    reason: Optional[str] = Query(None),
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Home PM or Admin rejects cross-PM resource project allocation."""
    from app.services.resource_optimizer import reject_cross_pm_resource
    try:
        res = await reject_cross_pm_resource(db, request_id, current_user, reason)
        return serialize_doc(res)
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
