import asyncio
import httpx
from app.db.database import connect_db, get_database
from app.core.security import create_access_token

async def test_analytics_endpoints():
    await connect_db()
    db = get_database()
    pm = await db.users.find_one({"email": "abhishekads264@gmail.com"})
    uid = str(pm["_id"])
    token = create_access_token({"sub": uid, "role": "project_manager", "email": pm.get("email")})
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        print("--- 1. /analytics/executive ---")
        res1 = await client.get("/analytics/executive", headers=headers)
        print("Status:", res1.status_code)
        print(res1.json())
        
        print("\n--- 2. /analytics/insights ---")
        res2 = await client.get("/analytics/insights", headers=headers)
        print("Status:", res2.status_code)
        for ins in res2.json().get("insights", []):
            print("  Insight:", ins)
            
        print("\n--- 3. /analytics/projects ---")
        res3 = await client.get("/analytics/projects", headers=headers)
        print("Status:", res3.status_code, "Count:", len(res3.json()))
        for p in res3.json()[:3]:
            print(f"  Project: {p['name']} | Status: {p['status']} | Progress: {p['progress']}% | Risk: {p['ml']['risk_class']} | Delay: {p['ml']['delay_days']} | BudgetRisk: {p['ml']['budget_overrun_risk']}")
            
        print("\n--- 4. /analytics/team ---")
        res4 = await client.get("/analytics/team", headers=headers)
        print("Status:", res4.status_code, "Count:", len(res4.json().get("employees", [])))
        for e in res4.json().get("employees", []):
            print(f"  Employee: {e['name']} ({e.get('email')}) | Load: {e['workload_ratio']}% ({e['assigned_hours']}h / {e['weekly_capacity_hours']}h) | Burnout: {e['burnout']['risk_level']}")
            
        print("\n--- 5. /analytics/risks ---")
        res5 = await client.get("/analytics/risks", headers=headers)
        print("Status:", res5.status_code)
        print("  Project Risk:", res5.json().get("project_risk"))
        print("  Employee Burnout:", res5.json().get("employee_burnout"))

if __name__ == "__main__":
    asyncio.run(test_analytics_endpoints())
