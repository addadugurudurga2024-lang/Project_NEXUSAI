from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, Optional

from app.core.deps import get_current_user, require_manager_or_admin
from app.db.database import get_database
from app.services.project_scoping_service import get_authorized_project_ids
from app.models.simulation import (
    SimulationRequest,
    SimulationResult,
    SimulationProjectOptions,
)
from app.services.simulation_service import (
    run_what_if_simulation,
    get_simulation_options,
)

router = APIRouter()


@router.post("/run", response_model=SimulationResult)
async def run_simulation_endpoint(
    request: SimulationRequest,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    Runs an in-memory What-If scenario analysis on a read-only snapshot.
    Enforces server-side PM project scoping and RBAC.
    Guarantees zero mutation to live MongoDB operational data.
    """
    role = current_user.get("role", "team_member")
    if role != "admin":
        auth_pids = await get_authorized_project_ids(db, current_user)
        if request.project_id not in auth_pids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: You do not have permission to simulate scenarios for this project",
            )

    try:
        return await run_what_if_simulation(request, db, current_user)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation failed: {str(e)}",
        )


@router.get("/options/{project_id}", response_model=SimulationProjectOptions)
async def get_simulation_options_endpoint(
    project_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    Fetches available tasks, team members, skill gaps, and candidates for scenario configuration.
    Enforces server-side PM project scoping.
    """
    role = current_user.get("role", "team_member")
    if role != "admin":
        auth_pids = await get_authorized_project_ids(db, current_user)
        if project_id not in auth_pids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: You do not have permission to access simulation options for this project",
            )

    try:
        return await get_simulation_options(project_id, db)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch simulation options: {str(e)}",
        )
