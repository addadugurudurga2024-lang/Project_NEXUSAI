import asyncio
from bson import ObjectId
from app.db.database import connect_db, get_database

async def inspect():
    await connect_db()
    db = get_database()
    
    print("=== COLLECTION COUNTS ===")
    collections = [
        "projects", "employees", "users", "tasks", "issues",
        "sprints", "project_predictions", "employee_risk_predictions",
        "recommendations", "notifications"
    ]
    for coll in collections:
        count = await db[coll].count_documents({})
        print(f"{coll}: {count}")
        
    print("\n=== USERS (Project Managers & Admins) ===")
    users = await db.users.find({}).to_list(100)
    for u in users:
        print(f"User: id={u.get('_id')} email={u.get('email')} role={u.get('role')} name={u.get('name')} full_name={u.get('full_name')}")
        
    print("\n=== EMPLOYEES ===")
    employees = await db.employees.find({}).to_list(100)
    for e in employees:
        print(f"Employee: id={e.get('_id')} name={e.get('name')} email={e.get('email')} user_id={e.get('user_id')} role={e.get('role')} department={e.get('department')}")
        
    print("\n=== PROJECTS ===")
    projects = await db.projects.find({}).to_list(100)
    for p in projects:
        print(f"Project: id={p.get('_id')} (type={type(p.get('_id'))}) name='{p.get('name')}' manager_id={p.get('manager_id')} (type={type(p.get('manager_id'))}) project_manager_id={p.get('project_manager_id')} (type={type(p.get('project_manager_id'))}) created_by={p.get('created_by')} team_member_ids={p.get('team_member_ids')} status={p.get('status')}")
        
    print("\n=== PROJECT PREDICTIONS ===")
    preds = await db.project_predictions.find({}).to_list(100)
    for pr in preds:
        print(f"Pred: id={pr.get('_id')} project_id={pr.get('project_id')} (type={type(pr.get('project_id'))}) risk_level={pr.get('risk_level')} health_score={pr.get('health_score')} delay={pr.get('predicted_delay') or pr.get('predicted_delay_days')} budget_overrun={pr.get('budget_overrun') or pr.get('budget_risk')}")

    print("\n=== AUDIT TEAM MEMBERS ===")
    audit_members = [e for e in employees if "audit" in str(e.get("name", "")).lower()]
    for am in audit_members:
        print(f"Audit Member: {am}")

    print("\n=== ALEX RODRIGUEZ TASKS ===")
    alex = next((e for e in employees if "alex" in str(e.get("name", "")).lower()), None)
    if alex:
        print(f"Alex Employee ID: {alex.get('_id')}")
        alex_tasks = await db.tasks.find({
            "$or": [
                {"assignee_id": str(alex.get("_id"))},
                {"assignee_id": alex.get("_id")},
                {"assigned_to": str(alex.get("_id"))},
                {"assigned_to": alex.get("_id")}
            ]
        }).to_list(100)
        print(f"Alex task count: {len(alex_tasks)}")
        for t in alex_tasks:
            print(f"Task: id={t.get('_id')} title='{t.get('title')}' est_hours={t.get('estimated_hours')} status={t.get('status')} assignee_id={t.get('assignee_id')} assigned_to={t.get('assigned_to')}")

if __name__ == "__main__":
    asyncio.run(inspect())
