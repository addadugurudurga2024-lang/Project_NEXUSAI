import asyncio
from app.db.database import connect_db, get_database

async def inspect_projects():
    await connect_db()
    db = get_database()
    projects = await db.projects.find({}).to_list(100)
    for p in projects:
        print("--------------------------------------------------")
        print(f"ID: {p['_id']}")
        print(f"Name: {p.get('name')}")
        print(f"manager_id: {p.get('manager_id')}")
        print(f"project_manager_id: {p.get('project_manager_id')}")
        print(f"created_by: {p.get('created_by')}")
        print(f"team_member_ids: {p.get('team_member_ids')}")
        print(f"status: {p.get('status')}")

if __name__ == "__main__":
    asyncio.run(inspect_projects())
