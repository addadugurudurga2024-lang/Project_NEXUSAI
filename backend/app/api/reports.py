from fastapi import APIRouter, Depends, HTTPException
from app.core.deps import get_current_user, require_manager_or_admin
from app.db.database import get_database
# pyrefly: ignore [missing-import]
from bson import ObjectId
from typing import Optional

router = APIRouter()


def serialize_report(r: dict) -> dict:
    return {
        "id": str(r["_id"]),
        "project_id": str(r.get("projectId") or r.get("project_id", "")),
        "project_name": r.get("project_name"),
        "generated_by": str(r.get("generatedBy") or r.get("generated_by", "")),
        "generated_by_name": r.get("generated_by_name"),
        "report_type": r.get("reportType") or r.get("report_type", "executive_summary"),
        "title": r.get("title"),
        "content": r.get("content"),
        "created_at": r.get("createdAt") or r.get("created_at"),
    }


@router.post("/generate/{project_id}")
async def generate_report(
    project_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Generate a comprehensive project intelligence report from real MongoDB data."""
    from app.services.report_service import generate_project_report

    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    user_name = current_user.get("name", "Project Manager")
    user_id = str(current_user["_id"])

    try:
        report = await generate_project_report(
            project_id=project_id,
            db=db,
            user_id=user_id,
            user_name=user_name,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

    return serialize_report(report)


@router.get("/")
async def list_reports(
    project_id: Optional[str] = None,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """List all generated reports, optionally filtered by project."""
    if current_user.get("role") not in ["admin", "project_manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")

    query = {}
    if project_id:
        query["$or"] = [{"projectId": project_id}, {"project_id": project_id}]

    reports = await db.reports.find(query).sort("createdAt", -1).to_list(100)
    return [serialize_report(r) for r in reports]


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Get a specific report by ID."""
    if current_user.get("role") not in ["admin", "project_manager"]:
        raise HTTPException(status_code=403, detail="Manager or Admin access required")

    try:
        report = await db.reports.find_one({"_id": ObjectId(report_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid report ID")
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return serialize_report(report)


@router.delete("/{report_id}")
async def delete_report(
    report_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Delete a report."""
    try:
        result = await db.reports.delete_one({"_id": ObjectId(report_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid report ID")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"message": "Report deleted"}
