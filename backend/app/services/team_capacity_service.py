from asyncio import Lock
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
# pyrefly: ignore [missing-import]
from bson import ObjectId
from app.core.config import settings
from app.services.notification_service import (
    notify_team_member_requested,
    notify_team_member_assigned,
    notify_team_member_rejected,
)

_pm_approval_locks: Dict[str, Lock] = {}


def _get_pm_lock(pm_user_id: str) -> Lock:
    if pm_user_id not in _pm_approval_locks:
        _pm_approval_locks[pm_user_id] = Lock()
    return _pm_approval_locks[pm_user_id]


def _to_str(val: Any) -> str:
    if isinstance(val, ObjectId):
        return str(val)
    return str(val) if val is not None else ""


async def init_team_memberships_if_needed(db):
    """
    Seeds baseline direct line-management team memberships for existing PMs
    if db.team_memberships has no active records yet.
    Ensures every PM has at most 15-17 active direct team members initially,
    leaving available capacity for new registrations.
    """
    existing_count = await db.team_memberships.count_documents({"status": "active"})
    if existing_count > 0:
        return

    # Find all project managers
    pms = await db.users.find({"role": "project_manager"}).to_list(100)
    for pm in pms:
        pm_id = str(pm["_id"])
        # Find projects managed by this PM
        projs = await db.projects.find({
            "$or": [
                {"manager_id": pm_id},
                {"project_manager_id": pm_id},
                {"created_by": pm_id},
            ]
        }).to_list(100)

        # Gather unique employees assigned to these projects
        emp_ids = set()
        for p in projs:
            for tid in p.get("team_member_ids", p.get("team_ids", [])):
                emp_ids.add(str(tid))

        # Seed up to 15 members so available capacity is at least 3
        seeded = 0
        for eid in list(emp_ids):
            if seeded >= 15:
                break
            # Find employee doc
            emp = None
            if ObjectId.is_valid(eid):
                emp = await db.employees.find_one({"_id": ObjectId(eid)})
            if not emp:
                emp = await db.employees.find_one({"_id": eid})
            if not emp:
                continue

            emp_id_str = str(emp["_id"])
            # Check if employee already assigned to another PM in team_memberships
            existing_mem = await db.team_memberships.find_one({"employee_id": emp_id_str, "status": "active"})
            if existing_mem:
                continue

            doc = {
                "pm_user_id": pm_id,
                "employee_id": emp_id_str,
                "status": "active",
                "role": emp.get("role", "Engineer"),
                "skills": emp.get("skills", []),
                "requested_by": emp.get("user_id") or pm_id,
                "requested_at": datetime.now(timezone.utc),
                "assigned_at": datetime.now(timezone.utc),
                "reviewed_by": pm_id,
                "reviewed_at": datetime.now(timezone.utc),
            }
            await db.team_memberships.insert_one(doc)
            seeded += 1


async def get_pm_active_member_count(db, pm_user_id: str) -> int:
    """Counts active team members directly managed by the given PM user ID."""
    return await db.team_memberships.count_documents({
        "pm_user_id": str(pm_user_id),
        "status": "active",
    })


