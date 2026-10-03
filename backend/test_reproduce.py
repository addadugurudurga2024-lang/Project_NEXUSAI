import asyncio
import httpx
from app.db.database import connect_db, get_database
from app.core.security import create_access_token

async def reproduce():
    await connect_db()
    db = get_database()
    
    # Check Project Managers
    pms = await db.users.find({"role": "project_manager"}).to_list(10)
    print(f"Found {len(pms)} Project Managers.")
    
    for pm in pms:
        uid = str(pm["_id"])
        email = pm.get("email")
        token = create_access_token({"sub": uid, "role": "project_manager", "email": email})
        headers = {"Authorization": f"Bearer {token}"}
        
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            proj_res = await client.get("/projects/", headers=headers)
            exec_res = await client.get("/analytics/executive", headers=headers)
            
            proj_count = len(proj_res.json()) if proj_res.status_code == 200 else f"Err {proj_res.status_code}"
            if exec_res.status_code == 200:
                exec_data = exec_res.json()
                exec_proj = exec_data.get("projects", {}).get("total")
                exec_high_risk = exec_data.get("projects", {}).get("high_risk")
                exec_tasks = exec_data.get("tasks", {}).get("total")
                exec_issues = exec_data.get("issues", {}).get("open")
                exec_team = exec_data.get("employees", {}).get("total")
            else:
                exec_proj = f"Err {exec_res.status_code}"
                exec_high_risk = None
                exec_tasks = None
                exec_issues = None
                exec_team = None
                
            print(f"PM: {email} (ID: {uid})")
            print(f"  /projects/ returned: {proj_count} projects")
            print(f"  /analytics/executive returned: total_projects={exec_proj}, high_risk={exec_high_risk}, tasks={exec_tasks}, issues={exec_issues}, team={exec_team}")

if __name__ == "__main__":
    asyncio.run(reproduce())
