from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional, Dict, Any
# pyrefly: ignore [missing-import]
from bson import ObjectId
from app.core.deps import get_current_user, require_manager_or_admin
from app.db.database import get_database
from app.services.team_capacity_service import (
    init_team_memberships_if_needed,
    get_pm_capacity_details,
    get_all_pms_capacity_summary,
    create_member_request,
    analyze_candidate_pm_matches,
    approve_member_request,
    reject_member_request,
)

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
    if "assigned_at" in res and res["assigned_at"]:
        res["assigned_at"] = res["assigned_at"].isoformat()
    return res


@router.get("/pms", response_model=List[Dict[str, Any]])
async def list_pms_capacity(
    db=Depends(get_database),
):
    """Returns capacity summary list for all Project Managers in the organization."""
    await init_team_memberships_if_needed(db)
    return await get_all_pms_capacity_summary(db)


@router.get("/my-capacity", response_model=Dict[str, Any])
async def get_my_capacity(
    pm_user_id: Optional[str] = None,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Returns detailed capacity metrics, role breakdown, and capability gaps for a PM."""
    await init_team_memberships_if_needed(db)

    target_pm_id = str(current_user["_id"])
    if pm_user_id and current_user.get("role") == "admin":
        target_pm_id = pm_user_id

    try:
        return await get_pm_capacity_details(db, target_pm_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/pending-requests", response_model=List[Dict[str, Any]])
async def list_pending_requests(
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """Lists pending team membership candidate requests awaiting PM decision."""
    await init_team_memberships_if_needed(db)

    role = current_user.get("role")
    uid = str(current_user["_id"])

    query: Dict[str, Any] = {"status": "pending"}
    if role != "admin":
        query["pm_user_id"] = uid

    requests = await db.team_memberships.find(query).sort("requested_at", -1).to_list(200)
    results = []

    for req in requests:
        s_req = serialize_doc(req)
        # Hydrate candidate employee details
        eid = req.get("employee_id")
        emp = None
        if ObjectId.is_valid(eid):
            emp = await db.employees.find_one({"_id": ObjectId(eid)})
        if not emp:
            emp = await db.employees.find_one({"_id": eid})

        if emp:
            s_req["candidate_name"] = emp.get("name")
            s_req["candidate_email"] = emp.get("email")
            s_req["candidate_role"] = emp.get("role")
            s_req["candidate_skills"] = emp.get("skills", [])
            s_req["candidate_specialization"] = emp.get("specialization")
            s_req["candidate_experience_years"] = emp.get("experience_years", 0)

        # Hydrate PM name
        pm = await db.users.find_one({"_id": ObjectId(req["pm_user_id"]) if ObjectId.is_valid(req["pm_user_id"]) else req["pm_user_id"]})
        if pm:
            s_req["pm_name"] = pm.get("name")

        results.append(s_req)

    return results


@router.post("/request/{pm_user_id}", response_model=Dict[str, Any])
async def submit_pm_request(
    pm_user_id: str,
    employee_id: Optional[str] = None,
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Submits a candidate request to join a Project Manager's team."""
    await init_team_memberships_if_needed(db)

    uid = str(current_user["_id"])
    target_emp_id = employee_id

    # If employee_id is not specified, resolve from current user
    if not target_emp_id:
        emp = await db.employees.find_one({"$or": [{"user_id": uid}, {"email": current_user.get("email")}]})
        if not emp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No employee profile associated with logged in user",
            )
        target_emp_id = str(emp["_id"])

    try:
        req_doc = await create_member_request(
            db=db,
            pm_user_id=pm_user_id,
            candidate_user_id=uid,
            employee_id=target_emp_id,
        )
        return serialize_doc(req_doc)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/analyze/{employee_id}", response_model=Dict[str, Any])
