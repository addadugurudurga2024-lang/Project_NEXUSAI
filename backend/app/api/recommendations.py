from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.deps import get_current_user, require_manager_or_admin
from app.db.database import get_database
# pyrefly: ignore [missing-import]
from bson import ObjectId
from datetime import datetime
from typing import List, Optional
from app.models.recommendation import RecommendationResponse, RecommendationUpdate

router = APIRouter()


def serialize_rec(r: dict) -> dict:
    return {
        "id": str(r["_id"]),
        "project_id": str(r.get("projectId") or r.get("project_id", "")),
        "project_name": r.get("project_name"),
        "employee_id": str(r.get("employeeId") or r.get("employee_id", "")) if (r.get("employeeId") or r.get("employee_id")) else None,
        "employee_name": r.get("employee_name"),
        "category": r.get("category", "General"),
        "priority": r.get("priority", "medium"),
        "title": r.get("title", r.get("action", "Recommendation")),
        "description": r.get("description"),
        "reason": r.get("reason", ""),
        "suggested_action": r.get("suggestedAction") or r.get("suggested_action") or r.get("action", ""),
        "expected_impact": r.get("expectedImpact") or r.get("expected_impact") or r.get("impact", ""),
        "status": r.get("status", "pending"),
        "created_at": r.get("createdAt") or r.get("created_at"),
        "updated_at": r.get("updatedAt") or r.get("updated_at"),
    }


@router.get("/", response_model=List[RecommendationResponse])
async def list_recommendations(
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    query = {}
    if project_id:
        query["$or"] = [{"projectId": project_id}, {"project_id": project_id}]
    if status:
        query["status"] = status
    if priority:
        query["priority"] = priority

    recs = await db.recommendations.find(query).sort("createdAt", -1).to_list(500)
    return [serialize_rec(r) for r in recs]


@router.post("/generate/{project_id}")
async def generate_recommendations(
    project_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Generate AI recommendations based on real project data, ML inferences, and employee workload."""
    from app.services.recommendation_service import generate_project_recommendations

    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    recommendations = await generate_project_recommendations(project_id, db)
    return {"recommendations": recommendations, "count": len(recommendations)}


@router.patch("/{rec_id}/status")
@router.put("/{rec_id}/status")
async def update_recommendation_status(
    rec_id: str,
    data: RecommendationUpdate,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Update status of a recommendation (pending -> reviewed -> accepted -> rejected -> completed)."""
    valid_statuses = ["pending", "reviewed", "accepted", "rejected", "completed", "implemented"]
    if data.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Valid statuses: {valid_statuses}")

    try:
        rec = await db.recommendations.find_one({"_id": ObjectId(rec_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid recommendation ID")

    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    update_fields = {
        "status": data.status,
        "updatedAt": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "decidedBy": str(current_user["_id"]),
    }
    if data.notes:
        update_fields["decisionNotes"] = data.notes

    await db.recommendations.update_one(
        {"_id": ObjectId(rec_id)},
        {"$set": update_fields}
    )

    updated = await db.recommendations.find_one({"_id": ObjectId(rec_id)})
    return serialize_rec(updated)


@router.post("/{rec_id}/accept")
async def accept_recommendation(
    rec_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Convenience endpoint to accept a recommendation."""
    try:
        rec = await db.recommendations.find_one({"_id": ObjectId(rec_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid recommendation ID")

    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    await db.recommendations.update_one(
        {"_id": ObjectId(rec_id)},
        {
            "$set": {
                "status": "accepted",
                "acceptedAt": datetime.utcnow(),
                "acceptedBy": str(current_user["_id"]),
                "updated_at": datetime.utcnow(),
            }
        }
    )
    return {"message": "Recommendation accepted successfully", "status": "accepted"}


@router.post("/{rec_id}/reject")
async def reject_recommendation(
    rec_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Convenience endpoint to reject a recommendation."""
    try:
        rec = await db.recommendations.find_one({"_id": ObjectId(rec_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid recommendation ID")

    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    await db.recommendations.update_one(
        {"_id": ObjectId(rec_id)},
        {
            "$set": {
                "status": "rejected",
                "rejectedAt": datetime.utcnow(),
                "rejectedBy": str(current_user["_id"]),
                "updated_at": datetime.utcnow(),
            }
        }
    )
    return {"message": "Recommendation rejected", "status": "rejected"}


@router.post("/{rec_id}/complete")
async def complete_recommendation(
    rec_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Convenience endpoint to mark recommendation as completed/implemented."""
    try:
        rec = await db.recommendations.find_one({"_id": ObjectId(rec_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid recommendation ID")

    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    await db.recommendations.update_one(
        {"_id": ObjectId(rec_id)},
        {
            "$set": {
                "status": "completed",
                "completedAt": datetime.utcnow(),
                "completedBy": str(current_user["_id"]),
                "updated_at": datetime.utcnow(),
            }
        }
    )
    return {"message": "Recommendation marked as completed", "status": "completed"}
