"""
What-If Simulation & Scenario Analysis Service for NexusAI
Authoritative, isolated in-memory scenario evaluation layer.
CRITICAL RULE: NEVER MUTATES LIVE OPERATIONAL DATA IN MONGODB.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from bson import ObjectId
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import uuid

from app.models.simulation import (
    ScenarioType,
    SimulationRequest,
    SimulationResult,
    SimulationStateSnapshot,
    SimulationComparisonMetric,
    SimulationExplanation,
    SimulationProjectOptions,
)
from ml.inference.project_risk import predict_project_risk_inference
from ml.inference.deadline_delay import predict_deadline_delay, _parse_dates
from ml.inference.budget_overrun import predict_budget_overrun
from ml.inference.project_health import calculate_project_health


async def get_simulation_options(project_id: str, db) -> SimulationProjectOptions:
    """
    Returns available project data (tasks, members, gaps, candidates) for the Scenario Builder.
    Read-only query on MongoDB.
    """
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id)})
    except Exception:
        project = None

    if not project:
        raise ValueError("Project not found")

    project_name = project.get("name", "Project")
    team_member_ids = [str(x) for x in project.get("team_member_ids", [])]

    # Fetch active tasks
    valid_pid_objs = [ObjectId(project_id)] if ObjectId.is_valid(project_id) else []
    tasks_cursor = db.tasks.find({
        "project_id": {"$in": [project_id] + valid_pid_objs},
        "status": {"$nin": ["done"]}
    })
    active_tasks_raw = await tasks_cursor.to_list(500)
    active_tasks = []
    for t in active_tasks_raw:
        aid = str(t.get("assignee_id", "") or t.get("assigned_to", "") or "")
        active_tasks.append({
            "id": str(t["_id"]),
            "title": t.get("title", "Task"),
            "priority": t.get("priority", "medium"),
            "estimated_hours": float(t.get("estimated_hours", 0) or 0),
            "status": t.get("status", "todo"),
            "due_date": t.get("due_date"),
            "assignee_id": aid,
            "assignee_name": t.get("assignee_name", "Unassigned"),
            "is_overdue": bool(t.get("due_date") and t.get("due_date") < datetime.utcnow().strftime("%Y-%m-%d")),
        })

    # Fetch team members
    project_team_eids = set(str(x) for x in (project.get("team_member_ids") or project.get("team_ids") or []))
    for t in active_tasks_raw:
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
    team_members = []
    total_assigned_hours = 0.0
    total_capacity = 0.0

    for emp in employees_raw:
        eid_str = str(emp["_id"])
        emp_tasks = [t for t in active_tasks if t["assignee_id"] == eid_str]
        assigned_h = sum(t["estimated_hours"] for t in emp_tasks)
        cap = float(emp.get("weekly_capacity_hours", 40) or 40)
        workload = (assigned_h / cap * 100) if cap > 0 else 0
        total_assigned_hours += assigned_h
        total_capacity += cap

        team_members.append({
            "id": eid_str,
            "name": emp.get("name", "Team Member"),
            "role": emp.get("role", "Engineer"),
            "specialization": emp.get("specialization", ""),
            "skills": emp.get("skills", []),
            "weekly_capacity": cap,
            "assigned_hours": assigned_h,
            "workload_ratio": round(workload, 1),
            "is_overloaded": workload > 100,
        })

    current_workload_pct = (total_assigned_hours / total_capacity * 100) if total_capacity > 0 else 50.0

    # Fetch latest prediction for health score
    pred = await db.project_predictions.find_one({"project_id": project_id})
    current_health_score = float(pred.get("health_score", 75.0)) if pred else 75.0

    # Fetch detected gaps and cross-PM candidates
    from app.services.resource_optimizer import detect_project_skill_gaps, discover_cross_pm_resources
    detected_gaps = await detect_project_skill_gaps(project, active_tasks_raw, team_members)
    project_pm_id = str(project.get("manager_id") or project.get("project_manager_id") or project.get("created_by") or "")
    available_candidates = await discover_cross_pm_resources(db, project_id, project_name, project_pm_id, detected_gaps)

    return SimulationProjectOptions(
        project_id=project_id,
        project_name=project_name,
        current_team_size=len(team_members),
        current_workload_pct=round(current_workload_pct, 1),
        current_health_score=round(current_health_score, 1),
        team_members=team_members,
        active_tasks=active_tasks,
        detected_gaps=detected_gaps,
        available_candidates=available_candidates,
    )


async def run_what_if_simulation(
    request: SimulationRequest,
    db,
    current_user: Optional[Dict[str, Any]] = None,
) -> SimulationResult:
    """
    Executes a What-If scenario analysis in-memory on a read-only snapshot.
    Guarantees ZERO modification of operational MongoDB collections.
    """
    project_id = request.project_id
    scenario_type = request.scenario_type
    params = request.parameters or {}

    # 1. READ-ONLY SNAPSHOT OF LIVE PROJECT DATA
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id)})
    except Exception:
        project = None

    if not project:
        raise ValueError("Project not found")

    project_name = project.get("name", "Project")
    budget = float(project.get("budget", 0) or 0)
    current_expenditure = float(project.get("current_expenditure", 0) or 0)
    progress = float(project.get("progress", 0) or 0)
    budget_utilization = (current_expenditure / budget * 100) if budget > 0 else 0.0

    # Tasks snapshot
    tasks_all = await db.tasks.find({"project_id": project_id}).to_list(1000)
    total_tasks = len(tasks_all)
    completed_tasks = sum(1 for t in tasks_all if t.get("status") == "done")
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    overdue_tasks = sum(
        1 for t in tasks_all
        if t.get("due_date") and t.get("status") not in ["done"] and t.get("due_date") < today_str
    )
    high_priority_tasks = sum(1 for t in tasks_all if t.get("priority") in ["high", "critical"])
    task_completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0.0
    remaining_work = 100.0 - progress

    # Issues snapshot
    issues = await db.issues.find({"project_id": project_id}).to_list(500)
    total_bugs = len(issues)
    critical_issues = sum(1 for i in issues if i.get("severity") == "critical" and i.get("status") not in ["resolved", "closed"])
    open_issues = sum(1 for i in issues if i.get("status") not in ["resolved", "closed"])

    # Sprints snapshot
    sprints = await db.sprints.find({"project_id": project_id}).to_list(100)
    completed_sprints = [s for s in sprints if s.get("status") == "completed"]
    avg_velocity = 0.0
    if completed_sprints:
        velocities = [s.get("velocity", 0) for s in completed_sprints]
        avg_velocity = sum(velocities) / len(velocities) if velocities else 0.0

    # Team & Workload snapshot
    team_member_ids = [str(x) for x in project.get("team_member_ids", [])]
    team_obj_ids = [ObjectId(x) for x in team_member_ids if ObjectId.is_valid(x)]
    employees_raw = await db.employees.find({"_id": {"$in": team_obj_ids}}).to_list(100) if team_obj_ids else []

    active_tasks = [t for t in tasks_all if t.get("status") not in ["done"]]
    employee_loads = []
    total_assigned_hours = 0.0
    total_capacity_hours = 0.0

    for emp in employees_raw:
        eid_str = str(emp["_id"])
        emp_tasks = [t for t in active_tasks if str(t.get("assignee_id", "")) == eid_str]
        assigned_h = sum(float(t.get("estimated_hours", 0) or 0) for t in emp_tasks)
        cap = float(emp.get("weekly_capacity_hours", 40) or 40)
        w_ratio = (assigned_h / cap * 100) if cap > 0 else 0.0
        total_assigned_hours += assigned_h
        total_capacity_hours += cap
        employee_loads.append({
            "employee_id": eid_str,
            "name": emp.get("name", "Team Member"),
            "role": emp.get("role", "Engineer"),
            "specialization": emp.get("specialization", ""),
            "weekly_capacity": cap,
            "assigned_hours": assigned_h,
            "workload_ratio": round(w_ratio, 1),
            "is_overloaded": w_ratio > 100.0,
        })

    team_workload_pct = (total_assigned_hours / total_capacity_hours * 100) if total_capacity_hours > 0 else 50.0

    # 2. BASELINE FEATURES & INFERENCE
    baseline_features = {
        "progress": float(progress),
        "task_completion_rate": float(task_completion_rate),
        "overdue_tasks": int(overdue_tasks),
        "avg_sprint_velocity": float(avg_velocity),
        "total_bugs": int(total_bugs),
        "critical_issues": int(critical_issues),
        "open_issues": int(open_issues),
        "team_workload": float(team_workload_pct),
        "budget_utilization": float(budget_utilization),
        "remaining_work": float(remaining_work),
        "high_priority_tasks": int(high_priority_tasks),
        "total_tasks": int(total_tasks),
        "team_size": len(team_member_ids),
    }

    base_risk = predict_project_risk_inference(baseline_features)
    base_delay = predict_deadline_delay(baseline_features, project)
    base_budget = predict_budget_overrun(baseline_features, project)
    base_health = calculate_project_health(baseline_features, project, base_risk, base_delay, base_budget)

    # Baseline recommendations
    base_recommendations = _evaluate_recommendations_for_features(
        project_id, project_name, baseline_features, base_risk, base_delay, base_budget, base_health, employee_loads
    )

    baseline_snapshot = SimulationStateSnapshot(
        team_size=len(team_member_ids),
        team_workload_pct=round(team_workload_pct, 1),
        total_capacity_hours=round(total_capacity_hours, 1),
        total_assigned_hours=round(total_assigned_hours, 1),
        total_tasks=total_tasks,
        remaining_tasks=len(active_tasks),
        overdue_tasks=overdue_tasks,
        critical_issues=critical_issues,
        open_issues=open_issues,
        progress=round(progress, 1),
        budget=round(budget, 2),
        current_expenditure=round(current_expenditure, 2),
        budget_utilization_pct=round(budget_utilization, 1),
        risk_class=base_risk["risk_class"],
        risk_probability=base_risk["risk_probability"],
        delay_days=base_delay["delay_days"],
        raw_delay_days=base_delay.get("raw_delay_days"),
        delay_probability=base_delay["delay_probability"],
        health_score=base_health["health_score"],
        health_status=base_health["health_status"],
        budget_overrun_amount=base_budget["overrun_amount"],
        budget_overrun_risk=base_budget.get("overrun_risk", "LOW"),
        recommendations=base_recommendations,
        employee_loads=employee_loads,
    )

    # 3. BUILD IN-MEMORY SIMULATED STATE BASED ON SCENARIO
    sim_features = dict(baseline_features)
    sim_project = dict(project)
    sim_employee_loads = [dict(e) for e in employee_loads]
    sim_team_size = len(team_member_ids)
    sim_total_capacity = total_capacity_hours
    sim_total_assigned = total_assigned_hours
    sim_total_tasks = total_tasks
    sim_remaining_tasks = len(active_tasks)
    sim_overdue_tasks = overdue_tasks
    sim_progress = progress
    sim_completion_rate = task_completion_rate
    sim_remaining_work = remaining_work
    sim_expenditure = current_expenditure
    sim_budget = budget

    # Compute lifecycle runway ratio from project schedule dates
    total_days, days_remaining, sched_prog = _parse_dates(project)
    runway_ratio = (days_remaining / total_days) if total_days > 0 else 0.5

    scenario_title = ""
    scenario_desc = ""
    what_changed_narrative = ""
    why_changed_narrative = ""
    warnings = []
    limitations = []

    if scenario_type == ScenarioType.RESOURCE_ADD:
        count = int(params.get("count", 1) or 1)
        role = params.get("role", "Engineer")
        weekly_h = float(params.get("weekly_capacity_hours", 40.0) or 40.0)
        cost_rate = float(params.get("hourly_rate", 65.0) or 65.0)

        added_capacity = count * weekly_h
        sim_team_size += count
        sim_total_capacity += added_capacity

        # Workload decreases as capacity increases
        sim_team_workload = (sim_total_assigned / sim_total_capacity * 100) if sim_total_capacity > 0 else 50.0
        sim_features["team_workload"] = float(sim_team_workload)
        sim_features["team_size"] = int(sim_team_size)

        # Added resource capacity helps resolve overdue tasks & accelerates remaining delivery if lagging
        if sim_overdue_tasks > 0:
            sim_overdue_tasks = max(0, sim_overdue_tasks - count)
            sim_features["overdue_tasks"] = int(sim_overdue_tasks)

        # Data-grounded throughput acceleration: scaled by added capacity share and remaining lifecycle runway
        if remaining_work > 0:
            cap_ratio = added_capacity / sim_total_capacity if sim_total_capacity > 0 else 0.0
            capacity_progress_boost = remaining_work * cap_ratio * runway_ratio
            sim_progress = min(100.0, progress + capacity_progress_boost)
            sim_completion_rate = min(100.0, task_completion_rate + capacity_progress_boost)
            sim_remaining_work = max(0.0, 100.0 - sim_progress)
            sim_features["progress"] = float(sim_progress)
            sim_features["task_completion_rate"] = float(sim_completion_rate)
            sim_features["remaining_work"] = float(sim_remaining_work)

        # Added resource adds to synthetic load snapshot
        for i in range(count):
            sim_employee_loads.append({
                "employee_id": f"sim_added_{i+1}",
                "name": f"Hypothetical {role} #{i+1}",
                "role": role,
                "specialization": role,
                "weekly_capacity": weekly_h,
                "assigned_hours": 0.0,
                "workload_ratio": 0.0,
                "is_overloaded": False,
            })

        # Cost impact (assumes ~8 weeks remaining runway)
        est_runway_weeks = max(4.0, (100.0 - progress) / 10.0 * 2.0)
        sim_additional_cost = count * weekly_h * est_runway_weeks * cost_rate
        sim_expenditure += sim_additional_cost
        sim_util = (sim_expenditure / sim_budget * 100) if sim_budget > 0 else 0.0
        sim_features["budget_utilization"] = float(sim_util)

        scenario_title = f"Add {count} {role}(s)"
        scenario_desc = f"Simulating addition of {count} {role}(s) providing +{added_capacity:.0f}h/week capacity."
        what_changed_narrative = f"Added {count} {role}(s), expanding total weekly capacity from {total_capacity_hours:.0f}h to {sim_total_capacity:.0f}h (+{added_capacity:.0f}h/wk)."
        why_changed_narrative = f"Workload concentration decreases from {team_workload_pct:.0f}% to {sim_team_workload:.0f}%. Additional delivery throughput relieves schedule compression."

    elif scenario_type == ScenarioType.RESOURCE_REMOVE:
        count = int(params.get("count", 1) or 1)
        target_emp_id = params.get("employee_id")
        emp_to_remove = next((e for e in sim_employee_loads if e["employee_id"] == target_emp_id), None)
        removed_name = emp_to_remove["name"] if emp_to_remove else f"{count} Engineer(s)"
        removed_cap = emp_to_remove["weekly_capacity"] if emp_to_remove else (count * 40.0)

        sim_team_size = max(1, sim_team_size - count)
        sim_total_capacity = max(1.0, sim_total_capacity - removed_cap)

        if emp_to_remove:
            sim_employee_loads = [e for e in sim_employee_loads if e["employee_id"] != target_emp_id]

        sim_team_workload = (sim_total_assigned / sim_total_capacity * 100) if sim_total_capacity > 0 else 150.0
        sim_features["team_workload"] = float(sim_team_workload)
        sim_features["team_size"] = int(sim_team_size)

        # If team becomes overloaded, backlog pressure increases overdue tasks
        if sim_team_workload > 100.0:
            sim_overdue_tasks = min(sim_total_tasks, overdue_tasks + count)
            sim_features["overdue_tasks"] = int(sim_overdue_tasks)

        scenario_title = f"Remove {removed_name}"
        scenario_desc = f"Simulating removal of {removed_name} (-{removed_cap:.0f}h/week capacity)."
        what_changed_narrative = f"Removed {removed_name}, reducing weekly capacity from {total_capacity_hours:.0f}h to {sim_total_capacity:.0f}h."
        why_changed_narrative = f"Remaining tasks must be absorbed by fewer team members, raising average workload to {sim_team_workload:.0f}%."

        if sim_team_workload > 110:
            warnings.append(f"Team becomes significantly overloaded ({sim_team_workload:.0f}% utilization). Delivery delay and burnout risk escalate.")

    elif scenario_type == ScenarioType.RESOURCE_REALLOCATION:
        cand_name = params.get("candidate_name", "Cross-PM Specialist")
        cand_role = params.get("candidate_role", "Senior Specialist")
        cand_cap = float(params.get("weekly_capacity_hours", 40.0) or 40.0)

        sim_team_size += 1
        sim_total_capacity += cand_cap
        sim_team_workload = (sim_total_assigned / sim_total_capacity * 100) if sim_total_capacity > 0 else 50.0
        sim_features["team_workload"] = float(sim_team_workload)
        sim_features["team_size"] = int(sim_team_size)

        if sim_overdue_tasks > 0:
            sim_overdue_tasks = max(0, sim_overdue_tasks - 1)
            sim_features["overdue_tasks"] = int(sim_overdue_tasks)

        if remaining_work > 0:
            cap_ratio = cand_cap / sim_total_capacity if sim_total_capacity > 0 else 0.0
            capacity_progress_boost = remaining_work * cap_ratio * runway_ratio
            sim_progress = min(100.0, progress + capacity_progress_boost)
            sim_completion_rate = min(100.0, task_completion_rate + capacity_progress_boost)
            sim_remaining_work = max(0.0, 100.0 - sim_progress)
            sim_features["progress"] = float(sim_progress)
            sim_features["task_completion_rate"] = float(sim_completion_rate)
            sim_features["remaining_work"] = float(sim_remaining_work)

        sim_employee_loads.append({
            "employee_id": params.get("candidate_employee_id", "sim_cross_pm"),
            "name": f"{cand_name} (Simulated Borrow)",
            "role": cand_role,
            "specialization": cand_role,
            "weekly_capacity": cand_cap,
            "assigned_hours": 0.0,
            "workload_ratio": 0.0,
            "is_overloaded": False,
        })

        scenario_title = f"Borrow {cand_name} ({cand_role})"
        scenario_desc = f"Simulating allocation of {cand_name} to address project skill gap."
        what_changed_narrative = f"Temporarily integrated {cand_name} into project capacity (+{cand_cap:.0f}h/week)."
        why_changed_narrative = f"Closes project role vacancy while absorbing critical task backlog without permanently reassigning line management."

    elif scenario_type == ScenarioType.TASK_REALLOCATION:
        task_id = params.get("task_id")
        task_hours = float(params.get("task_hours", 16.0) or 16.0)
        from_id = params.get("from_employee_id")
        to_id = params.get("to_employee_id")

        from_emp = next((e for e in sim_employee_loads if e["employee_id"] == from_id), None)
        to_emp = next((e for e in sim_employee_loads if e["employee_id"] == to_id), None)

        from_name = from_emp["name"] if from_emp else "Overloaded Engineer"
        to_name = to_emp["name"] if to_emp else "Available Engineer"

        if from_emp:
            from_emp["assigned_hours"] = max(0.0, from_emp["assigned_hours"] - task_hours)
            from_emp["workload_ratio"] = round((from_emp["assigned_hours"] / max(1.0, from_emp["weekly_capacity"])) * 100, 1)
            from_emp["is_overloaded"] = from_emp["workload_ratio"] > 100.0

        if to_emp:
            to_emp["assigned_hours"] += task_hours
            to_emp["workload_ratio"] = round((to_emp["assigned_hours"] / max(1.0, to_emp["weekly_capacity"])) * 100, 1)
            to_emp["is_overloaded"] = to_emp["workload_ratio"] > 100.0

        scenario_title = f"Move {task_hours:.0f}h from {from_name} to {to_name}"
        scenario_desc = f"Simulating task handover of {task_hours:.0f}h from {from_name} to {to_name}."
        what_changed_narrative = f"Reallocated {task_hours:.0f}h task workload from {from_name} to {to_name}."
        why_changed_narrative = f"{from_name}'s workload reduced to {from_emp['workload_ratio'] if from_emp else 80}%, alleviating individual burnout bottleneck."

    elif scenario_type == ScenarioType.SCOPE_REDUCTION:
        selected_task_ids = params.get("task_ids", [])
        descope_count = int(params.get("count", len(selected_task_ids) or 3))
        hours_reduced = float(params.get("hours_reduced", descope_count * 12.0))

        sim_total_tasks = max(1, sim_total_tasks - descope_count)
        sim_remaining_tasks = max(0, sim_remaining_tasks - descope_count)
        sim_overdue_tasks = max(0, sim_overdue_tasks - min(descope_count, sim_overdue_tasks))
        sim_total_assigned = max(0.0, sim_total_assigned - hours_reduced)

        # Completion rate increases
        sim_completion_rate = (completed_tasks / max(1, sim_total_tasks)) * 100
        sim_progress = min(100.0, progress + (descope_count * 2.5))
        sim_remaining_work = max(0.0, 100.0 - sim_progress)

        sim_team_workload = (sim_total_assigned / sim_total_capacity * 100) if sim_total_capacity > 0 else 50.0
        sim_features["task_completion_rate"] = float(sim_completion_rate)
        sim_features["progress"] = float(sim_progress)
        sim_features["remaining_work"] = float(sim_remaining_work)
        sim_features["overdue_tasks"] = int(sim_overdue_tasks)
        sim_features["total_tasks"] = int(sim_total_tasks)
        sim_features["team_workload"] = float(sim_team_workload)

        scenario_title = f"Descope {descope_count} Low-Priority Tasks"
        scenario_desc = f"Simulating removal of {descope_count} non-critical tasks (-{hours_reduced:.0f}h backlog)."
        what_changed_narrative = f"Descoped {descope_count} tasks, reducing remaining effort by {hours_reduced:.0f}h and lowering overdue task count to {sim_overdue_tasks}."
        why_changed_narrative = f"Compresses scope boundaries to protect commit deadline, lifting task completion rate from {task_completion_rate:.0f}% to {sim_completion_rate:.0f}%."

    elif scenario_type == ScenarioType.SCHEDULE_CAPACITY_CHANGE:
        velocity_boost = float(params.get("velocity_boost_pct", 20.0) or 20.0)
        sim_velocity = avg_velocity * (1.0 + (velocity_boost / 100.0))
        sim_features["avg_sprint_velocity"] = float(sim_velocity)

        # Velocity acceleration compresses remaining backlog burn-down scaled by remaining runway
        progress_gain = remaining_work * (velocity_boost / 100.0) * runway_ratio
        sim_progress = min(100.0, progress + progress_gain)
        sim_completion_rate = min(100.0, task_completion_rate + progress_gain)
        sim_remaining_work = max(0.0, 100.0 - sim_progress)
        sim_features["progress"] = float(sim_progress)
        sim_features["task_completion_rate"] = float(sim_completion_rate)
        sim_features["remaining_work"] = float(sim_remaining_work)

        if sim_overdue_tasks > 0 and velocity_boost >= 15.0:
            sim_overdue_tasks = max(0, sim_overdue_tasks - 1)
            sim_features["overdue_tasks"] = int(sim_overdue_tasks)

        scenario_title = f"Increase Sprint Velocity by {velocity_boost:.0f}%"
        scenario_desc = f"Simulating velocity boost from {avg_velocity:.1f} to {sim_velocity:.1f} story points."
        what_changed_narrative = f"Projected sprint velocity increases by {velocity_boost:.0f}% ({sim_velocity:.1f} pts/sprint)."
        why_changed_narrative = f"Higher team throughput compresses backlog burn-down cycle."

    elif scenario_type == ScenarioType.BUDGET_RESOURCE_CHANGE:
        budget_increase = float(params.get("budget_change_amount", 50000.0) or 50000.0)
        sim_budget += budget_increase
        sim_util = (sim_expenditure / sim_budget * 100) if sim_budget > 0 else 0.0
        sim_features["budget_utilization"] = float(sim_util)
        sim_project["budget"] = sim_budget

        scenario_title = f"Adjust Project Budget by ${budget_increase:+,.0f}"
        scenario_desc = f"Simulating budget expansion from ${budget:,.0f} to ${sim_budget:,.0f}."
        what_changed_narrative = f"Adjusted total budget runway by ${budget_increase:+,.0f}."
        why_changed_narrative = f"Budget utilization drops from {budget_utilization:.0f}% to {sim_util:.0f}%, absorbing cost overruns."

    else:
        scenario_title = "Custom Scenario"
        scenario_desc = "Custom simulated parameters applied."
        what_changed_narrative = "Custom parameter modification."
        why_changed_narrative = "Adjusted simulation inputs."

    # 4. RE-RUN REAL ML INFERENCE ON SIMULATED FEATURES
    sim_risk = predict_project_risk_inference(sim_features)
    sim_delay = predict_deadline_delay(sim_features, sim_project)
    sim_budget_res = predict_budget_overrun(sim_features, sim_project)
    sim_health = calculate_project_health(sim_features, sim_project, sim_risk, sim_delay, sim_budget_res)

    # Re-evaluate simulated recommendations
    sim_recommendations = _evaluate_recommendations_for_features(
        project_id, project_name, sim_features, sim_risk, sim_delay, sim_budget_res, sim_health, sim_employee_loads
    )

    simulated_snapshot = SimulationStateSnapshot(
        team_size=sim_team_size,
        team_workload_pct=round(sim_features["team_workload"], 1),
        total_capacity_hours=round(sim_total_capacity, 1),
        total_assigned_hours=round(sim_total_assigned, 1),
        total_tasks=sim_total_tasks,
        remaining_tasks=sim_remaining_tasks,
        overdue_tasks=sim_overdue_tasks,
        critical_issues=critical_issues,
        open_issues=open_issues,
        progress=round(sim_progress, 1),
        budget=round(sim_budget, 2),
        current_expenditure=round(sim_expenditure, 2),
        budget_utilization_pct=round(sim_features.get("budget_utilization", budget_utilization), 1),
        risk_class=sim_risk["risk_class"],
        risk_probability=sim_risk["risk_probability"],
        delay_days=sim_delay["delay_days"],
        raw_delay_days=sim_delay.get("raw_delay_days"),
        delay_probability=sim_delay["delay_probability"],
        health_score=sim_health["health_score"],
        health_status=sim_health["health_status"],
        budget_overrun_amount=sim_budget_res["overrun_amount"],
        budget_overrun_risk=sim_budget_res.get("overrun_risk", "LOW"),
        recommendations=sim_recommendations,
        employee_loads=sim_employee_loads,
    )

    # 5. COMPARISON DELTAS & SENTIMENT
    comparison_metrics = [
        SimulationComparisonMetric(
            metric_key="team_size",
            label="Team Size",
            baseline_value=baseline_snapshot.team_size,
            simulated_value=simulated_snapshot.team_size,
            delta=simulated_snapshot.team_size - baseline_snapshot.team_size,
            unit="members",
            sentiment="positive" if simulated_snapshot.team_size >= baseline_snapshot.team_size else "warning",
            description="Number of engineers assigned to project"
        ),
        SimulationComparisonMetric(
            metric_key="team_workload_pct",
            label="Team Workload",
            baseline_value=baseline_snapshot.team_workload_pct,
            simulated_value=simulated_snapshot.team_workload_pct,
            delta=round(simulated_snapshot.team_workload_pct - baseline_snapshot.team_workload_pct, 1),
            unit="%",
            sentiment="positive" if simulated_snapshot.team_workload_pct <= 95.0 else ("warning" if simulated_snapshot.team_workload_pct > 110.0 else "neutral"),
            description="Average capacity utilization across active team"
        ),
        SimulationComparisonMetric(
            metric_key="health_score",
            label="Project Health Score",
            baseline_value=baseline_snapshot.health_score,
            simulated_value=simulated_snapshot.health_score,
            delta=round(simulated_snapshot.health_score - baseline_snapshot.health_score, 1),
            unit="/100",
            sentiment="positive" if simulated_snapshot.health_score >= baseline_snapshot.health_score else "negative",
            description="Composite health indicator"
        ),
        SimulationComparisonMetric(
            metric_key="delay_days",
            label="Predicted Schedule Delay",
            baseline_value=baseline_snapshot.delay_days,
            simulated_value=simulated_snapshot.delay_days,
            delta=simulated_snapshot.delay_days - baseline_snapshot.delay_days,
            unit="days",
            sentiment="positive" if simulated_snapshot.delay_days < baseline_snapshot.delay_days else ("neutral" if simulated_snapshot.delay_days == baseline_snapshot.delay_days else "negative"),
            description="ML forecasted delivery slippage"
        ),
        SimulationComparisonMetric(
            metric_key="risk_class",
            label="ML Risk Classification",
            baseline_value=baseline_snapshot.risk_class,
            simulated_value=simulated_snapshot.risk_class,
            delta=f"{baseline_snapshot.risk_class} → {simulated_snapshot.risk_class}",
            unit="",
            sentiment="positive" if (baseline_snapshot.risk_class == "HIGH" and simulated_snapshot.risk_class != "HIGH") else ("negative" if (baseline_snapshot.risk_class != "HIGH" and simulated_snapshot.risk_class == "HIGH") else "neutral"),
            description="RandomForest model risk tier"
        ),
        SimulationComparisonMetric(
            metric_key="budget_overrun_amount",
            label="Projected Cost Overrun",
            baseline_value=baseline_snapshot.budget_overrun_amount,
            simulated_value=simulated_snapshot.budget_overrun_amount,
            delta=round(simulated_snapshot.budget_overrun_amount - baseline_snapshot.budget_overrun_amount, 2),
            unit="$",
            sentiment="positive" if simulated_snapshot.budget_overrun_amount <= baseline_snapshot.budget_overrun_amount else "negative",
            description="GradientBoosting budget overrun estimate"
        ),
    ]

    # 6. EXPLANATION GENERATION
    what_improved = []
    what_worsened = []
    remaining_risks = []
    resolved_recs = []

    if simulated_snapshot.health_score > baseline_snapshot.health_score:
        what_improved.append(f"Project health score improves by +{round(simulated_snapshot.health_score - baseline_snapshot.health_score, 1)} pts ({baseline_snapshot.health_score} → {simulated_snapshot.health_score}).")
    elif simulated_snapshot.health_score < baseline_snapshot.health_score:
        what_worsened.append(f"Project health score decreases by {round(simulated_snapshot.health_score - baseline_snapshot.health_score, 1)} pts.")

    if simulated_snapshot.delay_days < baseline_snapshot.delay_days:
        what_improved.append(f"Predicted schedule delay reduced by {baseline_snapshot.delay_days - simulated_snapshot.delay_days} day(s) ({baseline_snapshot.delay_days}d → {simulated_snapshot.delay_days}d).")
    elif simulated_snapshot.delay_days > baseline_snapshot.delay_days:
        what_worsened.append(f"Predicted schedule delay increases by {simulated_snapshot.delay_days - baseline_snapshot.delay_days} day(s).")

    if simulated_snapshot.team_workload_pct < baseline_snapshot.team_workload_pct:
        what_improved.append(f"Team workload reduces from {baseline_snapshot.team_workload_pct:.0f}% to {simulated_snapshot.team_workload_pct:.0f}%, mitigating burnout risk.")
    elif simulated_snapshot.team_workload_pct > baseline_snapshot.team_workload_pct:
        what_worsened.append(f"Team workload increases from {baseline_snapshot.team_workload_pct:.0f}% to {simulated_snapshot.team_workload_pct:.0f}%.")

    if simulated_snapshot.overdue_tasks < baseline_snapshot.overdue_tasks:
        what_improved.append(f"Overdue tasks reduced from {baseline_snapshot.overdue_tasks} to {simulated_snapshot.overdue_tasks}.")

    # Identify resolved recommendations
    base_rec_titles = set(r.get("title", "") for r in base_recommendations)
    sim_rec_titles = set(r.get("title", "") for r in sim_recommendations)
    for title in base_rec_titles:
        if title not in sim_rec_titles:
            resolved_recs.append(title)

    if critical_issues > 0:
        remaining_risks.append(f"Project still retains {critical_issues} unresolved critical defect(s).")
    if simulated_snapshot.budget_utilization_pct > 85.0:
        remaining_risks.append(f"Budget utilization remains elevated at {simulated_snapshot.budget_utilization_pct:.0f}%.")
    if simulated_snapshot.team_workload_pct > 100.0:
        remaining_risks.append(f"Team workload remains above 100% capacity ({simulated_snapshot.team_workload_pct:.0f}%).")

    explanation = SimulationExplanation(
        what_changed=what_changed_narrative,
        why_it_changed=why_changed_narrative,
        what_improved=what_improved or ["Simulation parameters applied without negative health impact."],
        what_worsened=what_worsened or ["No negative metric regressions observed."],
        remaining_risks=remaining_risks or ["All primary risk indicators within safe operating thresholds."],
        recommendations_resolved=resolved_recs,
    )

    simulation_id = f"sim_{uuid.uuid4().hex[:12]}"

    return SimulationResult(
        simulation_id=simulation_id,
        project_id=project_id,
        project_name=project_name,
        scenario_type=scenario_type,
        scenario_title=scenario_title,
        scenario_description=scenario_desc,
        parameters_applied=params,
        simulated_at=datetime.now(timezone.utc),
        baseline=baseline_snapshot,
        simulated=simulated_snapshot,
        comparison=comparison_metrics,
        explanation=explanation,
        warnings=warnings,
        limitations=limitations,
        is_live_mutation=False,
    )


def _evaluate_recommendations_for_features(
    project_id: str,
    project_name: str,
    features: Dict[str, Any],
    risk: Dict[str, Any],
    delay: Dict[str, Any],
    budget: Dict[str, Any],
    health: Dict[str, Any],
    employee_loads: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Evaluates explainable recommendation rules on a feature snapshot."""
    recs = []
    risk_class = risk.get("risk_class", "LOW")
    health_score = health.get("health_score", 85.0)
    delay_days = delay.get("delay_days", 0)
    workload = features.get("team_workload", 50.0)
    overdue_tasks = features.get("overdue_tasks", 0)
    critical_issues = features.get("critical_issues", 0)

    if risk_class == "HIGH" or health_score < 60:
        recs.append({
            "title": "Prioritize Overdue Critical Tasks & Risk Mitigation",
            "category": "Risk Management",
            "priority": "critical",
            "reason": f"High risk tier ({risk_class}) with health score {health_score:.0f}/100.",
        })

    if workload > 100:
        recs.append({
            "title": "Rebalance Team Workload to Prevent Burnout",
            "category": "Resource Management",
            "priority": "high",
            "reason": f"Team workload is at {workload:.0f}% capacity.",
        })

    if delay_days > 5 or overdue_tasks >= 2:
        recs.append({
            "title": "Review Sprint Scope & Delivery Schedule",
            "category": "Schedule Management",
            "priority": "high",
            "reason": f"Forecasted delay of {delay_days} days with {overdue_tasks} overdue tasks.",
        })

    if critical_issues > 0:
        recs.append({
            "title": "Prioritize Critical Defect Resolution",
            "category": "Quality Management",
            "priority": "critical",
            "reason": f"{critical_issues} open critical defect(s) threatening release quality.",
        })

    return recs