async def analyze_matches(
    employee_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    Evaluates candidate role, skills, team gaps, PM capacities, and project demand
    to recommend suitable PM placements.
    """
    await init_team_memberships_if_needed(db)
    try:
        return await analyze_candidate_pm_matches(db, employee_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/requests/{request_id}/approve", response_model=Dict[str, Any])
async def approve_request_endpoint(
    request_id: str,
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    PM/Admin approves candidate request.
    Server-side enforces PM active capacity <= 18.
    Enforces RBAC PM scoping.
    """
    await init_team_memberships_if_needed(db)
    try:
        res = await approve_member_request(db, request_id, current_user)
        return serialize_doc(res)
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/requests/{request_id}/reject", response_model=Dict[str, Any])
async def reject_request_endpoint(
    request_id: str,
    reason: Optional[str] = Query(None),
    current_user=Depends(require_manager_or_admin),
    db=Depends(get_database),
):
    """
    PM/Admin rejects candidate request.
    Enforces RBAC PM scoping.
    """
    await init_team_memberships_if_needed(db)
    try:
        res = await reject_member_request(db, request_id, current_user, reason)
        return serialize_doc(res)
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/my-status", response_model=Dict[str, Any])
async def get_my_membership_status(
    current_user=Depends(get_current_user),
    db=Depends(get_database),
):
    """Returns logged-in team member's authoritative PM team membership status and request history."""
    await init_team_memberships_if_needed(db)
    uid = str(current_user["_id"])
    emp = await db.employees.find_one({"$or": [{"user_id": uid}, {"email": current_user.get("email")}]})
    if not emp:
        return {
            "has_employee_profile": False,
            "status": "none",
            "pm_name": None,
            "pm_user_id": None,
            "pm_email": None,
            "pm_specialization": None,
            "rejection_reason": None,
            "requested_at": None,
            "reviewed_at": None,
            "assigned_at": None,
            "message": "No employee profile associated with logged in user account.",
            "active_membership": None,
            "latest_request": None,
            "all_requests": [],
            "memberships": [],
        }

    emp_id = str(emp["_id"])
    memberships = await db.team_memberships.find({"employee_id": emp_id}).sort("requested_at", -1).to_list(50)

    serialized = []
    for m in memberships:
        sm = serialize_doc(m)
        pm = await db.users.find_one({"_id": ObjectId(m["pm_user_id"]) if ObjectId.is_valid(m["pm_user_id"]) else m["pm_user_id"]})
        if pm:
            sm["pm_name"] = pm.get("name")
            sm["pm_email"] = pm.get("email")
            sm["pm_specialization"] = pm.get("specialization")
        serialized.append(sm)

    active_membership = next((sm for sm in serialized if sm.get("status") == "active"), None)
    pending_membership = next((sm for sm in serialized if sm.get("status") == "pending"), None)
    rejected_membership = next((sm for sm in serialized if sm.get("status") == "rejected"), None)

    if active_membership:
        status_val = "active"
        pm_name = active_membership.get("pm_name")
        pm_user_id = active_membership.get("pm_user_id")
        pm_email = active_membership.get("pm_email")
        pm_spec = active_membership.get("pm_specialization")
        rejection_reason = None
        requested_at = active_membership.get("requested_at")
        reviewed_at = active_membership.get("reviewed_at")
        assigned_at = active_membership.get("assigned_at")
        message = f"You are an active member of {pm_name or 'the Project Manager'}'s team."
    elif pending_membership:
        status_val = "pending"
        pm_name = pending_membership.get("pm_name")
        pm_user_id = pending_membership.get("pm_user_id")
        pm_email = pending_membership.get("pm_email")
        pm_spec = pending_membership.get("pm_specialization")
        rejection_reason = None
        requested_at = pending_membership.get("requested_at")
        reviewed_at = None
        assigned_at = None
        message = f"Your onboarding request to join {pm_name or 'the Project Manager'}'s team is pending review."
    elif rejected_membership:
        status_val = "rejected"
        pm_name = rejected_membership.get("pm_name")
        pm_user_id = rejected_membership.get("pm_user_id")
        pm_email = rejected_membership.get("pm_email")
        pm_spec = rejected_membership.get("pm_specialization")
        rejection_reason = rejected_membership.get("rejection_reason") or "Rejected by Project Manager"
        requested_at = rejected_membership.get("requested_at")
        reviewed_at = rejected_membership.get("reviewed_at")
        assigned_at = None
        message = f"Your request to join {pm_name or 'the Project Manager'}'s team was not approved."
    else:
        status_val = "none"
        pm_name = None
        pm_user_id = None
        pm_email = None
        pm_spec = None
        rejection_reason = None
        requested_at = None
        reviewed_at = None
        assigned_at = None
        message = "You are not currently assigned to a Project Manager's team."

    return {
        "has_employee_profile": True,
        "employee_id": emp_id,
        "employee_name": emp.get("name"),
        "employee_email": emp.get("email"),
        "employee_role": emp.get("role"),
        "employee_skills": emp.get("skills", []),
        "employee_specialization": emp.get("specialization"),
        "employee_weekly_capacity_hours": emp.get("weekly_capacity_hours", 40.0),
        "status": status_val,
        "pm_name": pm_name,
        "pm_user_id": pm_user_id,
        "pm_email": pm_email,
        "pm_specialization": pm_spec,
        "rejection_reason": rejection_reason,
        "requested_at": requested_at,
        "reviewed_at": reviewed_at,
        "assigned_at": assigned_at,
        "message": message,
        "active_membership": active_membership,
        "latest_request": serialized[0] if serialized else None,
        "all_requests": serialized,
        "memberships": serialized,
    }
