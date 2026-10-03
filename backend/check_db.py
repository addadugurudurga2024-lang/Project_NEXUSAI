import asyncio
# pyrefly: ignore [missing-import]
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['nexusai']
    users = await db.users.find({}).to_list(10)
    print(f"Total users: {len(users)}")
    for u in users:
        print(f"  email={u.get('email')}  role={u.get('role')}")
    projects = await db.projects.find({}).to_list(5)
    print(f"\nTotal projects: {len(projects)}")
    for p in projects:
        print(f"  id={str(p['_id'])}  name={p.get('name')}")

asyncio.run(main())
