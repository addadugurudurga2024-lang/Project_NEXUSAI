from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, Dict, Any, List
# pyrefly: ignore [missing-import]
from bson import ObjectId

from app.core.deps import get_current_user, require_manager_or_admin
from app.db.database import get_database
from app.models.prediction_tracking import (
    OutcomeRecordRequest,
    ModelPerformanceMetrics,
    TrajectoryResponse,
)
from app.services.prediction_tracking_service import (
    record_actual_outcome,
    get_project_prediction_history,
    get_project_trajectory,
    get_model_performance_summary,
    auto_evaluate_project_outcomes,
    _serialize_doc,
)

router = APIRouter()


@router.get("/performance", response_model=List[ModelPerformanceMetrics])
async def get_performance_endpoint(
    project_id: Optional[str] = Query(None),
    prediction_type: Optional[str] = Query(None),
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    Returns aggregated ML performance metrics (MAE, RMSE, Accuracy, F1)
    computed strictly from evaluated ground truth outcomes within the user's scope.
    """
    try:
        return await get_model_performance_summary(
            db=db,
            current_user=current_user,
            project_id=project_id,
            prediction_type_filter=prediction_type,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/history", response_model=List[Dict[str, Any]])
async def get_history_all_endpoint(
    project_id: Optional[str] = Query(None),
    prediction_type: Optional[str] = Query(None),
    evaluation_status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    Returns historical immutable prediction snapshots across all authorized projects or for a specific project.
    """
    try:
        return await get_project_prediction_history(
            db=db,
            project_id=project_id,
            current_user=current_user,
            prediction_type=prediction_type,
            evaluation_status=evaluation_status,
            limit=limit,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/history/{project_id}", response_model=List[Dict[str, Any]])
async def get_history_endpoint(
    project_id: str,
    prediction_type: Optional[str] = Query(None),
    evaluation_status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    Returns historical immutable prediction snapshots for a project.
    """
    try:
        return await get_project_prediction_history(
            db=db,
            project_id=project_id,
            current_user=current_user,
            prediction_type=prediction_type,
            evaluation_status=evaluation_status,
            limit=limit,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/initialize", response_model=Dict[str, Any])
async def initialize_prediction_snapshots_endpoint(
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    Idempotent initialization endpoint that ensures live projects and active direct team employees
    have legitimate immutable prediction snapshots in db.prediction_history.
    """
    try:
        from app.services.prediction_tracking_service import ensure_prediction_snapshots_initialized
        return await ensure_prediction_snapshots_initialized(db)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/trajectory/{project_id}", response_model=TrajectoryResponse)
async def get_trajectory_endpoint(
    project_id: str,
    prediction_type: str = Query("PROJECT_RISK"),
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    Returns chronological prediction trajectory and calculated trend (IMPROVING, DETERIORATING, STABLE).
    """
    try:
        return await get_project_trajectory(
            db=db,
            project_id=project_id,
            current_user=current_user,
            prediction_type=prediction_type,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{prediction_id}", response_model=Dict[str, Any])
async def get_prediction_detail_endpoint(
    prediction_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    Retrieves the complete snapshot and outcome audit trail of a single prediction record.
    """
    try:
        oid = ObjectId(prediction_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid prediction ID format")

    doc = await db.prediction_history.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction record not found")

    role = current_user.get("role", "team_member")
    if role == "project_manager" and doc.get("project_id"):
        from app.services.project_scoping_service import get_authorized_project_ids
        authorized_pids = await get_authorized_project_ids(db, current_user)
        if doc["project_id"] not in authorized_pids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: You do not manage this project")

    return _serialize_doc(doc)


@router.post("/{prediction_id}/outcome", response_model=Dict[str, Any])
async def record_outcome_endpoint(
    prediction_id: str,
    req: OutcomeRecordRequest,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    Records or updates the observed actual outcome for a prediction snapshot.
    """
    try:
        return await record_actual_outcome(
            db=db,
            prediction_id=prediction_id,
            req=req,
            current_user=current_user,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/project/{project_id}/auto-evaluate", response_model=Dict[str, Any])
async def auto_evaluate_project_endpoint(
    project_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    Auto-evaluates pending predictions for completed projects based on verified lifecycle data.
    """
    try:
        return await auto_evaluate_project_outcomes(
            db=db,
            project_id=project_id,
            current_user=current_user,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
