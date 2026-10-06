"""
Decision Intelligence Service for NexusAI
Synthesizes OBSERVE, PREDICT, EXPLAIN, RECOMMEND, OPTIMIZE, DECIDE metrics
using actual MongoDB project-management data and ML inferences.

Provides authoritative Decision Log persistence, RBAC scoping, lifecycle transitions,
and traceable context preservation.
"""
# pyrefly: ignore [missing-import]
from bson import ObjectId
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from app.services.notification_service import create_notification
from app.services.project_scoping_service import get_authorized_project_ids


def serialize_decision(d: dict) -> dict:
    """Serializes MongoDB decision document into clean JSON-serializable dictionary."""
    if not d:
        return {}
    res = dict(d)
    res["id"] = str(d["_id"])
    res["_id"] = str(d["_id"])
    if "created_at" in res and isinstance(res["created_at"], datetime):
        res["created_at"] = res["created_at"].isoformat()
    if "decided_at" in res and isinstance(res["decided_at"], datetime):
        res["decided_at"] = res["decided_at"].isoformat()
    if "audit_trail" in res and isinstance(res["audit_trail"], list):
        for entry in res["audit_trail"]:
            if "timestamp" in entry and isinstance(entry["timestamp"], datetime):
                entry["timestamp"] = entry["timestamp"].isoformat()
    return res


