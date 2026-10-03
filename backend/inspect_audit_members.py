import asyncio
from bson import ObjectId
from app.db.database import connect_db, get_database

async def inspect_audit():
    await connect_db()
    db = get_database()
    emps = await db.employees.find({"name": "Audit Team Member"}).to_list(100)
    print(f"Total 'Audit Team Member' records: {len(emps)}")
    for e in emps:
        eid = str(e["_id"])
        email = e.get("email")
        created = e.get("created_at")
        user_id = e.get("user_id")
        
        # Check tasks assigned
        tasks = await db.tasks.find({"assignee_id": eid}).to_list(100)
        # Check issues assigned
        issues = await db.issues.find({"assignee_id": eid}).to_list(100)
        # Check projects assigned
        projs = await db.projects.find({"team_member_ids": eid}).to_list(100)
        
        print(f"\nID: {eid} | email: {email} | user_id: {user_id} | created: {created}")
        print(f"  Tasks assigned: {len(tasks)}")
        print(f"  Issues assigned: {len(issues)}")
        print(f"  Projects team_member_ids: {len(projs)}")

if __name__ == "__main__":
    asyncio.run(inspect_audit())