async def get_pm_capacity_details(db, pm_user_id: str) -> Dict[str, Any]:
    """
    Computes capacity metrics, role breakdown, skill coverage, and capability gaps
    for a specific Project Manager.
    """
    pm_user = await db.users.find_one({"_id": ObjectId(pm_user_id) if ObjectId.is_valid(pm_user_id) else pm_user_id})
    pm_name = pm_user.get("name", "Project Manager") if pm_user else "Project Manager"

    active_memberships = await db.team_memberships.find({
        "pm_user_id": str(pm_user_id),
        "status": "active",
    }).to_list(500)

    active_count = len(active_memberships)
    max_cap = settings.pm_team_capacity
    rem_cap = max(0, max_cap - active_count)
    is_full = active_count >= max_cap

    # Role breakdown & skill coverage
    role_counts: Dict[str, int] = {}
    skill_counts: Dict[str, int] = {}
    employee_details = []

    for mem in active_memberships:
        eid = mem.get("employee_id")
        emp = None
        if ObjectId.is_valid(eid):
            emp = await db.employees.find_one({"_id": ObjectId(eid)})
        if not emp:
            emp = await db.employees.find_one({"_id": eid})

        if emp:
            r = emp.get("role", mem.get("role", "Engineer"))
            s_list = emp.get("skills", mem.get("skills", []))
            name = emp.get("name", "")
            emp_id_str = str(emp["_id"])
        else:
            r = mem.get("role", "Engineer")
            s_list = mem.get("skills", [])
            name = "Team Member"
            emp_id_str = str(eid)

        role_counts[r] = role_counts.get(r, 0) + 1
        for s in s_list:
            skill_counts[s] = skill_counts.get(s, 0) + 1

        employee_details.append({
            "employee_id": emp_id_str,
            "name": name,
            "role": r,
            "skills": s_list,
            "assigned_at": mem.get("assigned_at"),
        })

    # Find project demand & capability gaps across PM's managed projects
    managed_projects = await db.projects.find({
        "$or": [
            {"manager_id": str(pm_user_id)},
            {"project_manager_id": str(pm_user_id)},
            {"created_by": str(pm_user_id)},
        ]
    }).to_list(100)

    p_ids = [str(p["_id"]) for p in managed_projects]
    valid_pids = [ObjectId(p) for p in p_ids if ObjectId.is_valid(p)]

    # Fetch active tasks across PM's projects to see required skills/roles
    active_tasks = await db.tasks.find({
        "project_id": {"$in": p_ids + valid_pids},
        "status": {"$nin": ["done"]},
    }).to_list(500)

    # Check gap in roles/skills
    capability_gaps = []
    standard_roles = [
        "Backend Engineer", "Frontend Engineer", "ML Engineer",
        "Data Engineer", "QA Engineer", "DevOps Engineer", "UI/UX Designer", "Security Engineer"
    ]

    for std_role in standard_roles:
        count = sum(1 for r_name, r_cnt in role_counts.items() if std_role.lower() in r_name.lower())
        if count == 0:
            capability_gaps.append({
                "type": "role",
                "name": std_role,
                "status": "Missing",
                "description": f"No {std_role} currently active on PM team",
            })

    task_skills_needed = set()
    for t in active_tasks:
        req = t.get("required_skills", [])
        if isinstance(req, list):
            task_skills_needed.update(req)

    for req_skill in task_skills_needed:
        if skill_counts.get(req_skill, 0) == 0:
            capability_gaps.append({
                "type": "skill",
                "name": req_skill,
                "status": "Required by Active Tasks",
                "description": f"Skill '{req_skill}' required by project tasks but not present in team",
            })

    return {
        "pm_user_id": str(pm_user_id),
        "pm_name": pm_name,
        "active_members_count": active_count,
        "max_capacity": max_cap,
        "available_capacity": rem_cap,
        "is_full": is_full,
        "role_breakdown": role_counts,
        "skill_coverage": skill_counts,
        "capability_gaps": capability_gaps[:5],
        "active_members": employee_details,
    }


async def get_all_pms_capacity_summary(db) -> List[Dict[str, Any]]:
    """Returns capacity overview for all Project Managers in the organization."""
    pms = await db.users.find({"role": "project_manager"}).to_list(100)
    summaries = []
    for pm in pms:
        pm_id = str(pm["_id"])
        active_count = await get_pm_active_member_count(db, pm_id)
        max_cap = settings.pm_team_capacity
        rem_cap = max(0, max_cap - active_count)

        proj_count = await db.projects.count_documents({
            "$or": [
                {"manager_id": pm_id},
                {"project_manager_id": pm_id},
                {"created_by": pm_id},
            ]
        })

        summaries.append({
            "pm_user_id": pm_id,
            "name": pm.get("name", "Project Manager"),
            "email": pm.get("email"),
            "specialization": pm.get("specialization"),
            "active_members_count": active_count,
            "max_capacity": max_cap,
            "available_capacity": rem_cap,
            "is_full": active_count >= max_cap,
            "managed_projects_count": proj_count,
        })

    return sorted(summaries, key=lambda x: x["name"])


