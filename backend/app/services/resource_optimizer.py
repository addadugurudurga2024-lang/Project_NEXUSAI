"""
Resource Optimization Service for NexusAI
Constraint-based task reallocation and 3-Level Intelligent Resource Allocation System:
- Level 1: Internal team optimization (reassigning tasks within PM's team/projects)
- Level 2: Project skill and role gap detection
- Level 3: Cross-PM resource discovery and explainable allocation recommendations
- Human decision authority & cross-PM notification workflow
"""

from bson import ObjectId
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from app.services.notification_service import (
    create_notification,
    notify_project_stakeholders,
    notify_cross_pm_resource_requested,
    notify_cross_pm_resource_approved,
    notify_cross_pm_resource_rejected,
)


async def detect_project_skill_gaps(project: dict, tasks: List[dict], team_employees: List[dict]) -> List[Dict[str, Any]]:
    """
    Level 2: Detects roles or skills required by active project tasks where
    no team member has sufficient skill coverage or available capacity (<80% load).
    """
    gaps = []

    # Map team member skills & roles
    team_roles = [e.get("role", "").lower() for e in team_employees]
    available_team_skills = set()
    for e in team_employees:
        # Only count skills of members with available headroom (<100% capacity)
        if float(e.get("assigned_hours", 0)) / max(1.0, float(e.get("weekly_capacity", 40))) < 1.0:
            for s in e.get("skills", []):
                available_team_skills.add(s.lower())

    # Standard high-demand enterprise engineering roles
    target_roles = [
        "ML Engineer", "AI Engineer", "Security Engineer",
        "DevOps Engineer", "Data Engineer", "QA Engineer", "UI/UX Designer"
    ]

    # 1. Role Vacancy Detection: Check if project tasks require a role not present in active team
    for t in tasks:
        req_role = t.get("required_role") or t.get("role_requirement")
        task_title = t.get("title", "Task")
        task_hours = float(t.get("estimated_hours", 0) or 4.0)

        # Infer role requirement from task title or labels if not explicitly set
        if not req_role:
            title_lower = task_title.lower()
            if any(k in title_lower for k in ["ml", "machine learning", "model", "nlp", "tensorflow", "pytorch"]):
                req_role = "ML Engineer"
            elif any(k in title_lower for k in ["security", "auth", "audit", "pentest", "vulnerability"]):
                req_role = "Security Engineer"
            elif any(k in title_lower for k in ["devops", "ci/cd", "kubernetes", "docker", "pipeline"]):
                req_role = "DevOps Engineer"

        if req_role:
            has_role = any(req_role.lower() in tr for tr in team_roles)
            if not has_role:
                gaps.append({
                    "gap_id": f"gap_role_{str(t['_id'])}",
                    "task_id": str(t["_id"]),
                    "task_title": task_title,
                    "task_hours": task_hours,
                    "task_priority": t.get("priority", "medium"),
                    "required_role": req_role,
                    "required_skills": t.get("required_skills", [req_role]),
                    "gap_type": "ROLE_VACANCY",
                    "urgency": "HIGH" if t.get("priority") in ["high", "critical"] else "MEDIUM",
                    "description": f"No {req_role} currently available in team to complete '{task_title}' ({task_hours}h).",
                })

        # 2. Skill Shortage Detection: Check explicit task skill requirements
        req_skills = t.get("required_skills", []) or []
        missing_skills = [s for s in req_skills if s.lower() not in available_team_skills]
        if missing_skills and not any(g["task_id"] == str(t["_id"]) for g in gaps):
            gaps.append({
                "gap_id": f"gap_skill_{str(t['_id'])}",
                "task_id": str(t["_id"]),
                "task_title": task_title,
                "task_hours": task_hours,
                "task_priority": t.get("priority", "medium"),
                "required_role": req_role or "Specialist",
                "required_skills": missing_skills,
                "gap_type": "SKILL_SHORTAGE",
                "urgency": "HIGH" if t.get("priority") in ["high", "critical"] else "MEDIUM",
                "description": f"Skills [{', '.join(missing_skills)}] required by '{task_title}' not sufficiently covered in current team.",
            })

    # Generic check for ML / Security gap if project name implies specialized domain
    proj_name_lower = project.get("name", "").lower()
    if any(k in proj_name_lower for k in ["ai ", "ml", "medical imaging", "diagnostic", "telemetry"]) and not any("ml" in r for r in team_roles):
        if not any(g["required_role"] == "ML Engineer" for g in gaps):
            gaps.append({
                "gap_id": f"gap_proj_ml_{str(project['_id'])}",
                "task_id": None,
                "task_title": "Project ML Capability",
                "task_hours": 20.0,
                "task_priority": "high",
                "required_role": "ML Engineer",
                "required_skills": ["Python", "TensorFlow", "NLP", "PyTorch"],
                "gap_type": "ROLE_VACANCY",
                "urgency": "HIGH",
                "description": f"Domain '{project.get('name')}' has active AI/ML requirements but no direct ML Engineer on team.",
            })

    return gaps[:4]  # Return top 4 distinct gaps


