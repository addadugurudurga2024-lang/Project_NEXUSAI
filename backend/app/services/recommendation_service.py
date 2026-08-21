"""
Recommendation Engine Service for NexusAI
Generates explainable, context-aware decision recommendations from:
- MongoDB project metrics (tasks, issues, budget, progress, sprints)
- Machine Learning inferences (risk, deadline delay, budget overrun, health score)
- Employee workload, capacity, burnout predictions, and skills
- Document AI findings (security concerns, ambiguities, missing criteria)
"""
# pyrefly: ignore [missing-import]
from bson import ObjectId
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.services.notification_service import notify_project_stakeholders, create_notification


async def generate_project_recommendations(project_id: str, db) -> List[Dict[str, Any]]:
    """
    Generates actionable, explainable recommendations using real MongoDB data.
    """
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id)})
    except Exception:
        project = None

    if not project:
        return []

    project_name = project.get("name", "Project")
    budget = float(project.get("budget", 0) or 0)
    expenditure = float(project.get("current_expenditure", 0) or 0)
    progress = float(project.get("progress", 0) or 0)
    budget_utilization = (expenditure / budget * 100) if budget > 0 else 0

    # 1. Fetch ML Prediction
    pred = await db.project_predictions.find_one({"project_id": project_id})
    if not pred:
        from app.api.predictions import predict_project_risk
        try:
            pred = await predict_project_risk(project_id, db=db)
        except Exception:
            pred = {}

    risk_class = pred.get("risk_class", "LOW")
    delay_days = pred.get("delay_days", 0)
    budget_overrun_risk = pred.get("budget_overrun_risk", "LOW")
    overrun_amount = pred.get("budget_overrun_amount", 0)
    health_score = pred.get("health_score", 85)
    risk_prob = pred.get("risk_probability", 0.0)

    # 2. Fetch Tasks & Overdue Work
    tasks = await db.tasks.find({"project_id": project_id}).to_list(500)
    active_tasks = [t for t in tasks if t.get("status") not in ["done"]]
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    overdue_tasks = [
        t for t in active_tasks
        if t.get("due_date") and t.get("due_date") < today_str
    ]
    blocked_tasks = [t for t in active_tasks if t.get("status") == "blocked"]
    high_priority_active_tasks = [t for t in active_tasks if t.get("priority") in ["high", "critical"]]

    # 3. Fetch Issues
    issues = await db.issues.find({"project_id": project_id}).to_list(500)
    critical_unresolved_issues = [
        i for i in issues
        if i.get("severity") == "critical" and i.get("status") not in ["resolved", "closed"]
    ]
    high_unresolved_issues = [
        i for i in issues
        if i.get("severity") == "high" and i.get("status") not in ["resolved", "closed"]
    ]

    # 4. Fetch Employees Workload & Skills
    team_ids = project.get("team_member_ids", []) or project.get("teamMemberIds", []) or []
    employees = []
    for tid in team_ids:
        try:
            emp = await db.employees.find_one({"_id": ObjectId(tid)})
            if emp:
                emp_id_str = str(emp["_id"])
                emp_tasks = [t for t in active_tasks if t.get("assignee_id") == emp_id_str]
                assigned_hours = sum(float(t.get("estimated_hours", 0) or 0) for t in emp_tasks)
                capacity = float(emp.get("weekly_capacity_hours", 40) or 40)
                workload_ratio = (assigned_hours / capacity * 100) if capacity > 0 else 0

                burnout_pred = await db.employee_risk_predictions.find_one({"employee_id": emp_id_str})
                burnout_risk = burnout_pred.get("risk_level", "LOW") if burnout_pred else ("HIGH" if workload_ratio > 110 else "LOW")

                employees.append({
                    "id": emp_id_str,
                    "name": emp.get("name"),
                    "role": emp.get("role"),
                    "specialization": emp.get("specialization"),
                    "skills": emp.get("skills", []),
                    "capacity": capacity,
                    "assigned_hours": assigned_hours,
                    "workload_ratio": workload_ratio,
                    "burnout_risk": burnout_risk,
                    "active_tasks": emp_tasks,
                })
        except Exception:
            pass

    overloaded_employees = [e for e in employees if e["workload_ratio"] > 100 or e["burnout_risk"] == "HIGH"]
    available_employees = [e for e in employees if e["workload_ratio"] < 80]

    # 5. Fetch Document AI Analysis
    doc_analyses = await db.document_analysis.find({"project_id": project_id}).to_list(10)
    security_concerns = []
    ambiguities = []
    missing_criteria = []
    for da in doc_analyses:
        for iss in da.get("issues", []):
            if "Security" in iss.get("type", ""):
                security_concerns.append(iss)
            elif "Ambiguity" in iss.get("type", ""):
                ambiguities.append(iss)
            elif "Missing" in iss.get("type", "") or "Incomplete" in iss.get("type", ""):
                missing_criteria.append(iss)

    generated_recommendations = []

    # ── RULE 1: HIGH PROJECT RISK ─────────────────────────────────────────────
    if risk_class == "HIGH" or health_score < 60:
        overdue_count = len(overdue_tasks)
        crit_count = len(critical_unresolved_issues)
        reason_parts = []
        if overdue_count > 0:
            reason_parts.append(f"{overdue_count} overdue task(s)")
        if crit_count > 0:
            reason_parts.append(f"{crit_count} critical issue(s)")
        if risk_prob > 0.5:
            reason_parts.append(f"{risk_prob:.0%} ML failure probability")

        reason_str = f"Project exhibits high systemic risk driven by: {', '.join(reason_parts) if reason_parts else 'low overall health score'}."
        generated_recommendations.append(_build_recommendation_doc(
            project_id=project_id,
            project_name=project_name,
            category="Risk Management",
            priority="critical",
            title="Prioritize Overdue Critical Tasks & Risk Mitigation",
            description="Initiate an emergency risk mitigation review with project leads to unblock critical path items.",
            reason=reason_str,
            suggested_action="Schedule an immediate stakeholder risk alignment meeting and re-prioritize milestone dependencies.",
            expected_impact="Reduces schedule risk and stabilizes project health trajectory.",
        ))

    # ── RULE 2: EMPLOYEE OVERLOAD & BURNOUT ──────────────────────────────────
    for over_emp in overloaded_employees:
        generated_recommendations.append(_build_recommendation_doc(
            project_id=project_id,
            project_name=project_name,
            employee_id=over_emp["id"],
            employee_name=over_emp["name"],
            category="Resource Management",
            priority="high",
            title=f"Rebalance Workload for {over_emp['name']}",
            description=f"{over_emp['name']} is allocated {over_emp['assigned_hours']:.1f}h against a {over_emp['capacity']:.1f}h weekly capacity ({over_emp['workload_ratio']:.0f}% load).",
            reason=f"Current workload exceeds safe threshold with active burnout indicator flagged.",
            suggested_action=f"Consider offloading non-critical tasks from {over_emp['name']} to balance sprint commitments.",
            expected_impact="Reduces workload concentration, prevents burnout, and ensures delivery quality.",
        ))

    # ── RULE 3: AVAILABLE SPECIALIST REALLOCATION ────────────────────────────
    for over_emp in overloaded_employees:
        for avail_emp in available_employees:
            # Check skill or specialization overlap
            overlap = set(s.lower() for s in over_emp["skills"]) & set(s.lower() for s in avail_emp["skills"])
            spec_match = (
                over_emp.get("specialization") and avail_emp.get("specialization") and
                over_emp["specialization"].lower() == avail_emp["specialization"].lower()
            )
            if overlap or spec_match:
                skill_str = ", ".join(list(overlap)[:2]) if overlap else avail_emp.get("specialization")
                generated_recommendations.append(_build_recommendation_doc(
                    project_id=project_id,
                    project_name=project_name,
                    employee_id=avail_emp["id"],
                    employee_name=avail_emp["name"],
                    category="Capacity Optimization",
                    priority="medium",
                    title=f"Consider Reallocating Task(s) from {over_emp['name']} to {avail_emp['name']}",
                    description=f"{avail_emp['name']} has available bandwidth ({avail_emp['workload_ratio']:.0f}% load) and compatible competencies ({skill_str}).",
                    reason=f"Skill compatibility ({skill_str}) combined with an existing workload gap between team members.",
                    suggested_action=f"Assign suitable pending task(s) from {over_emp['name']} to {avail_emp['name']}.",
                    expected_impact=f"Improves capacity utilization and reduces schedule bottleneck for {over_emp['name']}.",
                ))
                break  # one specialist recommendation per overloaded employee

    # ── RULE 4: CRITICAL & HIGH SEVERITY ISSUES ──────────────────────────────
    if critical_unresolved_issues or len(high_unresolved_issues) >= 2:
        total_defect_count = len(critical_unresolved_issues) + len(high_unresolved_issues)
        generated_recommendations.append(_build_recommendation_doc(
            project_id=project_id,
            project_name=project_name,
            category="Quality Management",
            priority="critical" if critical_unresolved_issues else "high",
            title="Prioritize Critical Defect Resolution",
            description=f"Project contains {len(critical_unresolved_issues)} critical and {len(high_unresolved_issues)} high-severity unresolved defect(s).",
            reason=f"Active critical issues ({total_defect_count} total) introduce severe release and stability risk.",
            suggested_action="Temporarily freeze new feature work to triage and resolve critical-path bugs.",
            expected_impact="Prevents compounding technical debt and mitigates system disruption.",
        ))

    # ── RULE 5: BUDGET PRESSURE ──────────────────────────────────────────────
    if (budget > 0 and budget_utilization > 75 and budget_utilization > progress + 15) or budget_overrun_risk == "HIGH":
        generated_recommendations.append(_build_recommendation_doc(
            project_id=project_id,
            project_name=project_name,
            category="Budget Management",
            priority="high",
            title="Review Project Spending & Cost Allocation",
            description=f"Expenditure stands at ${expenditure:,.0f} of ${budget:,.0f} ({budget_utilization:.0f}%) while recorded progress is only {progress:.0f}%.",
            reason=f"High budget utilization relative to milestone delivery (projected overrun: ${overrun_amount:,.0f}).",
            suggested_action="Conduct a detailed financial audit to renegotiate vendor costs or adjust scope boundaries.",
            expected_impact="Controls budget overrun risk and realigns cost runway with remaining deliverables.",
        ))

    # ── RULE 6: DEADLINE PRESSURE / SCHEDULE COMPRESSION ─────────────────────
    if delay_days > 5 or (len(overdue_tasks) >= 2 and progress < 60):
        generated_recommendations.append(_build_recommendation_doc(
            project_id=project_id,
            project_name=project_name,
            category="Schedule Management",
            priority="high",
            title="Review Sprint Scope & Delivery Schedule",
            description=f"ML forecasting projects an estimated delay of {delay_days} day(s) based on current velocity and remaining workload.",
            reason=f"Schedule compression detected with {len(overdue_tasks)} overdue tasks and low completion velocity.",
            suggested_action="Review upcoming sprint backlog story points and negotiate milestone extensions if necessary.",
            expected_impact="Improves delivery predictability and restores team momentum.",
        ))

    # ── RULE 7: DOCUMENT AI ANALYSIS FINDINGS ────────────────────────────────
    if security_concerns:
        first_sec = security_concerns[0]
        generated_recommendations.append(_build_recommendation_doc(
            project_id=project_id,
            project_name=project_name,
            category="Security & Compliance",
            priority="high",
            title="Review Requirement Security Controls with Specialist",
            description=f"Document AI flagged potential security sensitivity: {first_sec.get('title', 'Security requirement detected')}.",
            reason=f"Document analysis identified {len(security_concerns)} security-related requirement pattern(s).",
            suggested_action="Conduct a formal security requirements review with a Cybersecurity Specialist before implementation.",
            expected_impact="Ensures compliance with security standards and prevents post-release vulnerabilities.",
        ))

    if ambiguities:
        generated_recommendations.append(_build_recommendation_doc(
            project_id=project_id,
            project_name=project_name,
            category="Requirements Clarity",
            priority="medium",
            title="Clarify Ambiguous Requirement Specifications",
            description=f"Document AI detected {len(ambiguities)} requirement statement(s) with subjective or vague criteria.",
            reason="Ambiguous specifications correlate with rework and missed acceptance criteria.",
            suggested_action="Define quantifiable acceptance criteria for flagged requirements with product stakeholders.",
            expected_impact="Reduces rework and aligns engineering deliverables with client expectations.",
        ))

    # ── FALLBACK: HEALTHY PROJECT ────────────────────────────────────────────
    if not generated_recommendations:
        generated_recommendations.append(_build_recommendation_doc(
            project_id=project_id,
            project_name=project_name,
            category="Monitoring",
            priority="low",
            title="Maintain Execution Cadence & Health Monitoring",
            description=f"Project health is strong ({health_score:.0f}/100) with balanced workload and no critical blockers.",
            reason="Current metrics indicate stable sprint progress, manageable risks, and on-track expenditure.",
            suggested_action="Continue planned execution with routine weekly milestone check-ins.",
            expected_impact="Maintains current positive project trajectory.",
        ))

    # ── PERSISTENCE INTO `recommendations` COLLECTION ────────────────────────
    # Clear previous pending recommendations for this project, keep accepted/completed ones
    await db.recommendations.delete_many({
        "$or": [{"projectId": project_id}, {"project_id": project_id}],
        "status": "pending",
    })

    if generated_recommendations:
        await db.recommendations.insert_many(generated_recommendations)

    # Notify Project Manager & Admins about new actionable recommendations
    high_priority_recs = [r for r in generated_recommendations if r["priority"] in ["critical", "high"]]
    if high_priority_recs:
        await notify_project_stakeholders(
            db=db,
            project_id=project_id,
            notification_type="new_recommendations",
            title=f"New Decision Recommendations: {project_name}",
            message=f"{len(high_priority_recs)} high-priority recommendation(s) generated for your review.",
            severity="high",
        )

    # Format return list
    formatted_result = []
    for r in generated_recommendations:
        r_copy = dict(r)
        r_copy["id"] = str(r_copy["_id"])
        del r_copy["_id"]
        formatted_result.append(r_copy)

    return formatted_result


def _build_recommendation_doc(
    project_id: str,
    project_name: str,
    category: str,
    priority: str,
    title: str,
    description: str,
    reason: str,
    suggested_action: str,
    expected_impact: str,
    employee_id: Optional[str] = None,
    employee_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Builds a recommendation document adhering to both authoritative and compatibility schemas."""
    return {
        # Authoritative schema fields
        "projectId": project_id,
        "employeeId": employee_id,
        "category": category,
        "priority": priority,
        "title": title,
        "description": description,
        "reason": reason,
        "suggestedAction": suggested_action,
        "expectedImpact": expected_impact,
        "status": "pending",
        "createdAt": datetime.utcnow(),
        # Compatibility fields
        "project_id": project_id,
        "project_name": project_name,
        "employee_id": employee_id,
        "employee_name": employee_name,
        "suggested_action": suggested_action,
        "action": suggested_action,
        "expected_impact": expected_impact,
        "impact": expected_impact,
        "created_at": datetime.utcnow(),
    }
