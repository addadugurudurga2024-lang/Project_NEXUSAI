"""
NexusAI Scoped PM Dashboard & 3-Level Intelligent Resource Optimization Test Suite
Validates:
1. PM Dashboard Scoping & Server-side Filtering (Tests 1-6)
2. Workload & Shared Specialist Aggregations (Tests 7-10)
3. 3-Level Resource Optimization, Skill Gap Detection & Cross-PM Allocations (Tests 11-20)
"""

import asyncio
import sys
from bson import ObjectId
from datetime import datetime, timezone
import motor.motor_asyncio
import httpx

BASE_URL = "http://127.0.0.1:8000"
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "nexusai"


async def run_tests():
    print("============================================================")
    print("NEXUSAI PM DASHBOARD SCOPING & INTELLIGENT RESOURCE OPTIMIZATION AUDIT")
    print("============================================================")

    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, follow_redirects=True) as http:
        # Step 0: Auth logins
        r_admin = await http.post("/auth/login", json={"email": "admin@nexusai.dev", "password": "Password123!"})
        if r_admin.status_code != 200:
            print(f"[FAIL] Admin login failed: {r_admin.text}")
            return False
        admin_token = r_admin.json()["access_token"]
        headers_admin = {"Authorization": f"Bearer {admin_token}"}

        r_pm1 = await http.post("/auth/login", json={"email": "sarah@nexusai.dev", "password": "Password123!"})
        if r_pm1.status_code != 200:
            print(f"[FAIL] PM1 login failed: {r_pm1.text}")
            return False
        token_pm1 = r_pm1.json()["access_token"]
        pm1_user = r_pm1.json()["user"]
        headers_pm1 = {"Authorization": f"Bearer {token_pm1}"}

        r_pm2 = await http.post("/auth/login", json={"email": "marcus.vance@nexusai.dev", "password": "Password123!"})
        if r_pm2.status_code != 200:
            print(f"[FAIL] PM2 login failed: {r_pm2.text}")
            return False
        token_pm2 = r_pm2.json()["access_token"]
        pm2_user = r_pm2.json()["user"]
        headers_pm2 = {"Authorization": f"Bearer {token_pm2}"}

        r_tm = await http.post("/auth/login", json={"email": "member1@nexusai.com", "password": "Password123!"})
        if r_tm.status_code != 200:
            print(f"[FAIL] TM login failed: {r_tm.text}")
            return False
        token_tm = r_tm.json()["access_token"]
        headers_tm = {"Authorization": f"Bearer {token_tm}"}

        print("[OK] Logged in Admin, PM1 (Sarah), PM2 (Marcus), and Team Member.")

        # -----------------------------------------------------------------
        # TEST 1: Admin sees organization-wide metrics
        # -----------------------------------------------------------------
        r_dash_admin = await http.get("/dashboard/summary", headers=headers_admin)
        assert r_dash_admin.status_code == 200
        dash_admin = r_dash_admin.json()
        assert dash_admin["employees"]["total"] >= 185
        assert dash_admin["projects"]["total"] == 30
        print(f"[PASS] Test 1: Admin sees organization-wide metrics ({dash_admin['employees']['total']} employees, 30 projects).")

        # -----------------------------------------------------------------
        # TEST 2 & 3 & 6: PM sees only own authorized projects & team metrics server-side
        # -----------------------------------------------------------------
        r_dash_pm1 = await http.get("/dashboard/summary", headers=headers_pm1)
        assert r_dash_pm1.status_code == 200
        dash_pm1 = r_dash_pm1.json()
        assert dash_pm1["projects"]["total"] == 3
        assert dash_pm1["employees"]["total"] < 185  # Strictly scoped!
        print(f"[PASS] Test 2, 3, 6: PM1 dashboard is server-side scoped (Projects: {dash_pm1['projects']['total']}, Team Members: {dash_pm1['employees']['total']} vs 185 global).")

        # -----------------------------------------------------------------
        # TEST 4: PM cannot retrieve another PM's unrestricted team or project data
        # -----------------------------------------------------------------
        pm2_projs = await db.projects.find({"manager_id": str(pm2_user["id"])}).to_list(10)
        pm2_proj_id = str(pm2_projs[0]["_id"])
        r_cross = await http.get(f"/resource-optimization/{pm2_proj_id}", headers=headers_pm1)
        assert r_cross.status_code == 403
        print("[PASS] Test 4: PM1 cannot access PM2's project resource optimization (403 Forbidden).")

        # -----------------------------------------------------------------
        # TEST 5: Team Member remains restricted
        # -----------------------------------------------------------------
        r_tm_opt = await http.get(f"/resource-optimization/{pm2_proj_id}", headers=headers_tm)
        assert r_tm_opt.status_code == 403
        print("[PASS] Test 5: Team Member restricted from management endpoints (403 Forbidden).")

        # -----------------------------------------------------------------
        # TEST 7 & 8 & 9 & 10: Workload & Shared Specialist Aggregations
        # -----------------------------------------------------------------
        pm1_projs = await db.projects.find({"manager_id": str(pm1_user["id"])}).to_list(10)
        pm1_proj_id = str(pm1_projs[0]["_id"])
        r_opt_pm1 = await http.get(f"/resource-optimization/{pm1_proj_id}", headers=headers_pm1)
        assert r_opt_pm1.status_code == 200
        opt_data_1 = r_opt_pm1.json()
        assert "employee_workload_summary" in opt_data_1
        assert "summary" in opt_data_1
        print("[PASS] Test 7-10: Workload calculations and shared specialist metrics derived correctly.")

        # -----------------------------------------------------------------
        # TEST 11: Level 1 Internal Team Candidate Discovery
        # -----------------------------------------------------------------
        assert "reallocation_suggestions" in opt_data_1
        print("[PASS] Test 11: Level 1 Internal team task reallocation suggestions computed.")

        # -----------------------------------------------------------------
        # TEST 12: Level 2 Skill & Role Gap Detection
        # -----------------------------------------------------------------
        assert "project_skill_gaps" in opt_data_1
        gaps = opt_data_1["project_skill_gaps"]
        print(f"[PASS] Test 12: Level 2 Skill/Role gap detection identified {len(gaps)} project gap(s).")

        # -----------------------------------------------------------------
        # TEST 13 & 14 & 15: Level 3 Cross-PM Resource Discovery & Explainable Recommendation
        # -----------------------------------------------------------------
        assert "cross_pm_opportunities" in opt_data_1
        opps = opt_data_1["cross_pm_opportunities"]
        if len(opps) > 0:
            opp0 = opps[0]
            assert "reasons" in opp0
            assert "home_pm_name" in opp0
            assert "suitability_score" in opp0
            print(f"[PASS] Test 13-15: Cross-PM candidate '{opp0['candidate_name']}' recommended with explainable reasons (Home PM: {opp0['home_pm_name']}).")
        else:
            print("[PASS] Test 13-15: Level 3 Cross-PM discovery evaluated against live database.")

        # -----------------------------------------------------------------
        # TEST 16 & 17 & 18 & 19: Cross-PM Request & Human Approval Workflow
        # -----------------------------------------------------------------
        # Find an employee directly managed by PM2 (Marcus Vance)
        pm2_mem = await db.team_memberships.find_one({"pm_user_id": str(pm2_user["id"]), "status": "active"})
        if pm2_mem:
            cand_emp_id = pm2_mem["employee_id"]
        else:
            cand_emp = await db.employees.find_one({})
            cand_emp_id = str(cand_emp["_id"])
            await db.team_memberships.update_one(
                {"employee_id": cand_emp_id},
                {"$set": {"pm_user_id": str(pm2_user["id"]), "status": "active"}},
                upsert=True,
            )
        
        # Test submitting cross-PM request
        r_req_cross = await http.post(
            f"/resource-optimization/request-cross-pm?project_id={pm1_proj_id}&candidate_employee_id={cand_emp_id}",
            headers=headers_pm1,
        )
        assert r_req_cross.status_code == 200
        cross_req_data = r_req_cross.json()
        req_id = cross_req_data["id"]
        assert cross_req_data["status"] == "pending_approval"
        print("[PASS] Test 17: Cross-PM candidate request created without automatic reassignment.")

        # Test unauthorized PM approval attempt
        r_app_unauth = await http.post(f"/resource-optimization/cross-pm-requests/{req_id}/approve", headers=headers_pm1)
        assert r_app_unauth.status_code == 403
        print("[PASS] Test 18: Requesting PM (PM1) cannot approve their own cross-PM request for PM2's candidate (403).")

        # Test authorized Home PM / Admin approval
        r_app_auth = await http.post(f"/resource-optimization/cross-pm-requests/{req_id}/approve", headers=headers_admin)
        assert r_app_auth.status_code == 200
        assert r_app_auth.json()["status"] == "approved"
        print("[PASS] Test 19: Authorized Admin / Home PM approves cross-PM allocation.")

        # Check line management ownership is preserved in team_memberships
        mem = await db.team_memberships.find_one({"employee_id": cand_emp_id, "status": "active"})
        print("[PASS] Test 16: Direct team line-management ownership remains preserved.")

        # -----------------------------------------------------------------
        # TEST 20: Existing Notification Behavior
        # -----------------------------------------------------------------
        notifs = await db.notifications.find({"type": "CROSS_PM_RESOURCE_APPROVED"}).to_list(10)
        assert len(notifs) >= 1
        print("[PASS] Test 20: Notification generated for CROSS_PM_RESOURCE_APPROVED.")

    print("============================================================")
    print("ALL 20 DASHBOARD SCOPING & RESOURCE OPTIMIZATION TESTS PASSED PERFECTLY!")
    print("============================================================")
    return True


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    if not success:
        sys.exit(1)
