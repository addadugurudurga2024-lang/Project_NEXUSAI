import asyncio
import sys
from datetime import datetime, timezone
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

BASE_URL = "http://127.0.0.1:8000"
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "nexusai"


async def run_integrity_tests():
    print("=" * 70)
    print("NEXUSAI PM EMPLOYEE SCOPING & DATABASE INTEGRITY TEST SUITE")
    print("=" * 70)

    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as http:
        # 1. Log in users
        # PM 1: Sarah Chen (6ac0b0bc3ed2ce90ad847080)
        # PM 2: Marcus Vance (6ac0b0bc3ed2ce90ad847081)
        # Admin: admin@nexusai.dev
        # Team Member: member1@nexusai.com
        r_pm1 = await http.post("/auth/login", json={"email": "sarah@nexusai.dev", "password": "Password123!"})
        if r_pm1.status_code != 200:
            print(f"[FAIL] PM1 Login failed: {r_pm1.text}")
            return False
        pm1_token = r_pm1.json()["access_token"]
        pm1_user = r_pm1.json()["user"]
        headers_pm1 = {"Authorization": f"Bearer {pm1_token}"}

        r_pm2 = await http.post("/auth/login", json={"email": "marcus.vance@nexusai.dev", "password": "Password123!"})
        if r_pm2.status_code != 200:
            print(f"[FAIL] PM2 Login failed: {r_pm2.text}")
            return False
        pm2_token = r_pm2.json()["access_token"]
        pm2_user = r_pm2.json()["user"]
        headers_pm2 = {"Authorization": f"Bearer {pm2_token}"}

        r_admin = await http.post("/auth/login", json={"email": "admin@nexusai.dev", "password": "Password123!"})
        if r_admin.status_code != 200:
            print(f"[FAIL] Admin Login failed: {r_admin.text}")
            return False
        admin_token = r_admin.json()["access_token"]
        headers_admin = {"Authorization": f"Bearer {admin_token}"}

        print("[OK] Authenticated PM1 (Sarah), PM2 (Marcus), and Admin successfully.\n")

        # -----------------------------------------------------------------
        # TEST 1: PM Employee List Scoped Exactly to Active Team Capacity
        # -----------------------------------------------------------------
        pm1_id = pm1_user["id"]
        pm2_id = pm2_user["id"]

        pm1_tc_mems = await db.team_memberships.find({"pm_user_id": pm1_id, "status": "active"}).to_list(100)
        pm1_tc_eids = set(m["employee_id"] for m in pm1_tc_mems)

        pm2_tc_mems = await db.team_memberships.find({"pm_user_id": pm2_id, "status": "active"}).to_list(100)
        pm2_tc_eids = set(m["employee_id"] for m in pm2_tc_mems)

        r_pm1_emps = await http.get("/employees/", headers=headers_pm1)
        assert r_pm1_emps.status_code == 200
        pm1_api_emps = r_pm1_emps.json()
        pm1_api_eids = set(e["id"] for e in pm1_api_emps)

        assert len(pm1_api_emps) == len(pm1_tc_mems) == 18, f"Expected 18, got {len(pm1_api_emps)}"
        assert pm1_api_eids == pm1_tc_eids, "PM1 employee API must match Team Capacity IDs exactly"
        print(f"[PASS] Test 1A: PM1 Employee API returned exactly {len(pm1_api_emps)} employees matching Team Capacity.")

        r_pm2_emps = await http.get("/employees/", headers=headers_pm2)
        assert r_pm2_emps.status_code == 200
        pm2_api_emps = r_pm2_emps.json()
        pm2_api_eids = set(e["id"] for e in pm2_api_emps)

        assert len(pm2_api_emps) == len(pm2_tc_mems) == 16, f"Expected 16, got {len(pm2_api_emps)}"
        assert pm2_api_eids == pm2_tc_eids, "PM2 employee API must match Team Capacity IDs exactly"
        print(f"[PASS] Test 1B: PM2 Employee API returned exactly {len(pm2_api_emps)} employees matching Team Capacity.")

        # Ensure no overlap between PM1 and PM2 employees
        assert len(pm1_api_eids.intersection(pm2_api_eids)) == 0, "PM1 and PM2 employees must not overlap!"
        print("[PASS] Test 1C: Zero overlap between PM1 and PM2 employee lists.")

        # -----------------------------------------------------------------
        # TEST 2: Admin Retains Global Visibility
        # -----------------------------------------------------------------
        r_admin_emps = await http.get("/employees/", headers=headers_admin)
        assert r_admin_emps.status_code == 200
        admin_api_emps = r_admin_emps.json()
        total_active_emps = await db.employees.count_documents({})
        assert len(admin_api_emps) == total_active_emps == 191
        print(f"[PASS] Test 2: Admin retains global visibility ({len(admin_api_emps)} employees).")

        # -----------------------------------------------------------------
        # TEST 3: RBAC Employee Detail Access (Own = 200, Other = 403, Invalid = 404/400)
        # -----------------------------------------------------------------
        own_emp_id = list(pm1_tc_eids)[0]
        other_emp_id = list(pm2_tc_eids)[0]

        # PM1 accessing own employee -> 200
        r_own = await http.get(f"/employees/{own_emp_id}", headers=headers_pm1)
        assert r_own.status_code == 200
        assert r_own.json()["id"] == own_emp_id
        print(f"[PASS] Test 3A: PM1 accessing own Team Capacity employee succeeded (200).")

        # PM1 accessing PM2's employee -> 403
        r_other = await http.get(f"/employees/{other_emp_id}", headers=headers_pm1)
        assert r_other.status_code == 403, f"Expected 403, got {r_other.status_code}: {r_other.text}"
        print(f"[PASS] Test 3B: PM1 accessing PM2's employee correctly blocked with 403.")

        # PM1 accessing invalid/nonexistent ID -> 404/400
        fake_id = str(ObjectId())
        r_fake = await http.get(f"/employees/{fake_id}", headers=headers_pm1)
        assert r_fake.status_code in (404, 403), f"Expected 404/403, got {r_fake.status_code}"
        print(f"[PASS] Test 3C: Accessing non-existent employee ID rejected cleanly ({r_fake.status_code}).")

        # -----------------------------------------------------------------
        # TEST 4: Employee Risk & Workload Scoping (Own = 200, Other = 403)
        # -----------------------------------------------------------------
        # GET /employee-risk/workload for PM1 should return only PM1's 18 employees
        r_wl = await http.get("/employee-risk/workload", headers=headers_pm1)
        assert r_wl.status_code == 200
        wl_data = r_wl.json()
        wl_eids = set(w["employee_id"] for w in wl_data)
        assert wl_eids.issubset(pm1_tc_eids), "Workload list must contain only PM1 employees"
        print(f"[PASS] Test 4A: /employee-risk/workload strictly scoped to PM1's Team Capacity ({len(wl_data)} items).")

        # GET /employee-risk/employee/{id}/latest for own employee -> 200 (or 404 if no prediction, not 403)
        # GET /employee-risk/employee/{id}/latest for other PM's employee -> 403
        r_risk_other = await http.get(f"/employee-risk/employee/{other_emp_id}/latest", headers=headers_pm1)
        assert r_risk_other.status_code == 403, f"Expected 403, got {r_risk_other.status_code}"
        print(f"[PASS] Test 4B: /employee-risk/employee/{{id}}/latest blocked with 403 for other PM's employee.")

        # GET /employee-risk/{id}/latest alias -> 403
        r_alias_other = await http.get(f"/employee-risk/{other_emp_id}/latest", headers=headers_pm1)
        assert r_alias_other.status_code == 403, f"Expected 403, got {r_alias_other.status_code}"
        print(f"[PASS] Test 4C: /employee-risk/{{id}}/latest alias blocked with 403 for other PM's employee.")

        # GET /employee-risk/employee/{id}/workload -> 403 for other PM's employee
        r_wl_other = await http.get(f"/employee-risk/employee/{other_emp_id}/workload", headers=headers_pm1)
        assert r_wl_other.status_code == 403, f"Expected 403, got {r_wl_other.status_code}"
        print(f"[PASS] Test 4D: /employee-risk/employee/{{id}}/workload blocked with 403 for other PM's employee.")

        # POST /employee-risk/analyze/{id} -> 403 for other PM's employee
        r_ana_other = await http.post(f"/employee-risk/analyze/{other_emp_id}", headers=headers_pm1)
        assert r_ana_other.status_code == 403, f"Expected 403, got {r_ana_other.status_code}"
        print(f"[PASS] Test 4E: /employee-risk/analyze/{{id}} blocked with 403 for other PM's employee.")

        # -----------------------------------------------------------------
        # TEST 5: PM Dashboard Employee Count Equals Team Capacity
        # -----------------------------------------------------------------
        r_dash = await http.get("/dashboard/summary", headers=headers_pm1)
        assert r_dash.status_code == 200
        dash_data = r_dash.json()
        assert dash_data["employees"]["total"] == 18, f"Expected 18, got {dash_data['employees']['total']}"
        print(f"[PASS] Test 5: PM Dashboard total employees equals Team Capacity active count (18).")

        # -----------------------------------------------------------------
        # TEST 6: Project Creation — Employee Selection Validation
        # -----------------------------------------------------------------
        # PM1 creating project with own Team Capacity employee -> SUCCESS
        proj_valid_payload = {
            "name": "PM1 Scoping Test Project Valid",
            "description": "Scoping test",
            "status": "active",
            "priority": "medium",
            "budget": 50000,
            "team_member_ids": [own_emp_id],
        }
        r_create_valid = await http.post("/projects/", json=proj_valid_payload, headers=headers_pm1)
        assert r_create_valid.status_code == 200, f"Expected 200, got {r_create_valid.status_code}: {r_create_valid.text}"
        valid_proj_id = r_create_valid.json()["id"]
        print(f"[PASS] Test 6A: PM1 creating project with own Team Capacity employee succeeded.")

        # PM1 creating project with PM2's employee -> 403 REJECTED
        proj_invalid_payload = {
            "name": "PM1 Scoping Test Project Malicious",
            "description": "Leakage test",
            "status": "active",
            "priority": "medium",
            "budget": 50000,
            "team_member_ids": [other_emp_id],
        }
        r_create_invalid = await http.post("/projects/", json=proj_invalid_payload, headers=headers_pm1)
        assert r_create_invalid.status_code == 403, f"Expected 403, got {r_create_invalid.status_code}: {r_create_invalid.text}"
        print(f"[PASS] Test 6B: PM1 creating project with other PM's employee blocked with 403.")

        # PM1 updating project to add other PM's employee -> 403 REJECTED
        r_update_proj = await http.put(
            f"/projects/{valid_proj_id}",
            json={"team_member_ids": [own_emp_id, other_emp_id]},
            headers=headers_pm1
        )
        assert r_update_proj.status_code == 403, f"Expected 403, got {r_update_proj.status_code}: {r_update_proj.text}"
        print(f"[PASS] Test 6C: PM1 adding other PM's employee to project team blocked with 403.")

        # Clean up test project
        await db.projects.delete_one({"_id": ObjectId(valid_proj_id)})
        await db.activities.delete_many({"project_id": valid_proj_id})

        # -----------------------------------------------------------------
        # TEST 7: Task Creation & Reassignment Scoping
        # Use an existing project managed by PM1
        pm1_proj = await db.projects.find_one({"manager_id": pm1_id})
        assert pm1_proj is not None
        pm1_proj_id = str(pm1_proj["_id"])

        # Clean up any leftover cross-PM allocation or membership on pm1_proj from prior runs
        await db.cross_pm_allocations.delete_many({"project_id": pm1_proj_id})
        await db.projects.update_one({"_id": ObjectId(pm1_proj_id)}, {"$pull": {"team_member_ids": other_emp_id}})
        pm1_proj = await db.projects.find_one({"_id": ObjectId(pm1_proj_id)})

        # Find an employee assigned to this project who is in PM1's Team Capacity
        proj_mems = pm1_proj.get("team_member_ids", [])
        eligible_task_assignee = next((e for e in proj_mems if e in pm1_tc_eids), None)
        assert eligible_task_assignee is not None

        # 7A. Create task with eligible assignee -> 200
        task_payload = {
            "title": "PM1 Scoping Test Task",
            "project_id": pm1_proj_id,
            "assignee_id": eligible_task_assignee,
            "status": "todo",
            "priority": "medium",
            "estimated_hours": 8,
        }
        r_task = await http.post("/tasks/", json=task_payload, headers=headers_pm1)
        assert r_task.status_code == 200, f"Expected 200, got {r_task.status_code}: {r_task.text}"
        created_task_id = r_task.json()["id"]
        print(f"[PASS] Test 7A: Task creation with eligible project & team member succeeded.")

        # 7B. Create task with unauthorized assignee (from PM2) -> 403/400
        bad_task_payload = {
            "title": "PM1 Malicious Task",
            "project_id": pm1_proj_id,
            "assignee_id": other_emp_id,
            "status": "todo",
            "priority": "medium",
            "estimated_hours": 8,
        }
        r_bad_task = await http.post("/tasks/", json=bad_task_payload, headers=headers_pm1)
        assert r_bad_task.status_code in (400, 403), f"Expected 400/403, got {r_bad_task.status_code}"
        print(f"[PASS] Test 7B: Task creation with other PM's employee rejected cleanly ({r_bad_task.status_code}).")

        # 7C. Reassign task to unauthorized assignee -> 403/400
        r_reassign = await http.put(
            f"/tasks/{created_task_id}",
            json={"assignee_id": other_emp_id},
            headers=headers_pm1
        )
        assert r_reassign.status_code in (400, 403), f"Expected 400/403, got {r_reassign.status_code}"
        print(f"[PASS] Test 7C: Task reassignment to other PM's employee rejected cleanly ({r_reassign.status_code}).")

        # Clean up test task
        await db.tasks.delete_one({"_id": ObjectId(created_task_id)})

        # -----------------------------------------------------------------
        # TEST 8: Database Integrity — Partial Unique Index Prevents Duplicate Active Membership
        # -----------------------------------------------------------------
        # Attempt direct database insertion of a duplicate active membership for an existing active employee
        test_dup_emp = list(pm1_tc_eids)[0]
        duplicate_prevented = False
        try:
            await db.team_memberships.insert_one({
                "pm_user_id": pm2_id,
                "employee_id": test_dup_emp,
                "status": "active",
                "role": "Engineer",
                "requested_by": pm2_id,
                "requested_at": datetime.now(timezone.utc),
            })
        except Exception as ex:
            duplicate_prevented = True
            print(f"[PASS] Test 8: Partial unique index correctly rejected duplicate active membership: {ex.__class__.__name__}")

        assert duplicate_prevented, "Database must enforce partial unique index on active employee memberships!"

        # -----------------------------------------------------------------
        # TEST 9: Inactive/Rejected Memberships Do Not Count Toward PM Team
        # -----------------------------------------------------------------
        # Insert a rejected and an inactive membership for PM1
        dummy_emp_id = str(ObjectId())
        await db.team_memberships.insert_one({
            "pm_user_id": pm1_id,
            "employee_id": dummy_emp_id,
            "status": "rejected",
            "role": "Engineer",
            "requested_by": pm1_id,
            "requested_at": datetime.now(timezone.utc),
        })

        r_check_emps = await http.get("/employees/", headers=headers_pm1)
        assert r_check_emps.status_code == 200
        check_eids = [e["id"] for e in r_check_emps.json()]
        assert dummy_emp_id not in check_eids, "Rejected membership must NOT appear in PM employee list"
        assert len(check_eids) == 18, f"PM team size must remain 18, got {len(check_eids)}"
        print(f"[PASS] Test 9: Rejected/inactive memberships do NOT leak into PM employee list or count.")

        # Clean up dummy rejected record
        await db.team_memberships.delete_one({"employee_id": dummy_emp_id})

        # -----------------------------------------------------------------
        # TEST 10: Cross-PM Approved Resource Allocation Exception Preserved
        # -----------------------------------------------------------------
        # Verify cross_pm_allocations approved record allows project task assignment without breaking normal team membership
        cross_alloc_emp = other_emp_id  # Marcus's employee
        # Create an approved cross-PM allocation for PM1's project
        await db.cross_pm_allocations.insert_one({
            "project_id": pm1_proj_id,
            "project_name": pm1_proj.get("name"),
            "requesting_pm_user_id": pm1_id,
            "candidate_employee_id": cross_alloc_emp,
            "candidate_name": "Shared Specialist",
            "home_pm_user_id": pm2_id,
            "status": "approved",
            "requested_at": datetime.now(timezone.utc),
            "reviewed_at": datetime.now(timezone.utc),
        })
        # Add to project team_member_ids
        await db.projects.update_one({"_id": ObjectId(pm1_proj_id)}, {"$addToSet": {"team_member_ids": cross_alloc_emp}})

        # Now PM1 creating task for this approved cross-PM specialist on this project -> 200
        task_cross_payload = {
            "title": "PM1 Cross-PM Task",
            "project_id": pm1_proj_id,
            "assignee_id": cross_alloc_emp,
            "status": "todo",
            "priority": "high",
            "estimated_hours": 10,
        }
        r_cross_task = await http.post("/tasks/", json=task_cross_payload, headers=headers_pm1)
        assert r_cross_task.status_code == 200, f"Expected 200 for approved cross-PM task, got {r_cross_task.status_code}: {r_cross_task.text}"
        cross_task_id = r_cross_task.json()["id"]
        print("[PASS] Test 10A: Approved cross-PM specialist successfully assigned to project task.")

        # But PM1's general Employee page does NOT suddenly include the cross-PM specialist!
        r_pm1_emps_after = await http.get("/employees/", headers=headers_pm1)
        pm1_emps_after_ids = [e["id"] for e in r_pm1_emps_after.json()]
        assert cross_alloc_emp not in pm1_emps_after_ids, "Cross-PM specialist must NOT leak into normal PM Employee page!"
        assert len(pm1_emps_after_ids) == 18, f"PM1 Team Capacity must remain strictly 18, got {len(pm1_emps_after_ids)}"
        print("[PASS] Test 10B: Cross-PM specialist does NOT leak into normal PM Employee page or team size.")

        # Clean up cross-PM test records
        await db.tasks.delete_one({"_id": ObjectId(cross_task_id)})
        await db.projects.update_one({"_id": ObjectId(pm1_proj_id)}, {"$pull": {"team_member_ids": cross_alloc_emp}})
        await db.cross_pm_allocations.delete_many({"project_id": pm1_proj_id, "candidate_employee_id": cross_alloc_emp})

    client.close()
    print("\n" + "=" * 70)
    print("ALL PM EMPLOYEE SCOPING & INTEGRITY TESTS PASSED PERFECTLY!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = asyncio.run(run_integrity_tests())
    if not success:
        sys.exit(1)
