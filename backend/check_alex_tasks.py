import asyncio
from app.db.database import connect_db, get_database

async def check_alex_tasks():
    await connect_db()
    db = get_database()
    tasks = await db.tasks.find({"assignee_id": "6a85941997238d6d29362523"}).to_list(100)
    for t in tasks:
        p = await db.projects.find_one({"_id": t.get("project_id")}) or await db.projects.find_one({"_id": str(t.get("project_id"))})
        pname = p.get("name") if p else "Unknown Project"
        print(f"Task: {t.get('title')} | hours: {t.get('estimated_hours')} | status: {t.get('status')} | project_id: {t.get('project_id')} ({pname})")

if __name__ == "__main__":
    asyncio.run(check_alex_tasks())
