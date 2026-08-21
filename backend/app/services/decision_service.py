"""
Decision Intelligence Service for NexusAI
Synthesizes OBSERVE, PREDICT, EXPLAIN, RECOMMEND, OPTIMIZE, DECIDE metrics
using actual MongoDB project-management data and ML inferences.
"""
# pyrefly: ignore [missing-import]
from bson import ObjectId
from datetime import datetime
from typing import Dict, Any, List, Optional


async def gather_decision_intelligence(project_id: str, db) -> Dict[str, Any]:
    """
    Assembles complete Decision Intelligence data bundle for a project.
    """
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id)})
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
            emp = await db.employees.find_one({"_id": ObjectId(tid)})
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
        # Generate prediction on the fly if missing
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
