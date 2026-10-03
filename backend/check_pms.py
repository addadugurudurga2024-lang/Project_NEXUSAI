import asyncio
from bson import ObjectId
from app.db.database import connect_db, get_database

async def check_pms():
    await connect_db()
    db = get_database()
    
    pms = await db.users.find({"role": "project_manager"}).to_list(100)
    print(f"Total PMs: {len(pms)}")
    for pm in pms:
        uid = str(pm["_id"])
        email = pm.get("email")
        name = pm.get("name")
        emp = await db.employees.find_one({"$or": [{"user_id": uid}, {"email": email}]})
        emp_id = str(emp["_id"]) if emp else None
        
        # Scoped projects query
        possible_ids = [uid] + ([emp_id] if emp_id else [])
        obj_ids = [ObjectId(x) for x in possible_ids if ObjectId.is_valid(x)]
        all_ids = possible_ids + obj_ids
        
        scoped = await db.projects.find({
            "$or": [
                {"project_manager_id": {"$in": all_ids}},
                {"manager_id": {"$in": all_ids}},
                {"team_member_ids": {"$in": possible_ids}},
                {"created_by": uid},
            ]
        }).to_list(100)
        
        print(f"PM: id={uid} email={email} name={name} linked_emp={emp_id} scoped_project_count={len(scoped)}")
        for sp in scoped:
            print(f"   -> scoped project: {sp.get('name')} (id={sp.get('_id')})")

if __name__ == "__main__":
    asyncio.run(check_pms())
