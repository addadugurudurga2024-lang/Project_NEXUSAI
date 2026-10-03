import asyncio
from app.db.database import connect_db, get_database
from app.services.resource_optimizer import compute_resource_optimization

async def test_all_optim():
    await connect_db()
    db = get_database()
    projects = await db.projects.find({}).to_list(100)
    for p in projects:
        pid = str(p["_id"])
        name = p.get("name")
        res = await compute_resource_optimization(pid, db)
        print(f"Project: {name} (ID: {pid})")
        print(f"  Summary: {res['summary']}")
        print(f"  Message: {res['message']}")
        print(f"  Suggestions count: {len(res['reallocation_suggestions'])}")
        for s in res['reallocation_suggestions']:
            print(f"    - Task: '{s.get('task_title')}' from {s.get('from_employee_name')} to {s.get('employee_name')}")

if __name__ == "__main__":
    asyncio.run(test_all_optim())
