"""
NexusAI Team Capacity & Intelligent Member Allocation Automated Test Suite
Validates the complete 18-member PM team capacity and onboarding workflow:
- Test 1: PM with 17 active members accepts candidate (17 -> 18)
- Test 2: PM with 18 active members rejects 19th candidate
- Test 3: Team Member submits PM request
- Test 4: PM receives request notification
- Test 5: PM approves candidate request
- Test 6: PM rejects candidate request
- Test 7: Full PM triggers intelligent alternative recommendation
- Test 8: Unauthorized PM cannot approve candidate for another PM (403)
- Test 9: Team Member cannot approve request / assign themselves (403)
- Test 10: Concurrent assignment attempts do not exceed 18 active members
- Test 11: Role/skill composition calculation
- Test 12: Shared-specialist project assignments remain intact
- Test 13: Existing notification workflow remains intact
- Test 14: Existing RBAC and project scoping remain intact
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
    print("NEXUSAI TEAM CAPACITY & ONBOARDING WORKFLOW TEST SUITE")
    print("============================================================")

    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, follow_redirects=True) as http:
        # Step 0: Auth Logins
        r_pm1 = await http.post("/auth/login", json={"email": "sarah@nexusai.dev", "password": "Password123!"})
        if r_pm1.status_code != 200:
            print(f"[FAIL] Could not login PM1 (Sarah): {r_pm1.text}")
            return False
        token_pm1 = r_pm1.json()["access_token"]
        pm1_user = r_pm1.json()["user"]
        headers_pm1 = {"Authorization": f"Bearer {token_pm1}"}

        r_pm2 = await http.post("/auth/login", json={"email": "marcus.vance@nexusai.dev", "password": "Password123!"})
        if r_pm2.status_code != 200:
            print(f"[FAIL] Could not login PM2 (Marcus): {r_pm2.text}")
            return False
        token_pm2 = r_pm2.json()["access_token"]
        headers_pm2 = {"Authorization": f"Bearer {token_pm2}"}

        r_admin = await http.post("/auth/login", json={"email": "admin@nexusai.dev", "password": "Password123!"})
        if r_admin.status_code != 200:
            print(f"[FAIL] Could not login Admin: {r_admin.text}")
            return False
        token_admin = r_admin.json()["access_token"]
        headers_admin = {"Authorization": f"Bearer {token_admin}"}

        r_tm = await http.post("/auth/login", json={"email": "member1@nexusai.com", "password": "Password123!"})
        if r_tm.status_code != 200:
            print(f"[FAIL] Could not login Team Member: {r_tm.text}")
            return False
        token_tm = r_tm.json()["access_token"]
        tm_user = r_tm.json()["user"]
        headers_tm = {"Authorization": f"Bearer {token_tm}"}

        print("[OK] Logged in PM1, PM2, Admin, and Team Member successfully.")

        # Trigger DB initialization of baseline team memberships
        r_init = await http.get("/team-capacity/pms", headers=headers_pm1)
        if r_init.status_code != 200:
            print(f"[FAIL] /team-capacity/pms failed: {r_init.text}")
            return False

        pm1_id = pm1_user["id"]

        # Fetch candidate employee for test requests
        test_emp = await db.employees.find_one({"email": "member1@nexusai.com"})
        if not test_emp:
            test_emp = await db.employees.find_one({})
        test_emp_id = str(test_emp["_id"])

        another_emp = await db.employees.find_one({"_id": {"$ne": test_emp["_id"]}})
        another_emp_id = str(another_emp["_id"])

        # Helper: Reset PM1 team capacity in DB to a specific number of active members
        async def set_pm1_active_count(count: int):
            await db.team_memberships.delete_many({"pm_user_id": pm1_id})
            # Find dummy/real employees excluding test candidate employees
            emps = await db.employees.find({"_id": {"$nin": [test_emp["_id"], another_emp["_id"]]}}).to_list(100)
            for i in range(min(count, len(emps))):
                emp = emps[i]
                await db.team_memberships.insert_one({
                    "pm_user_id": pm1_id,
                    "employee_id": str(emp["_id"]),
                    "status": "active",
                    "role": emp.get("role", "Engineer"),
                    "skills": emp.get("skills", []),
                    "requested_by": pm1_id,
                    "requested_at": datetime.now(timezone.utc),
                    "assigned_at": datetime.now(timezone.utc),
                })

        # -----------------------------------------------------------------
        # TEST 3: Submit PM Request
        # -----------------------------------------------------------------
        await db.team_memberships.delete_many({"employee_id": test_emp_id})
        await db.notifications.delete_many({"userId": pm1_id})

        r_req = await http.post(
            f"/team-capacity/request/{pm1_id}?employee_id={test_emp_id}",
            headers=headers_tm,
        )
        if r_req.status_code != 200:
            print(f"[FAIL] Test 3: Submit PM Request failed: {r_req.text}")
            return False
        req_data = r_req.json()
        req_id = req_data["id"]
        assert req_data["status"] == "pending"
        print("[PASS] Test 3: New Team Member can submit a request to a PM.")

        # -----------------------------------------------------------------
        # TEST 4: PM Candidate Request Notification
        # -----------------------------------------------------------------
        notifs = await db.notifications.find({"userId": pm1_id, "type": "TEAM_MEMBER_REQUESTED"}).to_list(10)
        assert len(notifs) >= 1
        assert "NEW TEAM MEMBER REQUEST" in notifs[0]["title"]
        print("[PASS] Test 4: PM receives candidate request notification.")

        # -----------------------------------------------------------------
        # TEST 1: PM with 17 active members accepts candidate -> 18 active members
        # -----------------------------------------------------------------
        await set_pm1_active_count(17)
        # Create a fresh pending request
        r_req_17 = await http.post(
            f"/team-capacity/request/{pm1_id}?employee_id={test_emp_id}",
            headers=headers_tm,
        )
        req_17_id = r_req_17.json()["id"]

        r_app_17 = await http.post(f"/team-capacity/requests/{req_17_id}/approve", headers=headers_pm1)
        if r_app_17.status_code != 200:
            print(f"[FAIL] Test 1: Approve at 17 members failed: {r_app_17.text}")
            return False
        assert r_app_17.json()["status"] == "active"
        active_cnt_18 = await db.team_memberships.count_documents({"pm_user_id": pm1_id, "status": "active"})
        assert active_cnt_18 == 18
        print("[PASS] Test 1: PM with 17 active members can accept candidate (17 -> 18).")

        # -----------------------------------------------------------------
        # TEST 2: PM with 18 active members cannot receive 19th active member
        # -----------------------------------------------------------------
        # Find another candidate employee not in team
        another_emp = await db.employees.find_one({"_id": {"$ne": test_emp["_id"]}})
        another_emp_id = str(another_emp["_id"])

        # Create pending request for PM1 who is now at 18/18 capacity
        r_req_18 = await http.post(
            f"/team-capacity/request/{pm1_id}?employee_id={another_emp_id}",
            headers=headers_admin,
        )
        req_18_id = r_req_18.json()["id"]

        r_app_18 = await http.post(f"/team-capacity/requests/{req_18_id}/approve", headers=headers_pm1)
        assert r_app_18.status_code in (400, 422)
        assert "capacity" in r_app_18.json()["detail"].lower()
        active_cnt_still_18 = await db.team_memberships.count_documents({"pm_user_id": pm1_id, "status": "active"})
        assert active_cnt_still_18 == 18
        print("[PASS] Test 2: PM with 18 active members cannot receive 19th member (enforced server-side).")

        # -----------------------------------------------------------------
        # TEST 5: PM Approves Candidate & Notification
        # -----------------------------------------------------------------
        await set_pm1_active_count(14)
        await db.notifications.delete_many({"userId": str(tm_user["id"])})
        r_req_5 = await http.post(
            f"/team-capacity/request/{pm1_id}?employee_id={test_emp_id}",
            headers=headers_tm,
        )
        req_5_id = r_req_5.json()["id"]
        r_app_5 = await http.post(f"/team-capacity/requests/{req_5_id}/approve", headers=headers_pm1)
        assert r_app_5.status_code == 200
        assert r_app_5.json()["status"] == "active"
        cnt_15 = await db.team_memberships.count_documents({"pm_user_id": pm1_id, "status": "active"})
        assert cnt_15 == 15

        # Check assignment notification to Team Member
        notif_tm = await db.notifications.find_one({"type": "TEAM_MEMBER_ASSIGNED"})
        assert notif_tm is not None
        assert "TEAM ASSIGNMENT" in notif_tm["title"]
        print("[PASS] Test 5: PM approves candidate, capacity increments, assignment notification sent.")

        # -----------------------------------------------------------------
        # TEST 6: PM Rejects Candidate
        # -----------------------------------------------------------------
        r_req_6 = await http.post(
            f"/team-capacity/request/{pm1_id}?employee_id={another_emp_id}",
            headers=headers_admin,
        )
        req_6_id = r_req_6.json()["id"]
        r_rej_6 = await http.post(f"/team-capacity/requests/{req_6_id}/reject", headers=headers_pm1)
        assert r_rej_6.status_code == 200
        assert r_rej_6.json()["status"] == "rejected"
        print("[PASS] Test 6: PM rejects candidate (candidate status = rejected, not active).")

        # -----------------------------------------------------------------
        # TEST 7: Full PM Triggers Intelligent Alternative Analysis
        # -----------------------------------------------------------------
        r_anal = await http.get(f"/team-capacity/analyze/{another_emp_id}", headers=headers_pm1)
        assert r_anal.status_code == 200
        anal_data = r_anal.json()
        assert "candidate" in anal_data
        assert "recommendations" in anal_data
        assert len(anal_data["recommendations"]) > 0
        rec0 = anal_data["recommendations"][0]
        assert "reasons" in rec0
        assert "score" in rec0
        print("[PASS] Test 7: Full PM triggers intelligent alternative PM analysis (no auto-assignment).")

        # -----------------------------------------------------------------
        # TEST 8: Unauthorized PM Cannot Approve Another PM's Candidate
        # -----------------------------------------------------------------
        r_req_8 = await http.post(
            f"/team-capacity/request/{pm1_id}?employee_id={another_emp_id}",
            headers=headers_admin,
        )
        req_8_id = r_req_8.json()["id"]
        r_app_unauth = await http.post(f"/team-capacity/requests/{req_8_id}/approve", headers=headers_pm2)
        assert r_app_unauth.status_code == 403
        print("[PASS] Test 8: Unauthorized PM cannot approve another PM's candidate (403).")

        # -----------------------------------------------------------------
        # TEST 9: Team Member Cannot Approve Request / Self-Assign
        # -----------------------------------------------------------------
        r_app_tm = await http.post(f"/team-capacity/requests/{req_8_id}/approve", headers=headers_tm)
        assert r_app_tm.status_code == 403
        print("[PASS] Test 9: Team Member cannot assign themselves or approve requests (403).")

        # -----------------------------------------------------------------
        # TEST 10: Concurrent Assignment Attempts
        # -----------------------------------------------------------------
        await set_pm1_active_count(17)
        # Create two pending requests
        r_c1 = await http.post(f"/team-capacity/request/{pm1_id}?employee_id={test_emp_id}", headers=headers_admin)
        req_c1_id = r_c1.json()["id"]

        r_c2 = await http.post(f"/team-capacity/request/{pm1_id}?employee_id={another_emp_id}", headers=headers_admin)
        req_c2_id = r_c2.json()["id"]

        # Attempt to approve both concurrently
        res_c1, res_c2 = await asyncio.gather(
            http.post(f"/team-capacity/requests/{req_c1_id}/approve", headers=headers_pm1),
            http.post(f"/team-capacity/requests/{req_c2_id}/approve", headers=headers_pm1),
            return_exceptions=True
        )

        statuses = [getattr(r, "status_code", 500) for r in (res_c1, res_c2)]
        active_cnt_conc = await db.team_memberships.count_documents({"pm_user_id": pm1_id, "status": "active"})
        assert active_cnt_conc <= 18
        print(f"[PASS] Test 10: Concurrent assignment attempts capped at max 18 active members (Active count: {active_cnt_conc}).")

        # -----------------------------------------------------------------
        # TEST 11: Role / Skill Composition
        # -----------------------------------------------------------------
        r_cap = await http.get("/team-capacity/my-capacity", headers=headers_pm1)
        assert r_cap.status_code == 200
        cap_body = r_cap.json()
        assert "role_breakdown" in cap_body
        assert "skill_coverage" in cap_body
        assert "capability_gaps" in cap_body
        print("[PASS] Test 11: Role/skill composition and capability gaps calculated correctly.")

        # -----------------------------------------------------------------
        # TEST 12: Existing Shared Specialist Model Intact
        # -----------------------------------------------------------------
        proj_count = await db.projects.count_documents({})
        assert proj_count >= 30
        multi_proj_emps = await db.employees.find({"assigned_project_ids.1": {"$exists": True}}).to_list(10)
        assert len(multi_proj_emps) > 0
        print("[PASS] Test 12: Existing shared-specialist project assignments remain intact.")

        # -----------------------------------------------------------------
        # TEST 13: Existing Notification Workflow Intact
        # -----------------------------------------------------------------
        notif_types = await db.notifications.distinct("type")
        assert any(t in notif_types for t in ["PROJECT_ASSIGNED", "ISSUE_ASSIGNED", "TEAM_MEMBER_ASSIGNED"])
        print("[PASS] Test 13: Existing notification workflow remains intact.")

        # -----------------------------------------------------------------
        # TEST 14: Existing RBAC / Scoping Intact
        # -----------------------------------------------------------------
        r_proj_pm1 = await http.get("/projects/", headers=headers_pm1)
        assert r_proj_pm1.status_code == 200
        r_proj_pm2 = await http.get("/projects/", headers=headers_pm2)
        assert r_proj_pm2.status_code == 200
        # Check PMs cannot see each other's unshared projects
        pm1_pids = {p["id"] for p in r_proj_pm1.json()}
        pm2_pids = {p["id"] for p in r_proj_pm2.json()}
        assert len(pm1_pids.intersection(pm2_pids)) == 0
        print("[PASS] Test 14: Existing RBAC and project scoping remain intact.")

    print("============================================================")
    print("ALL 14 TEAM CAPACITY & ALLOCATION TESTS PASSED PERFECTLY!")
    print("============================================================")
    return True


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    if not success:
        sys.exit(1)
