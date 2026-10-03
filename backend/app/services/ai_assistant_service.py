"""
AI Assistant Service — Phase 8: AI Decision Assistant
Provides grounded natural language responses to user inquiries about:
- Projects, tasks, issues, sprints
- Phase 5.5 ML Predictions (Risk, Delay, Budget Overrun, Employee Burnout)
- Recommendations and Resource Optimization
- Strict RBAC: Data is scoped by user role before any AI context is assembled.
"""
# pyrefly: ignore [missing-import]
from bson import ObjectId
from datetime import datetime
from typing import Dict, Any, List, Optional
import re
# pyrefly: ignore [missing-import]
import httpx
from app.core.config import settings


def _str_id(doc: dict) -> str:
    return str(doc.get("_id", ""))


def _today_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


async def get_scoped_context(user: dict, db, project_id_hint: Optional[str] = None) -> Dict[str, Any]:
    """
    Gathers RBAC-enforced live data for the assistant.
    - admin: all projects, tasks, issues, predictions, employees
    - project_manager: managed projects, tasks, issues, team members
    - team_member: projects they are in, tasks & issues assigned to them ONLY.
    """
    role = user.get("role", "team_member")
    uid = str(user.get("_id", ""))
    today = _today_str()

    emp = await db.employees.find_one({"$or": [{"user_id": uid}, {"email": user.get("email")}]})
    emp_id = str(emp["_id"]) if emp else None
    user_identifiers = [uid] + ([emp_id] if emp_id else [])
    obj_ids = [ObjectId(x) for x in user_identifiers if ObjectId.is_valid(x)]
    all_ids = user_identifiers + obj_ids

    # 1. Authoritative Scoped Projects
    from app.services.project_scoping_service import get_authorized_projects
    projects = await get_authorized_projects(db, user)
    scoped_project_ids = [_str_id(p) for p in projects]


    # Specific project hint validation
    target_project = None
    if project_id_hint:
        for p in projects:
            if _str_id(p) == project_id_hint:
                target_project = p
                break

    # 2. Tasks
    if role in ("admin", "project_manager"):
        task_query = {"project_id": {"$in": scoped_project_ids}} if scoped_project_ids else {"_id": None}
    else:
        task_query = {"assignee_id": {"$in": user_identifiers}}
    
    tasks = await db.tasks.find(task_query).to_list(1000)

    # 3. Issues
    if role in ("admin", "project_manager"):
        issue_query = {"project_id": {"$in": scoped_project_ids}} if scoped_project_ids else {"_id": None}
    else:
        issue_query = {"assignee_id": {"$in": user_identifiers}}

    issues = await db.issues.find(issue_query).to_list(500)

    # 4. ML Project Predictions
    project_preds = []
    if scoped_project_ids:
        valid_obj_ids = [ObjectId(x) for x in scoped_project_ids if ObjectId.is_valid(x)]
        preds = await db.project_predictions.find({
            "$or": [
                {"project_id": {"$in": scoped_project_ids}},
                {"project_id": {"$in": valid_obj_ids}},
            ]
        }).to_list(500)
        project_preds = preds

    # 5. Employees & Burnout (MANAGERS / ADMIN ONLY)
    employees = []
    burnout_preds = []
    if role in ("admin", "project_manager"):
        employees = await db.employees.find({"status": "active"}).to_list(500)
        burnout_preds = await db.employee_risk_predictions.find({}).to_list(500)
    else:
        # Team member can only see their own basic employee record, NOT burnout predictions
        emp = await db.employees.find_one({"email": user.get("email")})
        if emp:
            employees = [emp]

    # 6. Recommendations
    if role in ("admin", "project_manager"):
        rec_query = {"project_id": {"$in": scoped_project_ids}} if scoped_project_ids else {"_id": None}
    else:
        rec_query = {"project_id": {"$in": scoped_project_ids}, "type": "task"}
    recommendations = await db.recommendations.find(rec_query).to_list(200)

    return {
        "role": role,
        "user_name": user.get("name", "User"),
        "user_id": uid,
        "user_identifiers": user_identifiers,
        "projects": projects,
        "target_project": target_project,
        "tasks": tasks,
        "issues": issues,
        "project_predictions": project_preds,
        "employees": employees,
        "burnout_predictions": burnout_preds,
        "recommendations": recommendations,
        "today": today,
    }


