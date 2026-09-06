from fastapi import APIRouter, Depends, HTTPException
from app.core.deps import get_current_user, require_manager_or_admin
from app.db.database import get_database
# pyrefly: ignore [missing-import]
from bson import ObjectId

router = APIRouter()


@router.get("/{project_id}")
async def get_resource_optimization(
    project_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Compute resource optimization recommendations for a project."""
    from app.services.resource_optimizer import compute_resource_optimization

    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await compute_resource_optimization(project_id, db)
    return result


@router.post("/apply/{allocation_id}")
async def apply_allocation(
    allocation_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Apply a resource reallocation — reassigns the task to the suggested employee in MongoDB."""
    from app.services.resource_optimizer import apply_resource_reallocation

    user_id = str(current_user["_id"])
    try:
        result = await apply_resource_reallocation(allocation_id, db, applied_by_user_id=user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reallocation failed: {str(e)}")

    return result