async def discover_cross_pm_resources(
    db,
    project_id: str,
    project_name: str,
    project_pm_id: str,
    detected_gaps: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Level 3: Searches organization for suitable candidate resources belonging to
    OTHER Project Managers' direct teams. Generates explainable recommendations.
    Preserves direct team ownership and enforces human approval.
    Exposes ONLY specific candidate suitability details to protect PM privacy.
    """
    if not detected_gaps:
        return []

    # Find candidate employees who belong to OTHER PMs in db.team_memberships
    # or whose user profile / assigned PM is not project_pm_id
    all_memberships = await db.team_memberships.find({
        "status": "active",
        "pm_user_id": {"$ne": project_pm_id},
    }).to_list(500)

    if not all_memberships:
        # Fallback query: all active employees not directly managed by project_pm_id
        emp_raw = await db.employees.find({"status": "active"}).to_list(300)
        cross_candidates_raw = []
        for e in emp_raw:
            eid = str(e["_id"])
            mem = await db.team_memberships.find_one({"employee_id": eid, "status": "active"})
            if mem and str(mem.get("pm_user_id")) != project_pm_id:
                cross_candidates_raw.append((e, mem))
            elif not mem:
                cross_candidates_raw.append((e, None))
    else:
        cross_candidates_raw = []
        for mem in all_memberships:
            eid = mem.get("employee_id")
            emp = None
            if ObjectId.is_valid(eid):
                emp = await db.employees.find_one({"_id": ObjectId(eid)})
            if not emp:
                emp = await db.employees.find_one({"_id": eid})
            if emp:
                cross_candidates_raw.append((emp, mem))

    # Pre-fetch global task workload aggregation across all projects
    candidate_eids = [str(item[0]["_id"]) for item in cross_candidates_raw]
    candidate_objs = [item[0]["_id"] for item in cross_candidates_raw]

    task_agg = await db.tasks.aggregate([
        {"$match": {
            "$or": [
                {"assignee_id": {"$in": candidate_eids + candidate_objs}},
                {"assigned_to": {"$in": candidate_eids + candidate_objs}},
            ],
            "status": {"$nin": ["done"]}
        }},
        {"$group": {
            "_id": "$assignee_id",
            "assigned_hours": {"$sum": {"$ifNull": ["$estimated_hours", 0]}},
        }}
    ]).to_list(len(candidate_eids) + 50)

    load_map = {str(item["_id"]): float(item["assigned_hours"]) for item in task_agg}

    # PM User name cache
    pm_user_ids = list(set(str(item[1]["pm_user_id"]) for item in cross_candidates_raw if item[1]))
    valid_pm_objs = [ObjectId(p) for p in pm_user_ids if ObjectId.is_valid(p)]
    pm_users = await db.users.find({"_id": {"$in": valid_pm_objs + pm_user_ids}}).to_list(100)
    pm_name_map = {str(u["_id"]): u.get("name", "Project Manager") for u in pm_users}

    cross_opportunities = []

    for gap in detected_gaps:
        req_role = gap.get("required_role", "").lower()
        req_skills = set(s.lower() for s in gap.get("required_skills", []))

        best_cand = None
        best_score = -1

        for emp, mem in cross_candidates_raw:
            emp_id = str(emp["_id"])
            assigned_h = load_map.get(emp_id, 0.0)
            cap_h = float(emp.get("weekly_capacity_hours", 40) or 40)
            workload_pct = (assigned_h / cap_h * 100) if cap_h > 0 else 0
            avail_h = max(0.0, cap_h - assigned_h)

            # Exclude overloaded candidates (>80% workload)
            if workload_pct >= 80.0:
                continue

            emp_role = emp.get("role", "").lower()
            emp_spec = (emp.get("specialization") or "").lower()
            emp_skills = set(s.lower() for s in emp.get("skills", []))

            # Role & Specialization match
            role_match = 1.0 if req_role in emp_role or req_role in emp_spec else 0.5

            # Skill match ratio
            shared_skills = req_skills.intersection(emp_skills)
            skill_match_ratio = (len(shared_skills) / max(1, len(req_skills))) if req_skills else 0.8

            # Suitability score
            score = (skill_match_ratio * 45) + (role_match * 35) + ((80 - workload_pct) * 0.2)

            if score > best_score and score >= 35:
                best_score = score
                home_pm_id = str(mem["pm_user_id"]) if mem else ""
                home_pm_name = pm_name_map.get(home_pm_id, "External PM")

                reasons = [
                    f"✓ {round(skill_match_ratio * 100)}% skill match ({', '.join(list(emp_skills)[:3])})",
                    f"✓ {round(workload_pct)}% current load with {round(avail_h, 1)}h available capacity",
                    f"✓ Role fit: {emp.get('role', 'Specialist')}",
                    f"✓ Home PM: {home_pm_name} (Line management ownership preserved)",
                    f"✓ Low burnout risk (<80% capacity utilization)",
                ]

                best_cand = {
                    "opportunity_id": f"opp_{gap['gap_id']}_{emp_id}",
                    "project_id": project_id,
                    "project_name": project_name,
                    "task_id": gap.get("task_id"),
                    "task_title": gap.get("task_title"),
                    "task_hours": gap.get("task_hours", 4.0),
                    "candidate_employee_id": emp_id,
                    "candidate_name": emp.get("name", "Candidate"),
                    "candidate_role": emp.get("role", "Specialist"),
                    "candidate_specialization": emp.get("specialization", ""),
                    "candidate_skills": emp.get("skills", []),
                    "home_pm_user_id": home_pm_id,
                    "home_pm_name": home_pm_name,
                    "current_workload_percent": round(workload_pct, 1),
                    "available_hours": round(avail_h, 1),
                    "relevance_level": "HIGH" if score >= 55 else "MEDIUM",
                    "suitability_score": round(score, 1),
                    "reasons": reasons,
                    "gap_addressed": gap,
                }

        if best_cand:
            cross_opportunities.append(best_cand)

    return cross_opportunities


async def compute_resource_optimization(project_id: str, db, current_user: Optional[dict] = None) -> Dict[str, Any]:
    """
    Computes 3-Level Resource Optimization for a project:
    - Level 1: Internal team task reallocation
    - Level 2: Project skill & role gap detection
    - Level 3: Cross-PM resource discovery & explainable recommendations
    """
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id)})
    except Exception:
        project = None

    if not project:
        return {
            "project_id": project_id,
            "employee_workload_summary": [],
            "overloaded_employees": [],
            "available_employees": [],
            "reallocation_suggestions": [],
            "project_skill_gaps": [],
            "cross_pm_opportunities": [],
            "pending_cross_pm_requests": [],
            "summary": {
                "total_employees": 0,
                "overloaded_count": 0,
                "available_count": 0,
                "avg_workload_percent": 0,
                "suggestions_count": 0,
                "gaps_count": 0,
                "cross_pm_opportunities_count": 0,
            },
            "message": "Project not found",
            "computed_at": datetime.utcnow().isoformat(),
        }

    project_name = project.get("name", "Project")
    project_pm_id = str(project.get("manager_id") or project.get("project_manager_id") or project.get("created_by") or "")

    # Fetch Project Manager details
    pm_user = None
    if ObjectId.is_valid(project_pm_id):
        pm_user = await db.users.find_one({"_id": ObjectId(project_pm_id)})
    if not pm_user and project_pm_id:
        pm_user = await db.users.find_one({"_id": project_pm_id})
    project_pm_name = pm_user.get("name", "Project Manager") if pm_user else "Project Manager"
    project_pm_specialization = pm_user.get("specialization", "") if pm_user else ""

    # 1. Fetch active tasks for this project
    valid_pid_objs = [ObjectId(project_id)] if ObjectId.is_valid(project_id) else []
    tasks = await db.tasks.find({
        "project_id": {"$in": [project_id] + valid_pid_objs},
        "status": {"$nin": ["done"]},
    }).to_list(500)

    # 2. Fetch project team employees (scoped strictly to project team members & task assignees)
    project_team_eids = set(str(x) for x in project.get("team_member_ids", project.get("team_ids", [])))
    for t in tasks:
        aid = str(t.get("assignee_id", "") or t.get("assigned_to", ""))
        if aid:
            project_team_eids.add(aid)

    team_obj_ids = [ObjectId(x) for x in project_team_eids if ObjectId.is_valid(x)]
    team_str_ids = list(project_team_eids)

    if team_obj_ids or team_str_ids:
        employees_raw = await db.employees.find({
            "_id": {"$in": team_obj_ids + team_str_ids}
        }).to_list(100)
    else:
        employees_raw = []

    emp_ids = [str(e["_id"]) for e in employees_raw]
    emp_objs = [e["_id"] for e in employees_raw]

    # Global task load aggregation across all projects for team members
    task_load_agg = await db.tasks.aggregate([
        {"$match": {
            "$or": [
                {"assignee_id": {"$in": emp_ids + emp_objs}},
                {"assigned_to": {"$in": emp_ids + emp_objs}},
            ],
            "status": {"$nin": ["done"]}
        }},
        {"$group": {
            "_id": "$assignee_id",
            "assigned_hours": {"$sum": {"$ifNull": ["$estimated_hours", 0]}},
        }}
    ]).to_list(len(emp_ids) + 50)
    emp_hours_map = {str(item["_id"]): float(item["assigned_hours"]) for item in task_load_agg}

    # Burnout predictions
    burnout_preds = await db.employee_risk_predictions.find({
        "employee_id": {"$in": emp_ids}
    }).to_list(len(emp_ids) + 50)
    burnout_map = {str(b.get("employee_id")): b for b in burnout_preds}

    # Calculate workload for project team members
    employee_map = {}
    project_tasks_by_emp = {}
    for t in tasks:
        aid = str(t.get("assignee_id", "") or t.get("assigned_to", ""))
        project_tasks_by_emp.setdefault(aid, []).append(t)

    for emp in employees_raw:
        emp_id = str(emp["_id"])
        assigned_hours = emp_hours_map.get(emp_id, 0.0)
        capacity = float(emp.get("weekly_capacity_hours", 40) or 40)
        workload_ratio = (assigned_hours / capacity * 100) if capacity > 0 else 0
        available_hours = max(0.0, capacity - assigned_hours)

        burnout_pred = burnout_map.get(emp_id)
        burnout_risk = burnout_pred.get("risk_level", "LOW") if burnout_pred else ("HIGH" if workload_ratio > 110 else "LOW")

        emp_proj_tasks = project_tasks_by_emp.get(emp_id, [])

        employee_map[emp_id] = {
            "employee_id": emp_id,
            "id": emp_id,
            "name": emp.get("name", "Employee"),
            "email": emp.get("email", ""),
            "role": emp.get("role", "Engineer"),
            "specialization": emp.get("specialization", "General"),
            "skills": emp.get("skills", []),
            "weekly_capacity": capacity,
            "assigned_hours": round(assigned_hours, 1),
            "workload_ratio": round(workload_ratio, 1),
            "available_hours": round(available_hours, 1),
            "burnout_risk": burnout_risk,
            "is_overloaded": workload_ratio > 100,
            "is_available": workload_ratio < 80,
            "active_tasks": [
                {
                    "id": str(t["_id"]),
                    "title": t.get("title", "Task"),
                    "estimated_hours": float(t.get("estimated_hours", 0) or 0),
                    "priority": t.get("priority", "medium"),
                    "project_id": str(t.get("project_id")),
                }
                for t in emp_proj_tasks
            ]
        }

    overloaded = [e for e in employee_map.values() if e["is_overloaded"]]
    available = [e for e in employee_map.values() if e["is_available"]]

    overloaded.sort(key=lambda x: x["workload_ratio"], reverse=True)
    available.sort(key=lambda x: x["workload_ratio"])

    # Level 1: Generate internal task reallocation suggestions
    reallocation_suggestions = []
    persisted_allocations = []

    for over_emp in overloaded:
        assignable_tasks = [
            t for t in tasks
            if (str(t.get("assignee_id", "")) == over_emp["employee_id"] or str(t.get("assigned_to", "")) == over_emp["employee_id"])
            and t.get("priority") not in ["critical"]
        ]
        if not assignable_tasks:
            assignable_tasks = [
                t for t in tasks
                if str(t.get("assignee_id", "")) == over_emp["employee_id"] or str(t.get("assigned_to", "")) == over_emp["employee_id"]
            ]

        assignable_tasks.sort(key=lambda t: float(t.get("estimated_hours", 0) or 0), reverse=True)

        for task in assignable_tasks:
            task_id_str = str(task["_id"])
            task_title = task.get("title", "Task")
            task_hours = float(task.get("estimated_hours", 0) or 4.0)
            task_labels = task.get("labels", []) or []

            best_candidate = None
            best_score = -1

            for avail_emp in available:
                if avail_emp["employee_id"] == over_emp["employee_id"]:
                    continue

                new_avail_hours = avail_emp["assigned_hours"] + task_hours
                new_avail_ratio = (new_avail_hours / avail_emp["weekly_capacity"] * 100)
                if new_avail_ratio > 95:
                    continue

                avail_skills = set(s.lower() for s in avail_emp["skills"])
                over_skills = set(s.lower() for s in over_emp["skills"])
                label_skills = set(s.lower() for s in task_labels)

                skill_overlap = len(avail_skills & label_skills) if label_skills else len(avail_skills & over_skills)
                spec_match = 2 if (
                    avail_emp.get("specialization") and over_emp.get("specialization") and
                    avail_emp["specialization"].lower() == over_emp["specialization"].lower()
                ) else 0

                score = (skill_overlap * 3) + spec_match + ((80 - avail_emp["workload_ratio"]) / 10)

                if score > best_score:
                    best_score = score
                    best_candidate = avail_emp

            if best_candidate:
                current_from_hours = over_emp["assigned_hours"]
                new_from_hours = max(0.0, current_from_hours - task_hours)
                new_from_ratio = (new_from_hours / over_emp["weekly_capacity"] * 100)

                current_to_hours = best_candidate["assigned_hours"]
                new_to_hours = current_to_hours + task_hours
                new_to_ratio = (new_to_hours / best_candidate["weekly_capacity"] * 100)

                reason_text = (
                    f"NexusAI recommends moving this task from {over_emp['name']} to {best_candidate['name']} because "
                    f"{over_emp['name']} is significantly overloaded ({over_emp['workload_ratio']:.0f}%) while "
                    f"{best_candidate['name']} has available capacity ({best_candidate['available_hours']:.1f}h) and the required skill match."
                )

                impact_text = (
                    f"Reduces {over_emp['name']}'s workload from {over_emp['workload_ratio']:.0f}% ({current_from_hours:.1f}h) to {new_from_ratio:.0f}% ({new_from_hours:.1f}h). "
                    f"Optimizes {best_candidate['name']}'s capacity from {best_candidate['workload_ratio']:.0f}% to {new_to_ratio:.0f}% without altering line-management team ownership."
                )

                why_checklist = [
                    f"✓ Required skill match ({best_candidate.get('specialization', 'Engineering')})",
                    f"✓ Available capacity ({best_candidate['available_hours']:.1f}h available bandwidth)",
                    f"✓ Reduces overloaded engineer workload ({over_emp['name']} from {over_emp['workload_ratio']:.0f}% to {new_from_ratio:.0f}%)",
                    f"✓ Keeps work inside current PM team ({project_pm_name})",
                    "✓ No line-management ownership change (Direct PM ownership preserved)",
                ]

                suggestion_id = str(ObjectId())

                alloc_doc = {
                    "_id": ObjectId(suggestion_id),
                    "projectId": project_id,
                    "taskId": task_id_str,
                    "employeeId": best_candidate["employee_id"],
                    "fromEmployeeId": over_emp["employee_id"],
                    "currentAllocationHours": current_from_hours,
                    "recommendedAllocationHours": new_from_hours,
                    "allocationChange": -task_hours,
                    "reason": reason_text,
                    "expectedImpact": impact_text,
                    "why_checklist": why_checklist,
                    "status": "suggested",
                    "createdAt": datetime.utcnow(),
                    "project_id": project_id,
                    "project_name": project_name,
                    "project_pm_id": project_pm_id,
                    "project_pm_name": project_pm_name,
                    "project_pm_specialization": project_pm_specialization,
                    "task_id": task_id_str,
                    "task_title": task_title,
                    "task_hours": task_hours,
                    "task_priority": task.get("priority", "medium"),
                    "task_skills": task_labels or [best_candidate["specialization"]],
                    "employee_id": best_candidate["employee_id"],
                    "employee_name": best_candidate["name"],
                    "from_employee_id": over_emp["employee_id"],
                    "from_employee_name": over_emp["name"],
                    "to_employee": {
                        "id": best_candidate["employee_id"],
                        "name": best_candidate["name"],
                        "role": best_candidate["role"],
                        "specialization": best_candidate["specialization"],
                        "current_workload": best_candidate["workload_ratio"],
                        "projected_workload": round(new_to_ratio, 1),
                        "current_hours": current_to_hours,
                        "projected_hours": round(new_to_hours, 1),
                        "weekly_capacity": best_candidate["weekly_capacity"],
                    },
                    "from_employee": {
                        "id": over_emp["employee_id"],
                        "name": over_emp["name"],
                        "role": over_emp["role"],
                        "specialization": over_emp["specialization"],
                        "current_workload": over_emp["workload_ratio"],
                        "projected_workload": round(new_from_ratio, 1),
                        "current_hours": current_from_hours,
                        "projected_hours": round(new_from_hours, 1),
                        "weekly_capacity": over_emp["weekly_capacity"],
                    },
                    "skill_match": best_score >= 2,
                }

                persisted_allocations.append(alloc_doc)
                suggestion_item = dict(alloc_doc)
                suggestion_item["id"] = suggestion_id
                suggestion_item["_id"] = suggestion_id
                reallocation_suggestions.append(suggestion_item)

                over_emp["assigned_hours"] = new_from_hours
                over_emp["workload_ratio"] = new_from_ratio
                best_candidate["assigned_hours"] = new_to_hours
                best_candidate["workload_ratio"] = new_to_ratio
                best_candidate["available_hours"] = max(0.0, best_candidate["weekly_capacity"] - new_to_hours)

                if len(reallocation_suggestions) >= 5:
                    break

    await db.resource_allocations.delete_many({
        "$or": [{"projectId": project_id}, {"project_id": project_id}],
        "status": "suggested",
    })

    if persisted_allocations:
        await db.resource_allocations.insert_many(persisted_allocations)

    # Level 2: Detect Project Skill & Role Gaps
    project_skill_gaps = await detect_project_skill_gaps(project, tasks, list(employee_map.values()))

    # Level 3: Discover Cross-PM Resource Opportunities
    cross_pm_opportunities = await discover_cross_pm_resources(
        db=db,
        project_id=project_id,
        project_name=project_name,
        project_pm_id=project_pm_id,
        detected_gaps=project_skill_gaps,
    )

    # Fetch pending cross-PM allocation requests for this project
    pending_cross_pm_reqs = await db.cross_pm_allocations.find({
        "project_id": project_id,
        "status": "pending_approval",
    }).to_list(100)

    serialized_pending_reqs = []
    for pr in pending_cross_pm_reqs:
        pr_item = dict(pr)
        pr_item["id"] = str(pr["_id"])
        pr_item["_id"] = str(pr["_id"])
        serialized_pending_reqs.append(pr_item)

    total_employees = len(employee_map)
    overloaded_count = len([e for e in employee_map.values() if e["is_overloaded"]])
    available_count = len([e for e in employee_map.values() if e["is_available"]])
    avg_workload = sum(e["workload_ratio"] for e in employee_map.values()) / max(1, total_employees)

    return {
        "project_id": project_id,
        "project_name": project_name,
        "project_pm_id": project_pm_id,
        "project_pm_name": project_pm_name,
        "project_pm_specialization": project_pm_specialization,
        "employee_workload_summary": list(employee_map.values()),
        "overloaded_employees": overloaded,
        "available_employees": available,
        "reallocation_suggestions": reallocation_suggestions,
        "project_skill_gaps": project_skill_gaps,
        "cross_pm_opportunities": cross_pm_opportunities,
        "pending_cross_pm_requests": serialized_pending_reqs,
        "summary": {
            "total_employees": total_employees,
            "overloaded_count": overloaded_count,
            "available_count": available_count,
            "avg_workload_percent": round(avg_workload, 1),
            "suggestions_count": len(reallocation_suggestions),
            "gaps_count": len(project_skill_gaps),
            "cross_pm_opportunities_count": len(cross_pm_opportunities),
        },
        "has_reallocations": len(reallocation_suggestions) > 0 or len(cross_pm_opportunities) > 0,
        "message": (
            f"Generated {len(reallocation_suggestions)} internal suggestion(s) and discovered {len(cross_pm_opportunities)} cross-PM resource opportunity(ies)."
        ),
        "computed_at": datetime.utcnow().isoformat(),
    }


async def apply_resource_reallocation(allocation_id: str, db, applied_by_user_id: Optional[str] = None) -> Dict[str, Any]:
    """Applies an approved internal task reallocation."""
    try:
        alloc = await db.resource_allocations.find_one({"_id": ObjectId(allocation_id)})
    except Exception:
        alloc = None

    if not alloc:
        raise ValueError("Resource allocation recommendation not found")

    if alloc.get("status") == "applied":
        return {"message": "Resource allocation has already been applied", "allocation_id": allocation_id}

    task_id = alloc.get("taskId") or alloc.get("task_id")
    recipient_emp_id = alloc.get("employeeId") or alloc.get("employee_id")
    from_emp_id = alloc.get("fromEmployeeId") or alloc.get("from_employee_id")
    project_id = alloc.get("projectId") or alloc.get("project_id")

    recipient_emp = await db.employees.find_one({"_id": ObjectId(recipient_emp_id) if ObjectId.is_valid(recipient_emp_id) else recipient_emp_id})
    if not recipient_emp:
        raise ValueError("Recommendation is stale: Recipient employee no longer exists. Please re-analyze.")
    recipient_name = recipient_emp.get("name", "Team Member")

    task = await db.tasks.find_one({"_id": ObjectId(task_id) if ObjectId.is_valid(task_id) else task_id})
    if not task:
        raise ValueError("Recommendation is stale: Target task no longer exists. Please re-analyze.")

    if task.get("status") == "done":
        raise ValueError("Recommendation is stale: Task has already been completed. Please re-analyze.")

    current_assignee = str(task.get("assignee_id", "") or task.get("assigned_to", ""))
    if from_emp_id and current_assignee and current_assignee not in [str(from_emp_id), str(ObjectId(from_emp_id)) if ObjectId.is_valid(from_emp_id) else ""]:
        raise ValueError("Recommendation is stale: Task is no longer assigned to original team member. Please re-analyze.")

    task_title = task.get("title", "Task")

    await db.tasks.update_one(
        {"_id": task["_id"]},
        {
            "$set": {
                "assignee_id": recipient_emp_id,
                "assignee_name": recipient_name,
                "updated_at": datetime.utcnow(),
            }
        }
    )

    await db.resource_allocations.update_one(
        {"_id": alloc["_id"]},
        {
            "$set": {
                "status": "applied",
                "applied_at": datetime.utcnow(),
                "applied_by": applied_by_user_id,
            }
        }
    )

    if recipient_emp.get("user_id"):
        await create_notification(
            db=db,
            user_id=recipient_emp["user_id"],
            notification_type="task_reassigned_to_you",
            title=f"New Task Assigned: {task_title}",
            message=f"You have been assigned '{task_title}' to help rebalance team workload.",
            related_project_id=project_id,
            severity="medium",
        )

    return {
        "success": True,
        "message": f"Successfully reassigned '{task_title}' to {recipient_name}",
        "allocation_id": allocation_id,
        "task_id": str(task["_id"]),
        "new_assignee_id": recipient_emp_id,
        "new_assignee_name": recipient_name,
        "status": "applied",
    }


async def reject_resource_reallocation(allocation_id: str, db, user_id: Optional[str] = None, reason: Optional[str] = None) -> Dict[str, Any]:
    """Dismisses or rejects an internal resource reallocation suggestion."""
    try:
        alloc = await db.resource_allocations.find_one({"_id": ObjectId(allocation_id)})
    except Exception:
        alloc = None

    if not alloc:
        raise ValueError("Resource allocation recommendation not found")

    await db.resource_allocations.update_one(
        {"_id": alloc["_id"]},
        {
            "$set": {
                "status": "rejected",
                "rejected_at": datetime.utcnow(),
                "rejected_by": user_id,
                "rejection_reason": reason or "Dismissed by Project Manager",
            }
        }
    )

    return {
        "success": True,
        "message": "Resource reallocation proposal dismissed.",
        "allocation_id": allocation_id,
        "status": "rejected",
    }


async def request_cross_pm_resource(
    db,
    requesting_user: dict,
    project_id: str,
    candidate_emp_id: str,
    task_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Submits a cross-PM resource allocation request.
    Does NOT automatically assign or alter direct PM line management ownership.
    Notifies candidate's Home PM for decision approval.
    """
    project = await db.projects.find_one({"_id": ObjectId(project_id) if ObjectId.is_valid(project_id) else project_id})
    if not project:
        raise ValueError("Project not found")

    project_name = project.get("name", "Project")
    requesting_pm_id = str(requesting_user["_id"])
    requesting_pm_name = requesting_user.get("name", "Project Manager")

    emp = await db.employees.find_one({"_id": ObjectId(candidate_emp_id) if ObjectId.is_valid(candidate_emp_id) else candidate_emp_id})
    if not emp:
        raise ValueError("Candidate employee not found")

    candidate_name = emp.get("name", "Candidate")
    candidate_role = emp.get("role", "Specialist")

    # Find Home PM from team_memberships
    mem = await db.team_memberships.find_one({"employee_id": str(emp["_id"]), "status": "active"})
    home_pm_id = str(mem["pm_user_id"]) if mem else ""

    if not home_pm_id:
        # Default to another PM if not explicitly in team_memberships
        pms = await db.users.find({"role": "project_manager", "_id": {"$ne": ObjectId(requesting_pm_id) if ObjectId.is_valid(requesting_pm_id) else requesting_pm_id}}).to_list(1)
        if pms:
            home_pm_id = str(pms[0]["_id"])

    task_title = None
    if task_id:
        t = await db.tasks.find_one({"_id": ObjectId(task_id) if ObjectId.is_valid(task_id) else task_id})
        if t:
            task_title = t.get("title")

    # Check for existing pending request
    existing = await db.cross_pm_allocations.find_one({
        "project_id": str(project_id),
        "candidate_employee_id": str(emp["_id"]),
        "status": "pending_approval",
    })
    if existing:
        return {
            "id": str(existing["_id"]),
            "status": "pending_approval",
            "message": "A cross-PM resource request is already pending approval.",
        }

    doc = {
        "project_id": str(project_id),
        "project_name": project_name,
        "requesting_pm_user_id": requesting_pm_id,
        "requesting_pm_name": requesting_pm_name,
        "home_pm_user_id": home_pm_id,
        "candidate_employee_id": str(emp["_id"]),
        "candidate_name": candidate_name,
        "candidate_role": candidate_role,
        "task_id": str(task_id) if task_id else None,
        "task_title": task_title,
        "status": "pending_approval",
        "requested_at": datetime.now(timezone.utc),
    }

    res = await db.cross_pm_allocations.insert_one(doc)
    doc["_id"] = res.inserted_id
    doc["id"] = str(res.inserted_id)

    # Notify Home PM
    if home_pm_id:
        await notify_cross_pm_resource_requested(
            db=db,
            home_pm_user_id=home_pm_id,
            requesting_pm_name=requesting_pm_name,
            project_name=project_name,
            candidate_name=candidate_name,
            candidate_role=candidate_role,
            task_title=task_title,
        )

    return doc


async def approve_cross_pm_resource(
    db,
    request_id: str,
    reviewer_user: dict,
) -> Dict[str, Any]:
    """
    Home PM or Admin approves cross-PM resource project allocation.
    Reassigns task / adds employee to project.
    CRITICAL: Preserves direct PM team ownership (team_memberships remain unchanged).
    """
    try:
        req = await db.cross_pm_allocations.find_one({"_id": ObjectId(request_id)})
    except Exception:
        req = await db.cross_pm_allocations.find_one({"_id": request_id})

    if not req:
        raise ValueError("Cross-PM allocation request not found")

    home_pm_id = str(req.get("home_pm_user_id", ""))
    reviewer_role = reviewer_user.get("role", "team_member")
    reviewer_uid = str(reviewer_user["_id"])

    # Authorization check: Home PM or Admin
    if reviewer_role != "admin" and reviewer_uid != home_pm_id:
        raise PermissionError("Unauthorized: Only the candidate's Home Project Manager or Administrator can approve this request.")

    now_utc = datetime.now(timezone.utc)
    updated = await db.cross_pm_allocations.find_one_and_update(
        {"_id": req["_id"], "status": "pending_approval"},
        {
            "$set": {
                "status": "approved",
                "reviewed_by": reviewer_uid,
                "reviewed_at": now_utc,
            }
        },
        return_document=True,
    )

    if not updated:
        return await db.cross_pm_allocations.find_one({"_id": req["_id"]})

    # Perform controlled project assignment
    cand_emp_id = updated["candidate_employee_id"]
    proj_id = updated["project_id"]
    task_id = updated.get("task_id")

    # 1. Add employee to project's team_member_ids
    if ObjectId.is_valid(proj_id):
        await db.projects.update_one({"_id": ObjectId(proj_id)}, {"$addToSet": {"team_member_ids": cand_emp_id}})
    await db.projects.update_one({"_id": proj_id}, {"$addToSet": {"team_member_ids": cand_emp_id}})

    # 2. Add project to employee's assigned_project_ids
    if ObjectId.is_valid(cand_emp_id):
        await db.employees.update_one({"_id": ObjectId(cand_emp_id)}, {"$addToSet": {"assigned_project_ids": proj_id}})
    await db.employees.update_one({"_id": cand_emp_id}, {"$addToSet": {"assigned_project_ids": proj_id}})

    # 3. If task_id specified, reassign task
    if task_id:
        emp = await db.employees.find_one({"_id": ObjectId(cand_emp_id) if ObjectId.is_valid(cand_emp_id) else cand_emp_id})
        c_name = emp.get("name", "Team Member") if emp else "Team Member"
        await db.tasks.update_one(
            {"$or": [{"_id": ObjectId(task_id) if ObjectId.is_valid(task_id) else None}, {"_id": task_id}]},
            {"$set": {"assignee_id": cand_emp_id, "assignee_name": c_name, "updated_at": now_utc}}
        )

    # Send notification to Requesting PM
    await notify_cross_pm_resource_approved(
        db=db,
        requesting_pm_user_id=updated["requesting_pm_user_id"],
        candidate_name=updated.get("candidate_name", "Candidate"),
        project_name=updated.get("project_name", "Project"),
        approver_name=reviewer_user.get("name", "Home PM"),
    )

    return updated


async def reject_cross_pm_resource(
    db,
    request_id: str,
    reviewer_user: dict,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Home PM or Admin rejects cross-PM resource allocation request.
    """
    try:
        req = await db.cross_pm_allocations.find_one({"_id": ObjectId(request_id)})
    except Exception:
        req = await db.cross_pm_allocations.find_one({"_id": request_id})

    if not req:
        raise ValueError("Cross-PM allocation request not found")

    home_pm_id = str(req.get("home_pm_user_id", ""))
    reviewer_role = reviewer_user.get("role", "team_member")
    reviewer_uid = str(reviewer_user["_id"])

    if reviewer_role != "admin" and reviewer_uid != home_pm_id:
        raise PermissionError("Unauthorized: Only the candidate's Home Project Manager or Administrator can reject this request.")

    now_utc = datetime.now(timezone.utc)
    updated = await db.cross_pm_allocations.find_one_and_update(
        {"_id": req["_id"]},
        {
            "$set": {
                "status": "rejected",
                "reviewed_by": reviewer_uid,
                "reviewed_at": now_utc,
                "rejection_reason": reason or "Rejected by Home PM",
            }
        },
        return_document=True,
    )

    await notify_cross_pm_resource_rejected(
        db=db,
        requesting_pm_user_id=updated["requesting_pm_user_id"],
        candidate_name=updated.get("candidate_name", "Candidate"),
        project_name=updated.get("project_name", "Project"),
        approver_name=reviewer_user.get("name", "Home PM"),
    )

    return updated