def find_matched_project(user_msg: str, projects: List[dict]) -> Optional[dict]:
    """Finds if a project is named in user prompt."""
    msg_clean = user_msg.lower()
    stopwords = {"project", "projects", "test", "audit", "alpha", "beta", "gamma", "platform", "app", "migration"}
    for p in projects:
        name = p.get("name", "").lower()
        if name and name in msg_clean:
            return p
        # Check specific distinctive name parts (skip generic words like 'project', 'test')
        parts = [part.strip() for part in re.split(r'\s+', name) if len(part) > 3 and part.lower() not in stopwords]
        for part in parts:
            if re.search(rf"\b{re.escape(part)}\b", msg_clean):
                return p
    return None


def generate_grounded_fallback_response(query: str, ctx: Dict[str, Any], matched_project: Optional[dict]) -> Dict[str, Any]:
    """
    Deterministically synthesizes a grounded answer from actual data
    following the FACT -> PREDICTION -> RECOMMENDATION structure.
    Used when no external LLM key is configured or as safe fallback.
    """
    q = query.lower()
    role = ctx["role"]
    projects = ctx["projects"]
    tasks = ctx["tasks"]
    issues = ctx["issues"]
    project_preds = {str(p.get("project_id", "")): p for p in ctx["project_predictions"]}
    burnout_preds = {str(b.get("employee_id", "")): b for b in ctx["burnout_predictions"]}
    recs = ctx["recommendations"]
    today = ctx["today"]

    # 1. Project Specific Question
    if matched_project:
        p = matched_project
        pid = _str_id(p)
        p_tasks = [t for t in tasks if t.get("project_id") == pid]
        p_issues = [i for i in issues if i.get("project_id") == pid]
        p_pred = project_preds.get(pid, {})
        p_recs = [r for r in recs if r.get("project_id") == pid]

        total_t = len(p_tasks)
        done_t = sum(1 for t in p_tasks if t.get("status") == "done")
        overdue_t = sum(1 for t in p_tasks if t.get("status") != "done" and t.get("due_date") and t["due_date"] < today)
        blocked_t = sum(1 for t in p_tasks if t.get("status") == "blocked")
        crit_issues = sum(1 for i in p_issues if i.get("severity") in ("critical", "high") and i.get("status") != "resolved")

        budget = float(p.get("budget", 0) or 0)
        spent = float(p.get("current_expenditure", 0) or 0)
        budget_pct = (spent / budget * 100) if budget > 0 else 0

        risk_class = p_pred.get("risk_class", p.get("risk_level", "LOW")).upper()
        delay_days = p_pred.get("delay_days", 0)
        overrun_amt = p_pred.get("budget_overrun_amount", 0)

        response_lines = [
            f"### Analysis for **{p.get('name')}** (Status: {p.get('status', 'active').capitalize()})",
            "",
            "**Current Facts:**",
            f"- Progress: **{p.get('progress', 0)}%** ({done_t}/{total_t} tasks completed)",
            f"- Schedule & Tasks: **{overdue_t}** overdue task(s), **{blocked_t}** blocked task(s)",
            f"- Open Critical/High Issues: **{crit_issues}**",
            f"- Financials: Budget ₹{budget:,.0f} | Spent ₹{spent:,.0f} ({budget_pct:.1f}% utilized)",
            "",
            "**ML Predictions (Phase 5.5):**",
            f"- Predicted Risk Level: **{risk_class}**",
            f"- Predicted Schedule Delay: **{delay_days} day(s)**",
            f"- Predicted Budget Overrun: **₹{overrun_amt:,.0f}**",
        ]

        if p_recs:
            response_lines.append("")
            response_lines.append("**NexusAI Recommendations:**")
            for r in p_recs[:3]:
                response_lines.append(f"- **[{r.get('priority', 'medium').upper()}]**: {r.get('title')}: {r.get('description', '')[:120]}")
        else:
            response_lines.append("")
            response_lines.append("**NexusAI Recommendations:**")
            if overdue_t > 0:
                response_lines.append("- Prioritize and reallocate resources to overdue tasks immediately.")
            if crit_issues > 0:
                response_lines.append("- Escalate open critical/high severity issues to avoid milestone slippage.")
            if risk_class in ("HIGH", "MEDIUM") and delay_days > 0:
                response_lines.append("- Consider reviewing resource allocations in the Optimization tab.")

        return {
            "response": "\n".join(response_lines),
            "intent": "project_analysis",
            "context_summary": {"project_name": p.get("name"), "risk_class": risk_class, "tasks": total_t},
            "recommendations": p_recs[:3],
        }

    # 1. Team / Workload / Overloaded / Burnout Question (Checked early so 'burnout risk' matches workload)
    if any(k in q for k in ["overload", "burnout", "workload", "capacity", "team", "employee", "who"]):
        if role == "team_member":
            # Only summarize team member's own tasks
            my_uids = set(ctx.get("user_identifiers", [ctx["user_id"]]))
            my_tasks = [t for t in tasks if t.get("assignee_id") in my_uids]
            return {
                "response": f"Access restricted. As a Team Member, you can only see your personal workload. You currently have **{len(my_tasks)} task(s)** assigned to you ({sum(1 for t in my_tasks if t.get('status') == 'in_progress')} in progress). Team-wide workload and burnout analytics are restricted to Project Managers and Administrators.",
                "intent": "workload_personal",
                "context_summary": {"personal_tasks": len(my_tasks)},
                "recommendations": [],
            }

        # For Admin/PM
        employees = ctx["employees"]
        high_burnout = []
        for e in employees:
            eid = _str_id(e)
            b = burnout_preds.get(eid, {})
            level = b.get("burnout_risk_level", "LOW")
            prob = b.get("burnout_probability", 0)
            if level in ("HIGH", "MEDIUM") or prob > 0.5:
                high_burnout.append((e.get("name", "Unknown"), level, prob, e.get("role", "Developer")))

        lines = [
            f"**Team Workload & Burnout Intelligence ({len(employees)} team members in scope):**",
            ""
        ]
        if high_burnout:
            lines.append("**Employees with Elevated Burnout Risk (ML Random Forest):**")
            for name, lvl, prob, erole in high_burnout:
                lines.append(f"- **{name}** ({erole}): Risk **{lvl}** (Score: {prob:.2f})")
            lines.append("")
            lines.append("**Recommendation:**")
            lines.append("- Utilize the **Resource Optimization** module to rebalance story points and assign critical tasks to members with spare capacity.")
        else:
            lines.append("All team members are currently operating at sustainable workload levels with Low burnout indicators.")

        return {
            "response": "\n".join(lines),
            "intent": "team_workload",
            "context_summary": {"team_size": len(employees), "elevated_risk": len(high_burnout)},
            "recommendations": [],
        }

    # 2. Risk / High-risk Projects Question
    if any(k in q for k in ["risk", "at risk", "high risk", "health"]):
        high_risk_projs = []
        for p in projects:
            pid = _str_id(p)
            pred = project_preds.get(pid, {})
            r_level = (pred.get("risk_class") or p.get("risk_level") or "LOW").upper()
            if r_level in ("HIGH", "CRITICAL", "MEDIUM"):
                high_risk_projs.append((p, r_level, pred.get("delay_days", 0), pred.get("budget_overrun_amount", 0)))

        if not high_risk_projs:
            return {
                "response": "Based on current NexusAI data and ML predictions, there are currently **no high-risk projects** in your authorized scope. All monitored projects are within acceptable parameters.",
                "intent": "risk_overview",
                "context_summary": {"high_risk_count": 0},
                "recommendations": [],
            }

        lines = [
            f"Here are the **{len(high_risk_projs)} projects** identified with elevated risk in your authorized scope:",
            "",
            "**ML Risk Predictions:**"
        ]
        for p, r_level, delay, overrun in high_risk_projs:
            lines.append(f"- **{p.get('name')}** — Risk: **{r_level}** | Est. Delay: **{delay} days** | Est. Overrun: **₹{overrun:,.0f}** (Progress: {p.get('progress', 0)}%)")

        lines.extend([
            "",
            "**Recommended Next Steps:**",
            "- Review overdue tasks and open blockers for these projects.",
            "- Consult the **Optimization** page to reassign capacity if team members are overloaded.",
            "- Check project-specific recommendations in the AI Insights tab."
        ])

        return {
            "response": "\n".join(lines),
            "intent": "risk_overview",
            "context_summary": {"high_risk_count": len(high_risk_projs)},
            "recommendations": [],
        }

    # 3. Delay / Schedule Question
    if any(k in q for k in ["delay", "delayed", "schedule", "deadline", "late"]):
        delayed_projs = []
        for p in projects:
            pid = _str_id(p)
            pred = project_preds.get(pid, {})
            delay = pred.get("delay_days", 0)
            if delay > 0 or (p.get("end_date") and p["end_date"] < today and p.get("status") != "completed"):
                delayed_projs.append((p, delay))

        delayed_projs.sort(key=lambda x: x[1], reverse=True)

        if not delayed_projs:
            return {
                "response": "According to NexusAI gradient boosting prediction models, no projects are currently forecasted to experience significant deadline delays.",
                "intent": "delay_overview",
                "context_summary": {"delayed_count": 0},
                "recommendations": [],
            }

        lines = [
            "**Projects with Predicted Schedule Delays:**",
            ""
        ]
        for p, delay in delayed_projs[:5]:
            lines.append(f"- **{p.get('name')}**: Predicted delay of **{delay} days** (Current progress: {p.get('progress', 0)}%, End date: {p.get('end_date', 'N/A')})")

        lines.extend([
            "",
            "**Actionable Recommendations:**",
            "- Audit blocked tasks and resolve critical dependencies.",
            "- Use sprint velocity adjustments or sprint scope trimming."
        ])

        return {
            "response": "\n".join(lines),
            "intent": "delay_overview",
            "context_summary": {"delayed_count": len(delayed_projs)},
            "recommendations": [],
        }

    # 4. Budget / Financial Question
    if any(k in q for k in ["budget", "cost", "expenditure", "overrun", "money"]):
        if role == "team_member":
            return {
                "response": "You are currently logged in as a Team Member. Financial and budget analytics are restricted to Project Managers and Administrators.",
                "intent": "rbac_restricted",
                "context_summary": {},
                "recommendations": [],
            }

        budget_summary = []
        for p in projects:
            b = float(p.get("budget", 0) or 0)
            s = float(p.get("current_expenditure", 0) or 0)
            pid = _str_id(p)
            pred = project_preds.get(pid, {})
            overrun = pred.get("budget_overrun_amount", 0)
            pct = (s / b * 100) if b > 0 else 0
            if pct > 80 or overrun > 0:
                budget_summary.append((p, b, s, pct, overrun))

        lines = [
            "**Budget & Financial Forecast:**",
            ""
        ]
        if budget_summary:
            for p, b, s, pct, overrun in budget_summary:
                lines.append(f"- **{p.get('name')}**: ₹{s:,.0f} / ₹{b:,.0f} ({pct:.1f}% utilized) | Predicted overrun: **₹{overrun:,.0f}**")
        else:
            lines.append("All projects within your scope are currently operating within allocated budgets.")

        lines.extend([
            "",
            "**Recommendation:**",
            "- Review high-expenditure tasks and external tool license costs to prevent margin erosion."
        ])

        return {
            "response": "\n".join(lines),
            "intent": "budget_overview",
            "context_summary": {"monitored_projects": len(budget_summary)},
            "recommendations": [],
        }

    # 5. Overdue / Tasks Question
    if any(k in q for k in ["task", "overdue", "todo", "unfinished", "blocked", "prioritize"]):
        overdue_tasks = [t for t in tasks if t.get("status") != "done" and t.get("due_date") and t["due_date"] < today]
        blocked_tasks = [t for t in tasks if t.get("status") == "blocked"]
        in_progress = [t for t in tasks if t.get("status") == "in_progress"]

        lines = [
            f"**Task Breakdown ({len(tasks)} total tasks in your authorized scope):**",
            f"- Overdue: **{len(overdue_tasks)}**",
            f"- Blocked: **{len(blocked_tasks)}**",
            f"- In Progress: **{len(in_progress)}**",
            ""
        ]

        if overdue_tasks:
            lines.append("**Top Overdue Tasks:**")
            for t in overdue_tasks[:5]:
                lines.append(f"- **{t.get('title')}** (Due: {t.get('due_date')}, Priority: {t.get('priority', 'medium').capitalize()})")
            lines.append("")

        if blocked_tasks:
            lines.append("**Blocked Tasks Needing Immediate Unblocking:**")
            for t in blocked_tasks[:3]:
                lines.append(f"- **{t.get('title')}** (Assignee: {t.get('assignee_name', 'Unassigned')})")
            lines.append("")

        lines.extend([
            "**Action:**",
            "- Reassign or focus sprint effort on overdue and blocked items first."
        ])

        return {
            "response": "\n".join(lines),
            "intent": "tasks_overview",
            "context_summary": {"overdue": len(overdue_tasks), "blocked": len(blocked_tasks)},
            "recommendations": [],
        }

    # 6. Team / Workload / Overloaded / Burnout Question
    if any(k in q for k in ["overload", "burnout", "workload", "capacity", "team", "employee", "who"]):
        if role == "team_member":
            # Only summarize team member's own tasks
            my_tasks = [t for t in tasks if t.get("assignee_id") == ctx["user_id"]]
            return {
                "response": f"As a Team Member, you can see your personal workload. You currently have **{len(my_tasks)} task(s)** assigned to you ({sum(1 for t in my_tasks if t.get('status') == 'in_progress')} in progress). Team-wide workload and burnout analytics are restricted to Project Managers and Administrators.",
                "intent": "workload_personal",
                "context_summary": {"personal_tasks": len(my_tasks)},
                "recommendations": [],
            }

        # For Admin/PM
        employees = ctx["employees"]
        high_burnout = []
        for e in employees:
            eid = _str_id(e)
            b = burnout_preds.get(eid, {})
            level = b.get("burnout_risk_level", "LOW")
            prob = b.get("burnout_probability", 0)
            if level in ("HIGH", "MEDIUM") or prob > 0.5:
                high_burnout.append((e.get("name", "Unknown"), level, prob, e.get("role", "Developer")))

        lines = [
            f"**Team Workload & Burnout Intelligence ({len(employees)} team members in scope):**",
            ""
        ]
        if high_burnout:
            lines.append("**Employees with Elevated Burnout Risk (ML Random Forest):**")
            for name, lvl, prob, erole in high_burnout:
                lines.append(f"- **{name}** ({erole}): Risk **{lvl}** (Score: {prob:.2f})")
            lines.append("")
            lines.append("**Recommendation:**")
            lines.append("- Utilize the **Resource Optimization** module to rebalance story points and assign critical tasks to members with spare capacity.")
        else:
            lines.append("All team members are currently operating at sustainable workload levels with Low burnout indicators.")

        return {
            "response": "\n".join(lines),
            "intent": "team_workload",
            "context_summary": {"team_size": len(employees), "elevated_risk": len(high_burnout)},
            "recommendations": [],
        }

    # 7. Recommendations Question
    if any(k in q for k in ["recommend", "recommendation", "prioritize", "action", "suggest", "what should i do"]):
        if recs:
            lines = [
                f"**Active NexusAI Recommendations ({len(recs)} available):**",
                ""
            ]
            for r in recs[:5]:
                lines.append(f"- **[{r.get('priority', 'medium').upper()}] {r.get('title')}**: {r.get('description', '')}")
            return {
                "response": "\n".join(lines),
                "intent": "recommendations",
                "context_summary": {"count": len(recs)},
                "recommendations": recs[:5],
            }

    # 8. General Scope Overview
    lines = [
        f"**NexusAI Scope Summary for {ctx['user_name']} ({role.replace('_', ' ').title()}):**",
        f"- Active Projects: **{len(projects)}**",
        f"- Visible Tasks: **{len(tasks)}** ({sum(1 for t in tasks if t.get('status') == 'done')} completed)",
        f"- Visible Issues: **{len(issues)}** ({sum(1 for i in issues if i.get('status') == 'resolved')} resolved)",
        "",
        "You can ask me questions such as:",
        "- *'Which projects are at high risk?'*",
        "- *'Which project is most delayed?'*",
        "- *'How many tasks are overdue?'*",
        "- *'How is Project Alpha performing?'*",
    ]
    if role in ("admin", "project_manager"):
        lines.append("- *'Who is overloaded in the team?'*")
        lines.append("- *'What is our budget status?'*")

    return {
        "response": "\n".join(lines),
        "intent": "overview",
        "context_summary": {"projects": len(projects), "tasks": len(tasks)},
        "recommendations": [],
    }


