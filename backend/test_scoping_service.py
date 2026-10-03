import asyncio
from app.db.database import connect_db, get_database
from app.services.project_scoping_service import get_authorized_project_ids, get_authorized_employee_ids

async def test_scoping():
    await connect_db()
    db = get_database()
    
    test_emails = [
        "admin@nexusai.dev",
        "sarah@nexusai.dev",
        "abhishekads264@gmail.com",
        "devuser@gmail.com",
        "lokesh123@gmail.com",
        "member2@nexusai.com",
    ]
    for email in test_emails:
        user = await db.users.find_one({"email": email})
        if not user:
            print(f"User {email} not found")
            continue
        pids = await get_authorized_project_ids(db, user)
        eids = await get_authorized_employee_ids(db, user)
        print(f"User: {email} (role: {user.get('role')}) -> authorized_projects: {len(pids)}, authorized_employees: {len(eids)}")

if __name__ == "__main__":
    asyncio.run(test_scoping())
