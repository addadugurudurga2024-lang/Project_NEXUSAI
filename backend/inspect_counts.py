import asyncio
from app.db.database import connect_db, get_database

async def inspect():
    await connect_db()
    db = get_database()
    collections = [
        "projects", "employees", "users", "tasks", "issues",
        "sprints", "project_predictions", "employee_risk_predictions",
        "recommendations", "notifications"
    ]
    for coll in collections:
        count = await db[coll].count_documents({})
        print(f"{coll}: {count}")
        
    print("\n--- ALL USERS ---")
    users = await db.users.find({}).to_list(100)
    for u in users:
        print(f"User: id={u.get('_id')} email={u.get('email')} role={u.get('role')} name={u.get('name')}")

if __name__ == "__main__":
    asyncio.run(inspect())
