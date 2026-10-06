from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, Dict, Any, List
from app.core.deps import get_current_user, require_manager_or_admin
from app.db.database import get_database
from app.models.decision import (
    DecisionCreate,
    DecisionActionRequest,
    DecisionResponse,
)
from app.services.decision_service import (
    gather_decision_intelligence,
    create_decision,
    get_decisions,
    get_decision_by_id,
    record_decision_action,
    prepare_decision_draft,
    get_decision_stats,
    serialize_decision,
)

router = APIRouter()


@router.get("/stats", response_model=Dict[str, Any])
async def get_stats_endpoint(
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Returns aggregated decision metrics scoped to the user's authorized portfolio."""
    return await get_decision_stats(db, current_user)


@router.get("/intelligence/{project_id}", response_model=Dict[str, Any])
async def get_project_decision_intelligence(
    project_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    Gathers the complete 6-stage Decision Intelligence bundle
    (OBSERVE -> PREDICT -> EXPLAIN -> RECOMMEND -> OPTIMIZE -> DECIDE) for a project.
    """
    role = current_user.get("role", "team_member")
    if role == "project_manager":
        from app.services.project_scoping_service import get_authorized_project_ids
        authorized_pids = await get_authorized_project_ids(db, current_user)
        if project_id not in authorized_pids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: You do not manage this project")

    try:
        return await gather_decision_intelligence(project_id, db)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to gather intelligence: {str(e)}")


@router.get("/draft/{project_id}", response_model=Dict[str, Any])
async def draft_decision_endpoint(
    project_id: str,
    source_type: str = Query("manual"),
    source_id: Optional[str] = Query(None),
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    Pre-fills a rich Decision draft from live project intelligence, recommendations,
    or resource optimization findings, avoiding manual data re-entry.
    """
    role = current_user.get("role", "team_member")
    if role == "project_manager":
        from app.services.project_scoping_service import get_authorized_project_ids
        authorized_pids = await get_authorized_project_ids(db, current_user)
        if project_id not in authorized_pids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: You do not manage this project")

    try:
        return await prepare_decision_draft(db, project_id, source_type, source_id, current_user)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/", response_model=List[DecisionResponse])
async def list_decisions(
    project_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    decision_type: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    Lists historical and pending decisions within the user's authorized portfolio scope.
    """
    try:
        return await get_decisions(
            db=db,
            current_user=current_user,
            project_id=project_id,
            status=status,
            decision_type=decision_type,
            priority=priority,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{decision_id}", response_model=DecisionResponse)
async def get_decision_details(
    decision_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Retrieves full details of a specific Decision record with project authorization checks."""
    try:
        return await get_decision_by_id(db, decision_id, current_user)
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/", response_model=DecisionResponse)
async def create_decision_endpoint(
    data: DecisionCreate,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    Creates a new formal Decision record in db.decisions.
    Enforces server-side project scoping and authorization.
    """
    try:
        doc = await create_decision(db, data, current_user)
        return serialize_decision(doc)
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{decision_id}/approve", response_model=DecisionResponse)
async def approve_decision_endpoint(
    decision_id: str,
    req: DecisionActionRequest,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Formally approves a decision record with human decision rationale."""
    try:
        doc = await record_decision_action(
            db=db,
            decision_id=decision_id,
            action="APPROVED",
            rationale=req.rationale,
            current_user=current_user,
            selected_action=req.selected_action,
            selected_alternative_id=req.selected_alternative_id,
            notes=req.notes,
        )
        return serialize_decision(doc)
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{decision_id}/reject", response_model=DecisionResponse)
async def reject_decision_endpoint(
    decision_id: str,
    req: DecisionActionRequest,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Formally rejects a decision record with human decision rationale."""
    try:
        doc = await record_decision_action(
            db=db,
            decision_id=decision_id,
            action="REJECTED",
            rationale=req.rationale,
            current_user=current_user,
            selected_action=req.selected_action,
            selected_alternative_id=req.selected_alternative_id,
            notes=req.notes,
        )
        return serialize_decision(doc)
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{decision_id}/defer", response_model=DecisionResponse)
async def defer_decision_endpoint(
    decision_id: str,
    req: DecisionActionRequest,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Formally defers a decision record with human decision rationale."""
    try:
        doc = await record_decision_action(
            db=db,
            decision_id=decision_id,
            action="DEFERRED",
            rationale=req.rationale,
            current_user=current_user,
            selected_action=req.selected_action,
            selected_alternative_id=req.selected_alternative_id,
            notes=req.notes,
        )
        return serialize_decision(doc)
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