async def create_member_request(
    db,
    pm_user_id: str,
    candidate_user_id: str,
    employee_id: str,
) -> Dict[str, Any]:
    """
    Submits a new candidate PM association request.
    Does NOT automatically make the candidate an active member.
    Triggers notification to the requested PM.
    """
    pm_user = await db.users.find_one({"_id": ObjectId(pm_user_id) if ObjectId.is_valid(pm_user_id) else pm_user_id})
    if not pm_user or pm_user.get("role") != "project_manager":
        raise ValueError("Invalid Project Manager specified")

    emp = None
    if ObjectId.is_valid(employee_id):
        emp = await db.employees.find_one({"_id": ObjectId(employee_id)})
    if not emp:
        emp = await db.employees.find_one({"_id": employee_id})
    if not emp:
        raise ValueError("Employee profile not found")

    emp_id_str = str(emp["_id"])

    existing = await db.team_memberships.find_one({
        "pm_user_id": str(pm_user_id),
        "employee_id": emp_id_str,
        "status": {"$in": ["active", "pending"]},
    })
    if existing:
        if existing.get("status") == "active":
            raise ValueError(f"Candidate is already an active member of {pm_user.get('name')}'s team")
        else:
            return existing

    active_count = await get_pm_active_member_count(db, pm_user_id)

    doc = {
        "pm_user_id": str(pm_user_id),
        "employee_id": emp_id_str,
        "status": "pending",
        "role": emp.get("role", "Engineer"),
        "skills": emp.get("skills", []),
        "requested_by": str(candidate_user_id),
        "requested_at": datetime.now(timezone.utc),
    }

    result = await db.team_memberships.insert_one(doc)
    doc["_id"] = result.inserted_id
    doc["id"] = str(result.inserted_id)

    await notify_team_member_requested(
        db=db,
        pm_user_id=str(pm_user_id),
        candidate_name=emp.get("name", "Candidate"),
        candidate_role=emp.get("role", "Engineer"),
        candidate_skills=emp.get("skills", []),
        active_capacity=active_count,
        max_capacity=settings.pm_team_capacity,
    )

    return doc


async def analyze_candidate_pm_matches(db, employee_id: str) -> Dict[str, Any]:
    """
    Evaluates candidate role, skills, experience, PM active capacities, team gaps,
    and project requirements across the organization to recommend suitable PM matches.
    Does NOT auto-assign.
    """
    emp = None
    if ObjectId.is_valid(employee_id):
        emp = await db.employees.find_one({"_id": ObjectId(employee_id)})
    if not emp:
        emp = await db.employees.find_one({"_id": employee_id})
    if not emp:
        raise ValueError("Employee not found")

    candidate_role = emp.get("role", "").strip()
    candidate_skills = set(emp.get("skills", []))
    candidate_spec = emp.get("specialization", "") or ""

    pms = await db.users.find({"role": "project_manager"}).to_list(100)
    matches = []

    for pm in pms:
        pm_id = str(pm["_id"])
        cap_details = await get_pm_capacity_details(db, pm_id)

        rem_cap = cap_details["available_capacity"]
        active_cnt = cap_details["active_members_count"]
        is_full = cap_details["is_full"]

        reasons = []
        score = 0

        if rem_cap > 0:
            reasons.append(f"✓ {rem_cap} available team slot{'s' if rem_cap > 1 else ''} ({active_cnt}/18 active)")
            score += rem_cap * 10
        else:
            reasons.append("✖ PM team capacity is currently FULL (18/18)")

        pm_roles = cap_details["role_breakdown"]
        role_match_count = sum(cnt for r_name, cnt in pm_roles.items() if candidate_role.lower() in r_name.lower())
        if role_match_count == 0:
            reasons.append(f"✓ Candidate role '{candidate_role}' fills a missing role in team composition")
            score += 25
        else:
            reasons.append(f"• PM team already has {role_match_count} {candidate_role}(s)")
            score += 10

        team_skills = cap_details["skill_coverage"]
        shared_skills = candidate_skills.intersection(set(team_skills.keys()))
        new_skills = candidate_skills.difference(set(team_skills.keys()))

        if new_skills:
            reasons.append(f"✓ Brings {len(new_skills)} new skill(s) to team: {', '.join(list(new_skills)[:3])}")
            score += len(new_skills) * 8

        if shared_skills:
            reasons.append(f"✓ Aligns with existing team core skills: {', '.join(list(shared_skills)[:3])}")
            score += len(shared_skills) * 5

        pm_projs = await db.projects.find({
            "$or": [
                {"manager_id": pm_id},
                {"project_manager_id": pm_id},
                {"created_by": pm_id},
            ]
        }).to_list(100)

        proj_names = [p.get("name") for p in pm_projs]
        if proj_names:
            reasons.append(f"✓ Manages {len(pm_projs)} project(s): {', '.join(proj_names[:2])}")
            score += len(pm_projs) * 5

        rel_level = "High" if score >= 50 else ("Medium" if score >= 25 else "Low")

        matches.append({
            "pm_user_id": pm_id,
            "pm_name": pm.get("name"),
            "pm_email": pm.get("email"),
            "pm_specialization": pm.get("specialization"),
            "active_members_count": active_cnt,
            "available_capacity": rem_cap,
            "is_full": is_full,
            "relevance_level": rel_level,
            "score": score,
            "reasons": reasons,
        })

    sorted_matches = sorted(matches, key=lambda x: x["score"], reverse=True)

    return {
        "candidate": {
            "employee_id": str(emp["_id"]),
            "name": emp.get("name"),
            "role": candidate_role,
            "specialization": candidate_spec,
            "skills": list(candidate_skills),
        },
        "recommendations": sorted_matches,
    }