async def gather_decision_intelligence(project_id: str, db) -> Dict[str, Any]:
    """
    Assembles complete Decision Intelligence data bundle for a project.
    """
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id) if ObjectId.is_valid(project_id) else project_id})
    except Exception:
        project = None

    if not project:
        raise ValueError("Project not found")

    project_name = project.get("name", "Unnamed Project")
    budget = float(project.get("budget", 0) or 0)
    current_expenditure = float(project.get("current_expenditure", 0) or 0)
    progress = float(project.get("progress", 0) or 0)
    budget_utilization = (current_expenditure / budget * 100) if budget > 0 else 0

    # 1. OBSERVE — Raw Tasks, Issues, Sprints, Team
    tasks = await db.tasks.find({"project_id": project_id}).to_list(1000)
    total_tasks = len(tasks)
    active_tasks = [t for t in tasks if t.get("status") not in ["done"]]
    completed_tasks = [t for t in tasks if t.get("status") == "done"]
    blocked_tasks = [t for t in tasks if t.get("status") == "blocked"]
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    overdue_tasks = [
        t for t in active_tasks
        if t.get("due_date") and t.get("due_date") < today_str
    ]
    high_priority_tasks = [t for t in active_tasks if t.get("priority") in ["high", "critical"]]
    task_completion_rate = (len(completed_tasks) / total_tasks * 100) if total_tasks > 0 else 0

    issues = await db.issues.find({"project_id": project_id}).to_list(500)
    open_issues = [i for i in issues if i.get("status") == "open"]
    critical_issues = [i for i in issues if i.get("severity") == "critical" and i.get("status") != "resolved"]
    high_issues = [i for i in issues if i.get("severity") == "high" and i.get("status") != "resolved"]
    resolved_issues = [i for i in issues if i.get("status") == "resolved"]

    sprints = await db.sprints.find({"project_id": project_id}).to_list(100)
    completed_sprints = [s for s in sprints if s.get("status") == "completed"]
    avg_velocity = 0.0
    if completed_sprints:
        velocities = [s.get("velocity", 0) for s in completed_sprints if s.get("velocity")]
        if velocities:
            avg_velocity = sum(velocities) / len(velocities)

    # Team members & workload
    team_ids = project.get("team_member_ids", []) or project.get("teamMemberIds", []) or []
    team_members = []
    total_team_capacity = 0.0
    total_team_assigned_hours = 0.0

    for tid in team_ids:
        try:
            emp = await db.employees.find_one({"_id": ObjectId(tid) if ObjectId.is_valid(tid) else tid})
            if emp:
                emp_id_str = str(emp["_id"])
                emp_active_tasks = [t for t in active_tasks if t.get("assignee_id") == emp_id_str]
                assigned_h = sum(float(t.get("estimated_hours", 0) or 0) for t in emp_active_tasks)
                cap_h = float(emp.get("weekly_capacity_hours", 40) or 40)
                ratio = (assigned_h / cap_h * 100) if cap_h > 0 else 0

                total_team_capacity += cap_h
                total_team_assigned_hours += assigned_h

                # Check burnout prediction
                burnout_doc = await db.employee_risk_predictions.find_one({"employee_id": emp_id_str})
                burnout_risk = burnout_doc.get("risk_level", "LOW") if burnout_doc else ("HIGH" if ratio > 110 else "MEDIUM" if ratio > 85 else "LOW")

                team_members.append({
                    "id": emp_id_str,
                    "name": emp.get("name"),
                    "role": emp.get("role"),
                    "specialization": emp.get("specialization"),
                    "skills": emp.get("skills", []),
                    "capacity_hours": cap_h,
                    "assigned_hours": round(assigned_h, 1),
                    "workload_ratio": round(ratio, 1),
                    "active_tasks_count": len(emp_active_tasks),
                    "burnout_risk": burnout_risk,
                    "is_overloaded": ratio > 100,
                    "is_available": ratio < 80,
                })
        except Exception:
            pass

    overall_team_workload_ratio = (total_team_assigned_hours / total_team_capacity * 100) if total_team_capacity > 0 else 50.0

    # 2. PREDICT — Machine Learning Inferences
    pred = await db.project_predictions.find_one({"project_id": project_id})
    if not pred:
        from app.api.predictions import predict_project_risk
        try:
            pred = await predict_project_risk(project_id, db=db)
        except Exception:
            pred = None

    risk_class = pred.get("risk_class", "LOW") if pred else ("HIGH" if (len(overdue_tasks) > 2 or len(critical_issues) > 0) else "LOW")
    risk_prob = pred.get("risk_probability", 0.25) if pred else 0.25
    delay_days = pred.get("delay_days", 0) if pred else (len(overdue_tasks) * 3)
    delay_prob = pred.get("delay_probability", 0.3) if pred else 0.3
    budget_risk = pred.get("budget_overrun_risk", "LOW") if pred else ("HIGH" if budget_utilization > 85 else "LOW")
    overrun_amount = pred.get("budget_overrun_amount", 0) if pred else 0.0
    predicted_final_cost = pred.get("predicted_final_cost", budget) if pred else budget
    health_score = pred.get("health_score", 85) if pred else max(20, min(100, int(100 - (len(overdue_tasks) * 10) - (len(critical_issues) * 15) - max(0, budget_utilization - progress))))
    health_status = pred.get("health_status", "Healthy") if pred else ("Critical" if health_score < 50 else "Warning" if health_score < 75 else "Healthy")

    # 3. EXPLAIN — Contributing Factors Breakdown
    contributing_factors = []
    if len(overdue_tasks) > 0:
        contributing_factors.append({
            "category": "Schedule",
            "factor": f"{len(overdue_tasks)} overdue tasks causing timeline slippage",
            "severity": "high" if len(overdue_tasks) > 2 else "medium",
            "impact_score": round(min(1.0, len(overdue_tasks) * 0.25), 2),
        })
    if len(critical_issues) > 0:
        contributing_factors.append({
            "category": "Quality & Stability",
            "factor": f"{len(critical_issues)} unresolved critical issues blocking execution",
            "severity": "critical",
            "impact_score": 0.95,
        })
    if len(blocked_tasks) > 0:
        contributing_factors.append({
            "category": "Dependencies",
            "factor": f"{len(blocked_tasks)} tasks currently blocked by dependencies",
            "severity": "high" if len(blocked_tasks) > 1 else "medium",
            "impact_score": 0.7,
        })
    if budget_utilization > progress + 20 and budget > 0:
        contributing_factors.append({
            "category": "Budget",
            "factor": f"Budget utilization ({budget_utilization:.0f}%) significantly exceeds progress ({progress:.0f}%)",
            "severity": "high",
            "impact_score": 0.85,
        })
    overloaded_members = [m for m in team_members if m["is_overloaded"]]
    if overloaded_members:
        names = ", ".join(m["name"] for m in overloaded_members[:2])
        contributing_factors.append({
            "category": "Workload & Burnout",
            "factor": f"{len(overloaded_members)} team member(s) ({names}) operating above 100% capacity",
            "severity": "high",
            "impact_score": 0.8,
        })

    # Document AI insights if available
    doc_analyses = await db.document_analysis.find({"project_id": project_id}).to_list(10)
    security_issues_count = 0
    ambiguity_count = 0
    for da in doc_analyses:
        for iss in da.get("issues", []):
            if "Security" in iss.get("type", ""):
                security_issues_count += 1
            if "Ambiguity" in iss.get("type", ""):
                ambiguity_count += 1

    if security_issues_count > 0:
        contributing_factors.append({
            "category": "Document AI Security",
            "factor": f"{security_issues_count} potential security concerns identified in project documentation",
            "severity": "high",
            "impact_score": 0.75,
        })

    # 4. RECOMMEND — Active Recommendations
    recommendations = await db.recommendations.find({"projectId": project_id}).sort("createdAt", -1).to_list(50)
    if not recommendations:
        recommendations = await db.recommendations.find({"project_id": project_id}).sort("created_at", -1).to_list(50)

    serialized_recs = []
    for r in recommendations:
        serialized_recs.append({
            "id": str(r["_id"]),
            "project_id": project_id,
            "project_name": project_name,
            "title": r.get("title", r.get("action", "Recommendation")),
            "category": r.get("category", "General"),
            "priority": r.get("priority", "medium"),
            "reason": r.get("reason", ""),
            "suggested_action": r.get("suggestedAction", r.get("suggested_action", r.get("action", ""))),
            "expected_impact": r.get("expectedImpact", r.get("expected_impact", r.get("impact", ""))),
            "status": r.get("status", "pending"),
            "created_at": r.get("createdAt", r.get("created_at")),
        })

    # 5. OPTIMIZE — Resource Allocation Suggestions
    from app.services.resource_optimizer import compute_resource_optimization
    optimization_result = await compute_resource_optimization(project_id, db)

    return {
        "project": {
            "id": project_id,
            "name": project_name,
            "description": project.get("description", ""),
            "status": project.get("status", "planning"),
            "priority": project.get("priority", "medium"),
            "budget": budget,
            "current_expenditure": current_expenditure,
            "budget_utilization": round(budget_utilization, 1),
            "progress": progress,
            "start_date": project.get("start_date") or project.get("startDate"),
            "end_date": project.get("end_date") or project.get("endDate"),
            "manager_id": project.get("manager_id") or project.get("projectManagerId"),
        },
        "observe": {
            "tasks": {
                "total": total_tasks,
                "active": len(active_tasks),
                "completed": len(completed_tasks),
                "overdue": len(overdue_tasks),
                "blocked": len(blocked_tasks),
                "high_priority": len(high_priority_tasks),
                "completion_rate": round(task_completion_rate, 1),
            },
            "issues": {
                "total": len(issues),
                "open": len(open_issues),
                "critical": len(critical_issues),
                "high": len(high_issues),
                "resolved": len(resolved_issues),
            },
            "sprints": {
                "total": len(sprints),
                "completed": len(completed_sprints),
                "avg_velocity": round(avg_velocity, 1),
            },
            "team": {
                "members_count": len(team_members),
                "members": team_members,
                "overall_workload_ratio": round(overall_team_workload_ratio, 1),
                "overloaded_count": len(overloaded_members),
            },
            "document_ai": {
                "analyzed_docs_count": len(doc_analyses),
                "security_findings": security_issues_count,
                "ambiguity_findings": ambiguity_count,
            }
        },
        "predict": {
            "risk_class": risk_class,
            "risk_probability": round(risk_prob, 2),
            "delay_days": delay_days,
            "delay_probability": round(delay_prob, 2),
            "budget_overrun_risk": budget_risk,
            "budget_overrun_amount": round(overrun_amount, 2),
            "predicted_final_cost": round(predicted_final_cost, 2),
            "health_score": health_score,
            "health_status": health_status,
        },
        "explain": {
            "health_score": health_score,
            "contributing_factors": contributing_factors,
            "primary_driver": contributing_factors[0]["factor"] if contributing_factors else "Project metrics are aligned with planned targets.",
        },
        "recommend": {
            "total_count": len(serialized_recs),
            "pending_count": sum(1 for r in serialized_recs if r["status"] == "pending"),
            "accepted_count": sum(1 for r in serialized_recs if r["status"] == "accepted"),
            "recommendations": serialized_recs,
        },
        "optimize": optimization_result,
        "decide": {
            "can_generate_recommendations": True,
            "can_apply_optimization": len(optimization_result.get("reallocation_suggestions", [])) > 0,
            "pending_decisions_count": sum(1 for r in serialized_recs if r["status"] == "pending") + len(optimization_result.get("reallocation_suggestions", [])),
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


# ==============================================================================
# AUTHORITATIVE DECISION LOG CRUD & WORKFLOW
# ==============================================================================

async def create_decision(db, data: Any, current_user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates a new formal Decision record in db.decisions.
    Enforces server-side project scoping and authorization.
    """
    role = current_user.get("role", "team_member")
    uid = str(current_user["_id"])
    user_name = current_user.get("name", "Project Manager")

    if role == "team_member":
        raise PermissionError("Access denied: Team Members cannot create management decisions.")

    project_id = str(data.project_id)
    authorized_pids = await get_authorized_project_ids(db, current_user)
    if project_id not in authorized_pids:
        raise PermissionError(f"Access denied: You do not manage project {project_id}.")

    # Fetch project details
    project = await db.projects.find_one({"_id": ObjectId(project_id) if ObjectId.is_valid(project_id) else project_id})
    if not project:
        raise ValueError("Referenced project not found")

    project_name = project.get("name", "Project")

    now_utc = datetime.now(timezone.utc)
    status_val = data.decision_status.value if hasattr(data.decision_status, "value") else str(data.decision_status)
    type_val = data.decision_type.value if hasattr(data.decision_type, "value") else str(data.decision_type)
    priority_val = data.priority.value if hasattr(data.priority, "value") else str(data.priority)

    decided_at = now_utc if status_val in ("APPROVED", "REJECTED", "DEFERRED") else None
    decision_maker_id = uid if status_val in ("APPROVED", "REJECTED", "DEFERRED") else None
    decision_maker_name = user_name if status_val in ("APPROVED", "REJECTED", "DEFERRED") else None

    # Construct audit trail
    audit_trail = [{
        "action": "CREATED",
        "performed_by_id": uid,
        "performed_by_name": user_name,
        "timestamp": now_utc,
        "previous_status": None,
        "new_status": status_val,
        "notes": f"Decision created with status {status_val}" + (f": {data.decision_rationale}" if data.decision_rationale else ""),
    }]

    doc = {
        "project_id": project_id,
        "project_name": project_name,
        "decision_type": type_val,
        "title": data.title,
        "description": data.description,
        "decision_status": status_val,
        "priority": priority_val,
        "created_by": uid,
        "created_by_name": user_name,
        "decision_maker_id": decision_maker_id,
        "decision_maker_name": decision_maker_name,
        "created_at": now_utc,
        "decided_at": decided_at,
        "source_type": data.source_type or "manual",
        "source_reference_id": str(data.source_reference_id) if data.source_reference_id else None,
        "source_recommendation_id": str(data.source_recommendation_id) if data.source_recommendation_id else None,
        "source_prediction_id": str(data.source_prediction_id) if data.source_prediction_id else None,
        "source_issue_id": str(data.source_issue_id) if data.source_issue_id else None,
        "source_task_id": str(data.source_task_id) if data.source_task_id else None,
        "source_resource_request_id": str(data.source_resource_request_id) if data.source_resource_request_id else None,
        "observed_facts": data.observed_facts or [],
        "prediction_summary": data.prediction_summary or {},
        "recommendation_summary": data.recommendation_summary or {},
        "alternatives": data.alternatives or [],
        "selected_action": data.selected_action,
        "decision_rationale": data.decision_rationale,
        "affected_entities": data.affected_entities or [],
        "expected_impact": data.expected_impact,
        "audit_trail": audit_trail,
    }

    result = await db.decisions.insert_one(doc)
    doc["_id"] = result.inserted_id
    doc["id"] = str(result.inserted_id)

    # Optional: If decision is tied to a source recommendation, synchronize recommendation status
    if data.source_recommendation_id or (data.source_type == "recommendation" and data.source_reference_id):
        rec_id = data.source_recommendation_id or data.source_reference_id
        if rec_id and status_val == "APPROVED":
            await db.recommendations.update_one(
                {"_id": ObjectId(rec_id) if ObjectId.is_valid(rec_id) else rec_id},
                {"$set": {"status": "accepted", "updatedAt": now_utc, "updated_at": now_utc}}
            )
        elif rec_id and status_val == "REJECTED":
            await db.recommendations.update_one(
                {"_id": ObjectId(rec_id) if ObjectId.is_valid(rec_id) else rec_id},
                {"$set": {"status": "rejected", "updatedAt": now_utc, "updated_at": now_utc}}
            )

    # Dispatch notification for decision creation / action
    notif_type = f"DECISION_{status_val}" if status_val in ("APPROVED", "REJECTED", "DEFERRED") else "DECISION_CREATED"
    notif_msg = f"Decision '{data.title}' recorded on project '{project_name}' ({status_val})."
    if data.decision_rationale:
        notif_msg += f" Rationale: {data.decision_rationale}"

    await create_notification(
        db=db,
        user_id=uid,
        notification_type=notif_type,
        title=f"Decision {status_val.capitalize()}: {data.title}",
        message=notif_msg,
        related_project_id=project_id,
        assigned_by=uid,
        assigned_by_name=user_name,
        severity="high" if priority_val in ("high", "critical") else "medium",
    )

    return doc


async def get_decisions(
    db,
    current_user: Dict[str, Any],
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    decision_type: Optional[str] = None,
    priority: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Returns list of decision records strictly scoped by user's authorized projects.
    """
    role = current_user.get("role", "team_member")
    if role == "team_member":
        raise PermissionError("Access denied: Team Members cannot browse management decision logs.")

    authorized_pids = await get_authorized_project_ids(db, current_user)
    if not authorized_pids:
        return []

    query: Dict[str, Any] = {}

    if project_id:
        if project_id not in authorized_pids:
            return []
        query["project_id"] = project_id
    else:
        query["project_id"] = {"$in": authorized_pids}

    if status:
        query["decision_status"] = status.upper()
    if decision_type:
        query["decision_type"] = decision_type
    if priority:
        query["priority"] = priority.lower()

    decisions = await db.decisions.find(query).sort("created_at", -1).to_list(1000)
    return [serialize_decision(d) for d in decisions]


async def get_decision_by_id(db, decision_id: str, current_user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retrieves single decision with strict project authorization checks.
    """
    role = current_user.get("role", "team_member")
    if role == "team_member":
        raise PermissionError("Access denied: Team Members cannot view management decision records.")

    try:
        decision = await db.decisions.find_one({"_id": ObjectId(decision_id) if ObjectId.is_valid(decision_id) else decision_id})
    except Exception:
        decision = None

    if not decision:
        raise ValueError("Decision record not found")

    project_id = str(decision["project_id"])
    authorized_pids = await get_authorized_project_ids(db, current_user)
    if project_id not in authorized_pids:
        raise PermissionError(f"Access denied: You are not authorized to view decisions for project {project_id}.")

    return serialize_decision(decision)


async def record_decision_action(
    db,
    decision_id: str,
    action: str,
    rationale: str,
    current_user: Dict[str, Any],
    selected_action: Optional[str] = None,
    selected_alternative_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes a formal decision state transition (APPROVED, REJECTED, DEFERRED).
    Enforces server-side RBAC scoping and validates state transitions.
    """
    role = current_user.get("role", "team_member")
    uid = str(current_user["_id"])
    user_name = current_user.get("name", "Project Manager")

    if role == "team_member":
        raise PermissionError("Access denied: Team Members cannot decide or mutate decision records.")

    target_status = action.upper()
    if target_status not in ("APPROVED", "REJECTED", "DEFERRED"):
        raise ValueError(f"Invalid decision action '{action}'. Must be APPROVED, REJECTED, or DEFERRED.")

    try:
        decision = await db.decisions.find_one({"_id": ObjectId(decision_id) if ObjectId.is_valid(decision_id) else decision_id})
    except Exception:
        decision = None

    if not decision:
        raise ValueError("Decision record not found")

    project_id = str(decision["project_id"])
    authorized_pids = await get_authorized_project_ids(db, current_user)
    if project_id not in authorized_pids:
        raise PermissionError(f"Access denied: You do not manage project {project_id}.")

    current_status = decision.get("decision_status", "PENDING")

    # Idempotent return if already in the target state
    if current_status == target_status:
        return serialize_decision(decision)

    # State machine transition safety
    # Valid: PENDING -> APPROVED | REJECTED | DEFERRED
    # Valid: DEFERRED -> APPROVED | REJECTED
    # Invalid: APPROVED -> PENDING, REJECTED -> PENDING
    if current_status in ("APPROVED", "REJECTED") and target_status == "PENDING":
        raise ValueError(f"Invalid state transition: Cannot revert finalized {current_status} decision back to PENDING.")

    if not rationale or not rationale.strip():
        raise ValueError("Human decision rationale is mandatory and cannot be empty.")

    now_utc = datetime.now(timezone.utc)
    audit_entry = {
        "action": f"SET_{target_status}",
        "performed_by_id": uid,
        "performed_by_name": user_name,
        "timestamp": now_utc,
        "previous_status": current_status,
        "new_status": target_status,
        "notes": f"Rationale: {rationale.strip()}" + (f" | Notes: {notes.strip()}" if notes else ""),
    }

    # Update alternatives selection if provided
    alternatives = decision.get("alternatives", [])
    if selected_alternative_id and alternatives:
        for alt in alternatives:
            alt_id = str(alt.get("id", ""))
            alt["is_selected"] = (alt_id == str(selected_alternative_id))
            if alt["is_selected"] and not selected_action:
                selected_action = alt.get("title")

    update_fields: Dict[str, Any] = {
        "decision_status": target_status,
        "decision_rationale": rationale.strip(),
        "decision_maker_id": uid,
        "decision_maker_name": user_name,
        "decided_at": now_utc,
    }

    if selected_action:
        update_fields["selected_action"] = selected_action
    if alternatives:
        update_fields["alternatives"] = alternatives

    updated_doc = await db.decisions.find_one_and_update(
        {"_id": decision["_id"]},
        {
            "$set": update_fields,
            "$push": {"audit_trail": audit_entry},
        },
        return_document=True,
    )

    # Synchronize linked source recommendation
    rec_id = decision.get("source_recommendation_id") or (decision.get("source_reference_id") if decision.get("source_type") == "recommendation" else None)
    if rec_id:
        if target_status == "APPROVED":
            await db.recommendations.update_one(
                {"_id": ObjectId(rec_id) if ObjectId.is_valid(rec_id) else rec_id},
                {"$set": {"status": "accepted", "updatedAt": now_utc, "updated_at": now_utc}}
            )
        elif target_status == "REJECTED":
            await db.recommendations.update_one(
                {"_id": ObjectId(rec_id) if ObjectId.is_valid(rec_id) else rec_id},
                {"$set": {"status": "rejected", "updatedAt": now_utc, "updated_at": now_utc}}
            )

    # Emit notification
    notif_msg = f"Decision '{decision.get('title')}' for project '{decision.get('project_name')}' changed to {target_status} by {user_name}. Rationale: {rationale.strip()}"
    await create_notification(
        db=db,
        user_id=uid,
        notification_type=f"DECISION_{target_status}",
        title=f"Decision {target_status.capitalize()}: {decision.get('title')}",
        message=notif_msg,
        related_project_id=project_id,
        assigned_by=uid,
        assigned_by_name=user_name,
        severity="high" if decision.get("priority") in ("high", "critical") else "medium",
    )

    return serialize_decision(updated_doc)


async def prepare_decision_draft(
    db,
    project_id: str,
    source_type: str,
    source_id: Optional[str] = None,
    current_user: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Pre-fills a rich Decision draft from live project intelligence, recommendations,
    or resource optimization findings, avoiding manual data re-entry.
    """
    role = current_user.get("role", "team_member") if current_user else "admin"
    if role == "team_member":
        raise PermissionError("Access denied: Team Members cannot draft management decisions.")

    intel = await gather_decision_intelligence(project_id, db)
    project = intel["project"]
    predict = intel["predict"]
    explain = intel["explain"]
    observe = intel["observe"]

    draft: Dict[str, Any] = {
        "project_id": project_id,
        "project_name": project["name"],
        "source_type": source_type,
        "source_reference_id": source_id,
        "source_recommendation_id": None,
        "source_prediction_id": None,
        "source_issue_id": None,
        "source_task_id": None,
        "source_resource_request_id": None,
        "observed_facts": explain.get("contributing_factors", []),
        "prediction_summary": {
            "risk_class": predict.get("risk_class"),
            "health_score": predict.get("health_score"),
            "delay_days": predict.get("delay_days"),
            "budget_overrun_amount": predict.get("budget_overrun_amount"),
            "health_status": predict.get("health_status"),
        },
        "recommendation_summary": None,
        "alternatives": [],
        "selected_action": None,
        "decision_rationale": "",
        "decision_type": "OTHER",
        "title": f"Decision for {project['name']}",
        "priority": "medium",
        "affected_entities": [],
        "expected_impact": None,
    }

    # If drafted from a specific Recommendation
    if source_type == "recommendation" and source_id:
        try:
            rec = await db.recommendations.find_one({"_id": ObjectId(source_id) if ObjectId.is_valid(source_id) else source_id})
        except Exception:
            rec = None

        if rec:
            rec_title = rec.get("title", rec.get("action", "Project Recommendation"))
            rec_action = rec.get("suggestedAction", rec.get("suggested_action", rec.get("action", "")))
            rec_impact = rec.get("expectedImpact", rec.get("expected_impact", rec.get("impact", "")))
            rec_category = rec.get("category", "General")
            rec_priority = rec.get("priority", "medium").lower()

            draft["source_recommendation_id"] = str(rec["_id"])
            draft["title"] = rec_title
            draft["priority"] = rec_priority
            draft["expected_impact"] = rec_impact

            # Map category to DecisionType
            cat_upper = rec_category.upper()
            if "RESOURCE" in cat_upper or "WORKLOAD" in cat_upper:
                draft["decision_type"] = "RESOURCE_REALLOCATION"
            elif "SCHEDULE" in cat_upper or "DELAY" in cat_upper:
                draft["decision_type"] = "SCHEDULE_COMPRESSION"
            elif "SPRINT" in cat_upper or "SCOPE" in cat_upper:
                draft["decision_type"] = "SPRINT_RESCOPE"
            elif "BUDGET" in cat_upper or "COST" in cat_upper:
                draft["decision_type"] = "BUDGET_INVESTIGATION"
            elif "SECURITY" in cat_upper or "CRITICAL" in cat_upper or "QUALITY" in cat_upper:
                draft["decision_type"] = "QUALITY_ESCALATION"
            else:
                draft["decision_type"] = "RISK_MITIGATION"

            draft["recommendation_summary"] = {
                "id": str(rec["_id"]),
                "title": rec_title,
                "category": rec_category,
                "suggested_action": rec_action,
                "reason": rec.get("reason", ""),
                "expected_impact": rec_impact,
            }

            draft["alternatives"] = [
                {
                    "id": "alt-1",
                    "title": f"Execute Recommended Action: {rec_action}",
                    "description": f"Adopt NexusAI recommendation to achieve: {rec_impact}",
                    "is_selected": True,
                },
                {
                    "id": "alt-2",
                    "title": "Maintain Baseline Status Quo",
                    "description": "Accept current schedule/budget trajectory without intervening.",
                    "is_selected": False,
                },
                {
                    "id": "alt-3",
                    "title": "Defer Decision to Next Sprint Review",
                    "description": "Monitor indicators for one additional cycle before taking action.",
                    "is_selected": False,
                }
            ]
            draft["selected_action"] = rec_action

    # If drafted from Resource Optimization
    elif source_type == "resource_optimization":
        draft["decision_type"] = "RESOURCE_REALLOCATION"
        draft["title"] = f"Resource Workload Optimization — {project['name']}"
        opt = intel.get("optimize", {})
        reallocs = opt.get("reallocation_suggestions", [])
        if reallocs:
            top_r = reallocs[0]
            draft["selected_action"] = top_r.get("action_summary", "Reallocate workload internally")
            draft["expected_impact"] = top_r.get("expected_outcome", "Rebalance team workload and mitigate burnout risk")
            draft["affected_entities"] = [
                {"type": "employee", "name": top_r.get("from_employee_name"), "id": top_r.get("from_employee_id"), "role": "Source (Overloaded)"},
                {"type": "employee", "name": top_r.get("to_employee_name"), "id": top_r.get("to_employee_id"), "role": "Target (Available)"},
            ]
            draft["alternatives"] = [
                {
                    "id": "alt-opt-1",
                    "title": f"Internal Reallocation: {top_r.get('from_employee_name')} → {top_r.get('to_employee_name')}",
                    "description": f"Transfer {top_r.get('transfer_hours', 16)}h on task '{top_r.get('task_title')}'",
                    "is_selected": True,
                },
                {
                    "id": "alt-opt-2",
                    "title": "Explore Cross-PM Resource Discovery",
                    "description": "Request candidate specialist allocation from another PM's team.",
                    "is_selected": False,
                },
                {
                    "id": "alt-opt-3",
                    "title": "Descope Non-Critical Project Deliverables",
                    "description": "Remove low-priority tasks from current release scope.",
                    "is_selected": False,
                }
            ]

    return draft


async def get_decision_stats(db, current_user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns aggregated decision statistics scoped to the user's authorized portfolio.
    """
    role = current_user.get("role", "team_member")
    if role == "team_member":
        return {"total": 0, "pending": 0, "approved": 0, "rejected": 0, "deferred": 0, "by_type": {}}

    authorized_pids = await get_authorized_project_ids(db, current_user)
    if not authorized_pids:
        return {"total": 0, "pending": 0, "approved": 0, "rejected": 0, "deferred": 0, "by_type": {}}

    decisions = await db.decisions.find({"project_id": {"$in": authorized_pids}}).to_list(2000)

    total = len(decisions)
    pending = sum(1 for d in decisions if d.get("decision_status") == "PENDING")
    approved = sum(1 for d in decisions if d.get("decision_status") == "APPROVED")
    rejected = sum(1 for d in decisions if d.get("decision_status") == "REJECTED")
    deferred = sum(1 for d in decisions if d.get("decision_status") == "DEFERRED")

    by_type: Dict[str, int] = {}
    for d in decisions:
        t = d.get("decision_type", "OTHER")
        by_type[t] = by_type.get(t, 0) + 1

    return {
        "total": total,
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
        "deferred": deferred,
        "by_type": by_type,
    }
