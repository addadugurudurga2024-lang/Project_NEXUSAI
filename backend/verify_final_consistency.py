import asyncio
import sys
import io

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from app.db.database import connect_db, close_db, get_database
from app.services.project_scoping_service import get_authorized_projects, get_authorized_project_ids, get_authorized_employee_ids
from app.services.resource_optimizer import compute_resource_optimization
from app.services.ai_assistant_service import ask_decision_assistant
from app.api.analytics import get_executive_analytics, get_project_analytics, get_team_analytics, get_risk_analytics, get_executive_insights

async def main():
    await connect_db()
    db = get_database()
    users = await db['users'].find().to_list(100)
    pm = next((u for u in users if u.get('role') == 'project_manager'), None)
    admin = next((u for u in users if u.get('role') == 'admin'), None)
    tm = next((u for u in users if u.get('role') == 'team_member'), None)
    
    print('=== 1. USER ROLES & SCOPING ===')
    print(f'Admin: {admin.get("email")} (Role: {admin.get("role")})')
    print(f'PM:    {pm.get("email")} (Role: {pm.get("role")})')
    print(f'TM:    {tm.get("email")} (Role: {tm.get("role")})')
    
    admin_projects = await get_authorized_projects(db, admin)
    pm_projects = await get_authorized_projects(db, pm)
    tm_projects = await get_authorized_projects(db, tm)
    print(f'Admin authorized projects: {len(admin_projects)}')
    print(f'PM authorized projects:    {len(pm_projects)}')
    print(f'TM authorized projects:    {len(tm_projects)}')
    assert len(admin_projects) == 9, f"Expected 9 projects for admin, got {len(admin_projects)}"
    assert len(pm_projects) == 9, f"Expected 9 projects for PM, got {len(pm_projects)}"
    
    print('\n=== 2. ANALYTICS CONSISTENCY (PM View) ===')
    exec_data = await get_executive_analytics(current_user=pm, db=db)
    print(f'Executive Summary Projects: {exec_data.get("projects", {}).get("total")} (High Risk: {exec_data.get("projects", {}).get("high_risk")})')
    print(f'Executive Summary Tasks:    {exec_data.get("tasks", {}).get("total")} (Overdue: {exec_data.get("tasks", {}).get("overdue")})')
    print(f'Executive Summary Issues:   {exec_data.get("issues", {}).get("total")} (Open: {exec_data.get("issues", {}).get("open")})')
    assert exec_data["projects"]["total"] == 9, f"Expected 9 total projects in Executive summary, got {exec_data['projects']['total']}"
    
    proj_data = await get_project_analytics(current_user=pm, db=db)
    print(f'Project Analytics count:    {len(proj_data)}')
    assert len(proj_data) == 9, f"Expected 9 projects in Project Analytics, got {len(proj_data)}"
    
    risk_data = await get_risk_analytics(current_user=pm, db=db)
    print(f'Risk Analytics Project Risks: High={risk_data["project_risk"]["high"]}, Med={risk_data["project_risk"]["medium"]}, Low={risk_data["project_risk"]["low"]}')
    print(f'Risk Analytics Deadline Delays: {risk_data["deadline"]["projects_with_delay"]} projects with delay, Max={risk_data["deadline"]["max_delay_days"]}d')
    print(f'Risk Analytics Budget Overruns: {risk_data["budget_overrun"]["projects_at_risk"]} at risk, Max={risk_data["budget_overrun"]["max_overrun_amount"]}')
    
    print('\n=== 3. TEAM ANALYTICS & ALEX RODRIGUEZ WORKLOAD ===')
    team_data = await get_team_analytics(current_user=pm, db=db)
    print(f'Team Analytics Members: {team_data["summary"]["total"]}, Above Capacity: {team_data["summary"]["above_capacity"]}')
    alex_entry = next((e for e in team_data["employees"] if "Alex" in e["name"]), None)
    if alex_entry:
        print(f'Alex Rodriguez: Workload = {alex_entry["workload_ratio"]}%, Assigned = {alex_entry["assigned_hours"]}h, Capacity = {alex_entry["weekly_capacity_hours"]}h/wk, Tasks = {alex_entry["tasks"]["total"]}')
        assert alex_entry["workload_ratio"] == 300, f"Expected 300% for Alex Rodriguez, got {alex_entry['workload_ratio']}%"
    
    print('\n=== 4. RESOURCE OPTIMIZATION ===')
    alpha_proj = await db['projects'].find_one({'name': {'$regex': 'Alpha', '$options': 'i'}})
    if alpha_proj:
        res = await compute_resource_optimization(str(alpha_proj['_id']), db=db)
        print(f'Alpha E-Commerce Optimization: Suggestions={len(res.get("reallocation_suggestions", []))}')
        for r in res.get("reallocation_suggestions", []):
            print(f'  - Move "{r.get("task_title")}" ({r.get("estimated_hours")}h) from {r.get("from_employee_name")} -> {r.get("to_employee_name")}')
        if res.get("message"):
            print(f'  - Summary note: {res.get("message")}')
            
    print('\n=== 5. AI INSIGHTS ===')
    insights_resp = await get_executive_insights(current_user=pm, db=db)
    insights = insights_resp.get("insights", [])
    print(f'AI Insights count: {len(insights)}')
    for ins in insights:
        print(f'  - [{ins.get("level").upper()}] {ins.get("text")} (Source: {ins.get("source")}, Entity: {ins.get("entity_reference")})')
    assert len(insights) > 0, "Expected insights to be populated"
    assert not any("All projects are currently within healthy operational thresholds" in ins["text"] for ins in insights), "Misleading healthy message present when issues exist!"
    
    print('\n=== 6. AI ASSISTANT GROUNDINGS & RBAC ===')
    q1 = await ask_decision_assistant(user=pm, db=db, message='Which projects currently have the highest risk?')
    print(f'PM Risk Query Response:\n{q1.get("response")[:250]}...\n')
    assert "HIGH" in q1.get("response") or "risk" in q1.get("response").lower()
    
    q2 = await ask_decision_assistant(user=tm, db=db, message='Show me the burnout risk of all employees.')
    print(f'TM Restricted Query Response:\n{q2.get("response")}\n')
    assert "restricted" in q2.get("response").lower() or "permission" in q2.get("response").lower() or "access" in q2.get("response").lower()
    
    print('ALL VERIFICATION CHECKS COMPLETED SUCCESSFULLY!')
    await close_db()

if __name__ == '__main__':
    asyncio.run(main())