async def ask_decision_assistant(user: dict, db, message: str, project_id: Optional[str] = None, history: Optional[List[dict]] = None) -> Dict[str, Any]:
    """
    Main entry point for AI Decision Assistant.
    1. Fetches authorized RBAC data
    2. Identifies mentioned project (or handles project_id parameter)
    3. Handles non-existent project explicitly (NO hallucination)
    4. If LLM provider configured, queries LLM with grounded prompt
    5. Otherwise falls back to deterministic grounded synthesis
    """
    ctx = await get_scoped_context(user, db, project_id)
    projects = ctx["projects"]

    # Check if a project was specifically targeted via param or text
    matched_project = ctx["target_project"]
    if not matched_project:
        matched_project = find_matched_project(message, projects)

    # Check if user asked about a specific project that is NOT in their scope or database
    proj_regex = re.search(r'\bproject\s+([A-Za-z0-9_\-]+)\b', message, re.IGNORECASE)
    common_words = {"has", "with", "currently", "status", "risk", "delays", "delay", "progress", "budget", "health", "alpha", "beta", "gamma", "name", "overview", "details"}
    if proj_regex and not matched_project:
        queried_name = proj_regex.group(1).lower()
        if queried_name not in common_words:
            other_p = await db.projects.find_one({"name": {"$regex": f"^{queried_name}$", "$options": "i"}})
            if other_p:
                return {
                    "response": f"You do not have access to **Project {proj_regex.group(1)}**. Access is restricted by your role ({user.get('role')}).",
                    "intent": "unauthorized_project",
                    "context_summary": {},
                    "recommendations": [],
                }
            else:
                return {
                    "response": f"I couldn't find **Project {proj_regex.group(1)}** in NexusAI. I can only provide insights on verified projects stored in the system.",
                    "intent": "not_found",
                    "context_summary": {},
                    "recommendations": [],
                }

    # If LLM API Key is available, build grounded prompt and call LLM
    if settings.ai_api_key and settings.ai_api_key.strip():
        try:
            context_summary = {
                "user_role": ctx["role"],
                "today": ctx["today"],
                "projects": [
                    {
                        "name": p.get("name"),
                        "status": p.get("status"),
                        "progress": p.get("progress"),
                        "budget": p.get("budget"),
                        "spent": p.get("current_expenditure"),
                        "end_date": p.get("end_date"),
                        "risk_level": p.get("risk_level"),
                    } for p in projects[:15]
                ],
                "task_counts": {
                    "total": len(ctx["tasks"]),
                    "overdue": sum(1 for t in ctx["tasks"] if t.get("status") != "done" and t.get("due_date") and t["due_date"] < ctx["today"]),
                    "blocked": sum(1 for t in ctx["tasks"] if t.get("status") == "blocked"),
                    "done": sum(1 for t in ctx["tasks"] if t.get("status") == "done"),
                },
                "ml_project_predictions": [
                    {
                        "project_name": next((p.get("name") for p in projects if _str_id(p) == pred.get("project_id")), "Unknown"),
                        "risk_class": pred.get("risk_class"),
                        "delay_days": pred.get("delay_days"),
                        "budget_overrun_amount": pred.get("budget_overrun_amount"),
                    } for pred in ctx["project_predictions"][:15]
                ],
            }

            if ctx["role"] in ("admin", "project_manager"):
                context_summary["team_burnout_ml"] = [
                    {
                        "employee_name": next((e.get("name") for e in ctx["employees"] if _str_id(e) == b.get("employee_id")), "Unknown"),
                        "burnout_risk_level": b.get("burnout_risk_level"),
                        "burnout_probability": b.get("burnout_probability"),
                    } for b in ctx["burnout_predictions"][:15]
                ]

            system_prompt = f"""You are the NexusAI AI Decision Assistant.
You answer user inquiries strictly grounded in provided NexusAI data.

GROUNDING & TRUTHFULNESS RULES:
1. ONLY use information present in the provided context.
2. NEVER invent projects, tasks, employees, deadlines, metrics, or predictions.
3. If data is missing or not in context, state: "I don't have enough data in NexusAI to determine that."
4. Distinguish between CURRENT FACTS, ML PREDICTIONS (estimated/predicted), and ACTIONABLE RECOMMENDATIONS.
5. Respect user role: {ctx['role']}. Never reveal data forbidden for this role.

CONTEXT:
{context_summary}
"""

            messages = [{"role": "system", "content": system_prompt}]
            if history:
                for h in history[-4:]:
                    messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
            messages.append({"role": "user", "content": message})

            async with httpx.AsyncClient(timeout=25) as client:
                res = await client.post(
                    f"{settings.ai_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.ai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.ai_model,
                        "messages": messages,
                        "temperature": 0.2,
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    answer = data["choices"][0]["message"]["content"]
                    return {
                        "response": answer,
                        "intent": "llm_grounded",
                        "context_summary": {"matched_project": matched_project.get("name") if matched_project else None},
                        "recommendations": ctx["recommendations"][:3],
                    }
        except Exception:
            pass

    # Deterministic grounded fallback
    return generate_grounded_fallback_response(message, ctx, matched_project)
