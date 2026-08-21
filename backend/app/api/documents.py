from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from app.core.deps import get_current_user, require_manager_or_admin
from app.db.database import get_database
# pyrefly: ignore [missing-import]
from bson import ObjectId
from datetime import datetime
import os, shutil, uuid
from app.core.config import settings
from typing import Optional

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".xlsx"}
MAX_SIZE = settings.max_upload_size_mb * 1024 * 1024


@router.get("/")
async def list_documents(
    project_id: Optional[str] = None,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    query = {}
    if project_id:
        query["project_id"] = project_id
    docs = await db.project_documents.find(query).sort("upload_date", -1).to_list(200)
    result = []
    for d in docs:
        d["id"] = str(d["_id"])
        del d["_id"]
        result.append(d)
    return result


@router.post("/upload")
async def upload_document(
    project_id: str = Form(...),
    file: UploadFile = File(...),
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    # Validate extension
    _, ext = os.path.splitext(file.filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type {ext} not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Max size: {settings.max_upload_size_mb}MB")

    # Validate project exists
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Save file securely
    upload_dir = os.path.abspath(settings.upload_dir)
    os.makedirs(upload_dir, exist_ok=True)
    safe_name = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(upload_dir, safe_name)
    with open(file_path, "wb") as f:
        f.write(content)

    # Persist metadata
    doc = {
        "project_id": project_id,
        "original_filename": file.filename,
        "stored_filename": safe_name,
        "file_type": ext.lower(),
        "file_size": len(content),
        "storage_path": file_path,
        "upload_date": datetime.utcnow(),
        "uploaded_by": str(current_user["_id"]),
        "analysis_status": "pending",
    }
    result = await db.project_documents.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc["created_at"] = doc.get("upload_date")
    del doc["_id"]
    return doc


@router.post("/{document_id}/analyze")
@router.post("/analyze/{document_id}")
async def analyze_document(
    document_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Run AI analysis pipeline on an uploaded document."""
    from app.services.document_service import analyze_document_pipeline

    try:
        doc = await db.project_documents.find_one({"_id": ObjectId(document_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid document ID")
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Run analysis pipeline
    analysis_result = await analyze_document_pipeline(doc, db)

    # Update document status
    await db.project_documents.update_one(
        {"_id": ObjectId(document_id)},
        {"$set": {"analysis_status": "completed", "analyzed_at": datetime.utcnow()}}
    )

    return analysis_result


@router.get("/{document_id}/analysis")
@router.get("/analysis/{document_id}")
async def get_document_analysis(
    document_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    analysis = await db.document_analysis.find_one({"document_id": document_id})
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found. Run analysis first.")
    analysis["id"] = str(analysis["_id"])
    del analysis["_id"]
    return analysis
