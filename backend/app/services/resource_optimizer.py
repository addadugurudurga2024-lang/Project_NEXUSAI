"""
Resource Optimization Service for NexusAI
Constraint-based task reallocation and capacity balancing using:
- Employee skills, specialization, weekly capacity, and current workload
- Active project tasks, estimated hours, priority, and deadlines
- Authoritative resource_allocations persistence and execution workflow
"""
# pyrefly: ignore [missing-import]
from bson import ObjectId
from typing import Dict, List, Any, Optional
from datetime import datetime
from app.services.notification_service import create_notification, notify_project_stakeholders


async def compute_resource_optimization(project_id: str, db) -> Dict[str, Any]:
    """
    Computes explainable, skill-matched task reallocation suggestions for a project.
    Persists suggestions into the authoritative `resource_allocations` collection.
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
            "summary": {
                "total_employees": 0,
                "overloaded_count": 0,
                "available_count": 0,
                "avg_workload_percent": 0,
                "suggestions_count": 0,
            },
            "message": "Project not found",
            "computed_at": datetime.utcnow().isoformat(),
        }

    project_name = project.get("name", "Project")

    # 1. Fetch active tasks for this project
    tasks = await db.tasks.find({
        "project_id": project_id,
        "status": {"$nin": ["done"]},
    }).to_list(500)

    # 2. Fetch all active employees
    employees_raw = await db.employees.find({"status": "active"}).to_list(200)

    # 3. Calculate global workload across all projects for each employee
    employee_map = {}
    for emp in employees_raw:
        emp_id = str(emp["_id"])
        # Find all active tasks assigned across all projects to measure total real load
        all_emp_tasks = await db.tasks.find({
            "assignee_id": emp_id,
            "status": {"$nin": ["done"]},
        }).to_list(500)

        assigned_hours = sum(float(t.get("estimated_hours", 0) or 0) for t in all_emp_tasks)
        capacity = float(emp.get("weekly_capacity_hours", 40) or 40)
        workload_ratio = (assigned_hours / capacity * 100) if capacity > 0 else 0
        available_hours = max(0.0, capacity - assigned_hours)

        # Check burnout risk prediction
        burnout_pred = await db.employee_risk_predictions.find_one({"employee_id": emp_id})
        burnout_risk = burnout_pred.get("risk_level", "LOW") if burnout_pred else ("HIGH" if workload_ratio > 110 else "LOW")

        employee_map[emp_id] = {
            "employee_id": emp_id,
            "id": emp_id,
            "name": emp.get("name", "Employee"),
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
                    "project_id": t.get("project_id"),
                }
                for t in all_emp_tasks if t.get("project_id") == project_id
            ]
        }

    # 4. Identify Overloaded and Available Employees
    overloaded = [e for e in employee_map.values() if e["is_overloaded"]]
    available = [e for e in employee_map.values() if e["is_available"]]

    overloaded.sort(key=lambda x: x["workload_ratio"], reverse=True)
    available.sort(key=lambda x: x["workload_ratio"])

    # 5. Generate Constraint-Based Reallocation Suggestions
    reallocation_suggestions = []
    persisted_allocations = []

    for over_emp in overloaded:
        # Get assignable tasks belonging to this project for the overloaded employee
        assignable_tasks = [
            t for t in tasks
            if t.get("assignee_id") == over_emp["employee_id"]
            and t.get("priority") not in ["critical"]  # Avoid moving critical path unless essential
        ]
        if not assignable_tasks:
            # Fallback to any active non-done task
            assignable_tasks = [t for t in tasks if t.get("assignee_id") == over_emp["employee_id"]]

        # Sort tasks by estimated hours descending (aim for impactful rebalance)
        assignable_tasks.sort(key=lambda t: float(t.get("estimated_hours", 0) or 0), reverse=True)

        for task in assignable_tasks:
            task_id_str = str(task["_id"])
            task_title = task.get("title", "Task")
            task_hours = float(task.get("estimated_hours", 0) or 0)
            if task_hours <= 0:
                task_hours = 4.0  # Default nominal hours if unspecified

            task_labels = task.get("labels", []) or []

            # Find suitable available candidate
            best_candidate = None
            best_score = -1

            for avail_emp in available:
                if avail_emp["employee_id"] == over_emp["employee_id"]:
                    continue

                # Ensure candidate has capacity for this task without becoming overloaded
                new_avail_hours = avail_emp["assigned_hours"] + task_hours
                new_avail_ratio = (new_avail_hours / avail_emp["weekly_capacity"] * 100)
                if new_avail_ratio > 95:
                    continue  # Would overload recipient

                # Calculate skill matching score
                avail_skills = set(s.lower() for s in avail_emp["skills"])
                over_skills = set(s.lower() for s in over_emp["skills"])
                label_skills = set(s.lower() for s in task_labels)

                skill_overlap = len(avail_skills & label_skills) if label_skills else len(avail_skills & over_skills)
                spec_match = 2 if (
                    avail_emp.get("specialization") and over_emp.get("specialization") and
                    avail_emp["specialization"].lower() == over_emp["specialization"].lower()
                ) else 0

                # Score combines skill overlap, role match, and available headroom
                score = (skill_overlap * 3) + spec_match + ((80 - avail_emp["workload_ratio"]) / 10)

                if score > best_score:
                    best_score = score
                    best_candidate = avail_emp

            if best_candidate:
                # Compute before & after metrics
                current_from_hours = over_emp["assigned_hours"]
                new_from_hours = max(0.0, current_from_hours - task_hours)
                new_from_ratio = (new_from_hours / over_emp["weekly_capacity"] * 100)

                current_to_hours = best_candidate["assigned_hours"]
                new_to_hours = current_to_hours + task_hours
                new_to_ratio = (new_to_hours / best_candidate["weekly_capacity"] * 100)

                reason_text = (
                    f"{over_emp['name']} is allocated {over_emp['workload_ratio']:.0f}% of capacity ({over_emp['assigned_hours']:.1f}h / {over_emp['weekly_capacity']:.1f}h). "
                    f"{best_candidate['name']} has {best_candidate['available_hours']:.1f}h available bandwidth with matching competencies ({best_candidate['specialization']})."
                )

                impact_text = (
                    f"Reduces {over_emp['name']}'s workload from {over_emp['workload_ratio']:.0f}% ({current_from_hours:.1f}h) to {new_from_ratio:.0f}% ({new_from_hours:.1f}h). "
                    f"Optimizes {best_candidate['name']}'s capacity from {best_candidate['workload_ratio']:.0f}% to {new_to_ratio:.0f}%."
                )

                suggestion_id = str(ObjectId())

                # Authoritative schema document
                alloc_doc = {
                    "_id": ObjectId(suggestion_id),
                    "projectId": project_id,
                    "taskId": task_id_str,
                    "employeeId": best_candidate["employee_id"],  # recipient
                    "fromEmployeeId": over_emp["employee_id"],
                    "currentAllocationHours": current_from_hours,
                    "recommendedAllocationHours": new_from_hours,
                    "allocationChange": -task_hours,
                    "reason": reason_text,
                    "expectedImpact": impact_text,
                    "status": "suggested",
                    "createdAt": datetime.utcnow(),
                    # Compatibility fields
                    "project_id": project_id,
                    "project_name": project_name,
                    "task_id": task_id_str,
                    "task_title": task_title,
                    "task_hours": task_hours,
                    "task_priority": task.get("priority", "medium"),
                    "employee_id": best_candidate["employee_id"],
                    "employee_name": best_candidate["name"],
                    "from_employee_id": over_emp["employee_id"],
                    "from_employee_name": over_emp["name"],
                    "to_employee": {
                        "id": best_candidate["employee_id"],
                        "name": best_candidate["name"],
                        "current_workload": best_candidate["workload_ratio"],
                        "projected_workload": round(new_to_ratio, 1),
                        "current_hours": current_to_hours,
                        "projected_hours": round(new_to_hours, 1),
                    },
                    "from_employee": {
                        "id": over_emp["employee_id"],
                        "name": over_emp["name"],
                        "current_workload": over_emp["workload_ratio"],
                        "projected_workload": round(new_from_ratio, 1),
                        "current_hours": current_from_hours,
                        "projected_hours": round(new_from_hours, 1),
                    },
                    "skill_match": best_score >= 2,
                }

                persisted_allocations.append(alloc_doc)

                suggestion_item = dict(alloc_doc)
                suggestion_item["id"] = suggestion_id
                suggestion_item["_id"] = suggestion_id
                reallocation_suggestions.append(suggestion_item)

                # Update running state for this loop so subsequent tasks don't over-allocate
                over_emp["assigned_hours"] = new_from_hours
                over_emp["workload_ratio"] = new_from_ratio
                best_candidate["assigned_hours"] = new_to_hours
                best_candidate["workload_ratio"] = new_to_ratio
                best_candidate["available_hours"] = max(0.0, best_candidate["weekly_capacity"] - new_to_hours)

                if len(reallocation_suggestions) >= 5:
                    break

        if len(reallocation_suggestions) >= 5:
            break

    # 6. Persist generated suggestions into MongoDB `resource_allocations`
    # Replace pending suggested allocations for this project
    await db.resource_allocations.delete_many({
        "$or": [{"projectId": project_id}, {"project_id": project_id}],
        "status": "suggested",
    })

    if persisted_allocations:
        await db.resource_allocations.insert_many(persisted_allocations)

    total_employees = len(employee_map)
    overloaded_count = len([e for e in employee_map.values() if e["is_overloaded"]])
    available_count = len([e for e in employee_map.values() if e["is_available"]])
    avg_workload = sum(e["workload_ratio"] for e in employee_map.values()) / max(1, total_employees)

    return {
        "project_id": project_id,
        "project_name": project_name,
        "employee_workload_summary": list(employee_map.values()),
        "overloaded_employees": overloaded,
        "available_employees": available,
        "reallocation_suggestions": reallocation_suggestions,
        "summary": {
            "total_employees": total_employees,
            "overloaded_count": overloaded_count,
            "available_count": available_count,
            "avg_workload_percent": round(avg_workload, 1),
            "suggestions_count": len(reallocation_suggestions),
        },
        "has_reallocations": len(reallocation_suggestions) > 0,
        "message": (
            f"Generated {len(reallocation_suggestions)} resource reallocation suggestion(s)."
            if reallocation_suggestions
            else "No suitable resource reallocation identified based on current workload and skills."
        ),
        "computed_at": datetime.utcnow().isoformat(),
    }


async def apply_resource_reallocation(allocation_id: str, db, applied_by_user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Applies an approved resource allocation:
    - Reassigns the task in MongoDB to the recipient employee.
    - Updates `resource_allocations` document status to 'applied'.
    - Generates notifications for the assigned employee, original employee, and project manager.
    """
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

    # 1. Fetch recipient employee details
    recipient_emp = await db.employees.find_one({"_id": ObjectId(recipient_emp_id)})
    if not recipient_emp:
        raise ValueError("Recipient employee not found")
    recipient_name = recipient_emp.get("name", "Team Member")

    # 2. Update task assignment in MongoDB
    try:
        task = await db.tasks.find_one({"_id": ObjectId(task_id)})
    except Exception:
        task = None

    if not task:
        raise ValueError("Target task not found")

    task_title = task.get("title", "Task")

    await db.tasks.update_one(
        {"_id": ObjectId(task_id)},
        {
            "$set": {
                "assignee_id": recipient_emp_id,
                "assignee_name": recipient_name,
                "updated_at": datetime.utcnow(),
            }
        }
    )

    # 3. Update allocation record status
    await db.resource_allocations.update_one(
        {"_id": ObjectId(allocation_id)},
        {
            "$set": {
                "status": "applied",
                "applied_at": datetime.utcnow(),
                "applied_by": applied_by_user_id,
            }
        }
    )

    # 4. Create Notifications for recipient and former assignee
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

    if from_emp_id:
        from_emp = await db.employees.find_one({"_id": ObjectId(from_emp_id)})
        if from_emp and from_emp.get("user_id"):
            await create_notification(
                db=db,
                user_id=from_emp["user_id"],
                notification_type="task_offloaded",
                title=f"Task Reallocated: {task_title}",
                message=f"'{task_title}' has been reallocated to {recipient_name} to optimize sprint workload.",
                related_project_id=project_id,
                severity="low",
            )

    # 5. Notify Project Stakeholders
    await notify_project_stakeholders(
        db=db,
        project_id=project_id,
        notification_type="resource_optimization_applied",
        title="Resource Reallocation Applied",
        message=f"Task '{task_title}' reassigned to {recipient_name}.",
        severity="medium",
    )

    return {
        "success": True,
        "message": f"Successfully reassigned '{task_title}' to {recipient_name}",
        "allocation_id": allocation_id,
        "task_id": task_id,
        "new_assignee_id": recipient_emp_id,
        "new_assignee_name": recipient_name,
        "status": "applied",
    }