async def approve_member_request(
    db,
    request_id: str,
    reviewer_user: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Approves candidate request and activates direct PM team membership.
    Strictly enforces SERVER-SIDE capacity cap of 18 active members.
    Prevents unauthorized PMs from approving another PM's candidate.
    """
    try:
        req = await db.team_memberships.find_one({"_id": ObjectId(request_id)})
    except Exception:
        req = await db.team_memberships.find_one({"_id": request_id})

    if not req:
        raise ValueError("Membership request not found")

    pm_user_id = str(req["pm_user_id"])
    reviewer_role = reviewer_user.get("role", "team_member")
    reviewer_uid = str(reviewer_user["_id"])

    if reviewer_role != "admin" and reviewer_uid != pm_user_id:
        raise PermissionError("Unauthorized: Cannot approve candidate for another Project Manager's team")

    # SERVER-SIDE CAPACITY ENFORCEMENT WITH CONCURRENCY LOCK
    async with _get_pm_lock(pm_user_id):
        active_count = await get_pm_active_member_count(db, pm_user_id)
        if active_count >= settings.pm_team_capacity:
            raise ValueError(f"Cannot assign team member: Project Manager has reached maximum active team capacity ({settings.pm_team_capacity} members).")

        now_utc = datetime.now(timezone.utc)
        res = await db.team_memberships.find_one_and_update(
            {
                "_id": req["_id"],
                "status": "pending",
            },
            {
                "$set": {
                    "status": "active",
                    "reviewed_by": reviewer_uid,
                    "reviewed_at": now_utc,
                    "assigned_at": now_utc,
                }
            },
            return_document=True,
        )

        if not res:
            updated_req = await db.team_memberships.find_one({"_id": req["_id"]})
            if updated_req and updated_req.get("status") == "active":
                return updated_req
            raise ValueError("Request status is no longer pending")

    pm_user = await db.users.find_one({"_id": ObjectId(pm_user_id) if ObjectId.is_valid(pm_user_id) else pm_user_id})
    pm_name = pm_user.get("name", "Project Manager") if pm_user else "Project Manager"

    await notify_team_member_assigned(
        db=db,
        member_emp_id=res["employee_id"],
        pm_name=pm_name,
        role_name=res.get("role", "Team Member"),
    )

    return res


async def reject_member_request(
    db,
    request_id: str,
    reviewer_user: Dict[str, Any],
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Rejects candidate PM request.
    Prevents unauthorized PMs from rejecting another PM's candidate.
    """
    try:
        req = await db.team_memberships.find_one({"_id": ObjectId(request_id)})
    except Exception:
        req = await db.team_memberships.find_one({"_id": request_id})

    if not req:
        raise ValueError("Membership request not found")

    pm_user_id = str(req["pm_user_id"])
    reviewer_role = reviewer_user.get("role", "team_member")
    reviewer_uid = str(reviewer_user["_id"])

    if reviewer_role != "admin" and reviewer_uid != pm_user_id:
        raise PermissionError("Unauthorized: Cannot manage requests for another Project Manager's team")

    now_utc = datetime.now(timezone.utc)
    res = await db.team_memberships.find_one_and_update(
        {"_id": req["_id"]},
        {
            "$set": {
                "status": "rejected",
                "reviewed_by": reviewer_uid,
                "reviewed_at": now_utc,
                "rejection_reason": reason or "Rejected by Project Manager",
            }
        },
        return_document=True,
    )

    pm_user = await db.users.find_one({"_id": ObjectId(pm_user_id) if ObjectId.is_valid(pm_user_id) else pm_user_id})
    pm_name = pm_user.get("name", "Project Manager") if pm_user else "Project Manager"

    await notify_team_member_rejected(
        db=db,
        member_emp_id=res["employee_id"],
        pm_name=pm_name,
    )

    return res
