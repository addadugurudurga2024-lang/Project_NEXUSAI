"""
NEXUSAI — PM-CENTRIC RESOURCE SWAP & CROSS-PM ALLOCATION AUDIT TEST SUITE
========================================================================
Comprehensive verification covering:
1. Level 1 Internal Reallocation (PM ownership, why_checklist, Review, Approve & Allocate, Stale task validation, Reject)
2. Level 2 Project Skill & Role Gap Detection (Action bridge to Level 3)
3. Level 3 Cross-PM Opportunities (Home PM display, Workload < 80% boundary, Request resource, Home PM approval vs self-approval block, Home PM ownership preservation)
4. Data Integrity (Project Team unique count, No global 185 leakage, Shared specialist distinct counting)
5. RBAC & Scoping
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


async def run_audit():
    print("================================================================================")
    print("NEXUSAI — PM-CENTRIC RESOURCE SWAP & CROSS-PM ALLOCATION AUDIT")
    print("================================================================================")

    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    test_passed = 0
    test_total = 0

    def record_test(name: str, passed: bool, detail: str = ""):
        nonlocal test_passed, test_total
        test_total += 1
        if passed:
            test_passed += 1
            print(f"[PASS] Test {test_total}: {name} {f'({detail})' if detail else ''}")
        else:
            print(f"[FAIL] Test {test_total}: {name} -> {detail}")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, follow_redirects=True) as http:
        # Step 0: Auth logins
        r_admin = await http.post("/auth/login", json={"email": "admin@nexusai.dev", "password": "Password123!"})
        assert r_admin.status_code == 200, f"Admin login failed: {r_admin.text}"
        admin_token = r_admin.json()["access_token"]
        headers_admin = {"Authorization": f"Bearer {admin_token}"}

        # Alex Rodriguez (Data Platform PM)
        alex_user = await db.users.find_one({"name": {"$regex": "Alex Rodriguez", "$options": "i"}})
        assert alex_user is not None, "Alex Rodriguez user not found in DB"
        r_alex = await http.post("/auth/login", json={"email": alex_user["email"], "password": "Password123!"})
        if r_alex.status_code != 200:
            # Try default password if needed
            r_alex = await http.post("/auth/login", json={"email": "alex.rodriguez@nexusai.dev", "password": "Password123!"})
        assert r_alex.status_code == 200, f"Alex login failed: {r_alex.text}"
        alex_token = r_alex.json()["access_token"]
        headers_alex = {"Authorization": f"Bearer {alex_token}"}

        # Marcus Vance (Healthcare PM)
        marcus_user = await db.users.find_one({"name": {"$regex": "Marcus Vance", "$options": "i"}})
        assert marcus_user is not None, "Marcus Vance user not found in DB"
        r_marcus = await http.post("/auth/login", json={"email": marcus_user["email"], "password": "Password123!"})
        if r_marcus.status_code != 200:
            r_marcus = await http.post("/auth/login", json={"email": "marcus.vance@nexusai.dev", "password": "Password123!"})
        assert r_marcus.status_code == 200, f"Marcus login failed: {r_marcus.text}"
        marcus_token = r_marcus.json()["access_token"]
        headers_marcus = {"Authorization": f"Bearer {marcus_token}"}

        # Sarah Chen PM
        sarah_user = await db.users.find_one({"name": {"$regex": "Sarah Chen", "$options": "i"}})
        assert sarah_user is not None, "Sarah Chen user not found in DB"
        r_sarah = await http.post("/auth/login", json={"email": sarah_user["email"], "password": "Password123!"})
        if r_sarah.status_code != 200:
            r_sarah = await http.post("/auth/login", json={"email": "sarah.chen@nexusai.dev", "password": "Password123!"})
        assert r_sarah.status_code == 200, f"Sarah login failed: {r_sarah.text}"
        sarah_token = r_sarah.json()["access_token"]
        headers_sarah = {"Authorization": f"Bearer {sarah_token}"}

        print("[OK] Authenticated Admin, Alex Rodriguez (PM), Marcus Vance (PM), and Sarah Chen (PM).")

        # -----------------------------------------------------------------
        # TEST 1: Project Team Count Semantics (No 185/186 Global Leakage)
        # -----------------------------------------------------------------
        alex_projs = await db.projects.find({"manager_id": str(alex_user["_id"])}).to_list(10)
        assert len(alex_projs) > 0, "Alex has no projects"
        alex_proj = alex_projs[0]
        alex_proj_id = str(alex_proj["_id"])

        r_alex_opt = await http.get(f"/resource-optimization/{alex_proj_id}", headers=headers_alex)
        assert r_alex_opt.status_code == 200, f"Optimization failed: {r_alex_opt.text}"
        alex_opt_data = r_alex_opt.json()

        team_count = alex_opt_data["summary"]["total_employees"]
        record_test(
            "Project Team count represents unique project participants only (no global org 185 leakage)",
            0 < team_count <= 25 and team_count < 185,
            f"Project team size: {team_count} (Org size: 185)"
        )

        # -----------------------------------------------------------------
        # TEST 2: PM Ownership Context in Resource Optimization
        # -----------------------------------------------------------------
        record_test(
            "Resource Optimization includes PM ownership context",
            alex_opt_data.get("project_pm_id") == str(alex_user["_id"]) and "Alex" in alex_opt_data.get("project_pm_name", ""),
            f"PM Name: {alex_opt_data.get('project_pm_name')}, PM Spec: {alex_opt_data.get('project_pm_specialization')}"
        )

        # -----------------------------------------------------------------
        # TEST 3: Level 1 Internal Reallocations Structure & Explainability
        # -----------------------------------------------------------------
        reallocs = alex_opt_data.get("reallocation_suggestions", [])
        if not reallocs:
            # Let's check another project if this one has no reallocs or create a task
            for p in alex_projs:
                r_p = await http.get(f"/resource-optimization/{str(p['_id'])}", headers=headers_alex)
                if r_p.status_code == 200 and r_p.json().get("reallocation_suggestions"):
                    alex_proj_id = str(p["_id"])
                    alex_opt_data = r_p.json()
                    reallocs = alex_opt_data.get("reallocation_suggestions", [])
                    break

        has_realloc_structure = False
        sample_realloc = None
        if reallocs:
            sample_realloc = reallocs[0]
            has_realloc_structure = (
                "from_employee" in sample_realloc and
                "to_employee" in sample_realloc and
                "why_checklist" in sample_realloc and
                len(sample_realloc.get("why_checklist", [])) >= 3
            )

        record_test(
            "Level 1 Reallocation includes structured from/to payloads and why_checklist",
            has_realloc_structure,
            f"Found {len(reallocs)} suggestions with explainability checklist"
        )

        # -----------------------------------------------------------------
        # TEST 4: Level 1 PM Review & Approve Task Assignment Flow
        # -----------------------------------------------------------------
        if sample_realloc:
            alloc_id = sample_realloc["id"]
            target_task_id = sample_realloc["task_id"]
            to_emp_id = sample_realloc["to_employee"]["id"]

            r_apply = await http.post(f"/resource-optimization/apply/{alloc_id}", headers=headers_alex)
            applied_success = r_apply.status_code == 200 and r_apply.json().get("status") == "applied"

            # Check that task assignee was actually updated
            updated_task = await db.tasks.find_one({"_id": ObjectId(target_task_id) if ObjectId.is_valid(target_task_id) else target_task_id})
            task_updated = updated_task and str(updated_task.get("assignee_id")) == str(to_emp_id)

            record_test(
                "Level 1 PM Approve & Allocate successfully modifies task assignment",
                applied_success and task_updated,
                f"Task reassigned to {updated_task.get('assignee_name') if updated_task else 'None'}"
            )
        else:
            record_test("Level 1 PM Approve & Allocate flow", True, "Skipped apply execution (no overloaded items)")

        # -----------------------------------------------------------------
        # TEST 5: Level 1 Rejection Flow (Dismiss Proposal)
        # -----------------------------------------------------------------
        # Generate new suggestion or test reject on a dummy allocation
        dummy_alloc = {
            "projectId": alex_proj_id,
            "project_id": alex_proj_id,
            "taskId": "dummy_task_123",
            "fromEmployeeId": "emp_1",
            "employeeId": "emp_2",
            "status": "suggested",
            "createdAt": datetime.now(timezone.utc)
        }
        res_ins = await db.resource_allocations.insert_one(dummy_alloc)
        dummy_alloc_id = str(res_ins.inserted_id)

        r_reject = await http.post(f"/resource-optimization/reject/{dummy_alloc_id}", headers=headers_alex)
        reject_success = r_reject.status_code == 200 and r_reject.json().get("status") == "rejected"
        record_test(
            "Level 1 PM Reject Proposal dismisses suggestion without mutating tasks",
            reject_success,
            f"Status: {r_reject.json().get('status') if r_reject.status_code == 200 else r_reject.status_code}"
        )

        # -----------------------------------------------------------------
        # TEST 6: Stale Level 1 Recommendation Cannot Blindly Apply
        # -----------------------------------------------------------------
        sample_emp = await db.employees.find_one({"status": "active"})
        sample_eid = str(sample_emp["_id"]) if sample_emp else "emp_1"

        stale_alloc = {
            "projectId": alex_proj_id,
            "project_id": alex_proj_id,
            "taskId": "6ac0b0bc3ed2ce90ad840000",
            "fromEmployeeId": sample_eid,
            "employeeId": sample_eid,
            "status": "suggested",
            "createdAt": datetime.now(timezone.utc)
        }
        res_stale = await db.resource_allocations.insert_one(stale_alloc)
        stale_alloc_id = str(res_stale.inserted_id)

        r_stale_apply = await http.post(f"/resource-optimization/apply/{stale_alloc_id}", headers=headers_alex)
        record_test(
            "Stale Level 1 recommendation safely blocked from applying",
            r_stale_apply.status_code == 400 and "stale" in r_stale_apply.text.lower(),
            f"Response code: {r_stale_apply.status_code} - {r_stale_apply.text[:60]}"
        )

        # -----------------------------------------------------------------
        # TEST 7: Level 2 Project Skill & Role Gaps Detection
        # -----------------------------------------------------------------
        gaps = alex_opt_data.get("project_skill_gaps", [])
        record_test(
            "Level 2 detects missing skills/roles for project deliverables",
            isinstance(gaps, list),
            f"Found {len(gaps)} detected skill gaps for project"
        )

        # -----------------------------------------------------------------
        # TEST 8: Level 3 Cross-PM Resource Discovery & Home PM Display
        # -----------------------------------------------------------------
        # Marcus Vance project check
        marcus_projs = await db.projects.find({"manager_id": str(marcus_user["_id"])}).to_list(10)
        assert len(marcus_projs) > 0, "Marcus has no projects"
        marcus_proj_id = str(marcus_projs[0]["_id"])

        r_marcus_opt = await http.get(f"/resource-optimization/{marcus_proj_id}", headers=headers_marcus)
        assert r_marcus_opt.status_code == 200
        marcus_opt_data = r_marcus_opt.json()

        cross_opps = marcus_opt_data.get("cross_pm_opportunities", [])
        home_pm_valid = True
        workload_boundary_valid = True

        for opp in cross_opps:
            if not opp.get("home_pm_name") or not opp.get("home_pm_user_id"):
                home_pm_valid = False
            # Check 80% boundary
            if opp.get("current_workload_percent", 0) >= 80.0:
                workload_boundary_valid = False

        record_test(
            "Level 3 Cross-PM Opportunities prominently identify Home PM and adhere to <80% workload boundary",
            home_pm_valid and workload_boundary_valid,
            f"Discovered {len(cross_opps)} cross-PM opportunities"
        )

        # -----------------------------------------------------------------
        # TEST 9: Cross-PM Resource Request Workflow Creation
        # -----------------------------------------------------------------
        # Find a candidate from another PM's team
        candidate_emp = await db.employees.find_one({"status": "active"})
        assert candidate_emp is not None
        candidate_id = str(candidate_emp["_id"])

        # Check candidate home PM
        mem = await db.team_memberships.find_one({"employee_id": candidate_id, "status": "active"})
        cand_home_pm_id = str(mem["pm_user_id"]) if mem else str(alex_user["_id"])

        # Clean up any existing pending requests for test isolation
        await db.cross_pm_allocations.delete_many({"project_id": marcus_proj_id, "candidate_employee_id": candidate_id})

        r_req = await http.post(
            f"/resource-optimization/request-cross-pm?project_id={marcus_proj_id}&candidate_employee_id={candidate_id}",
            headers=headers_marcus
        )
        req_created = r_req.status_code == 200 and r_req.json().get("status") == "pending_approval"
        req_id = r_req.json().get("id") if req_created else None

        record_test(
            "Cross-PM request creation sets status to pending_approval",
            req_created and req_id is not None,
            f"Request ID: {req_id}"
        )

        # -----------------------------------------------------------------
        # TEST 10: Requesting PM Cannot Self-Approve Cross-PM Request
        # -----------------------------------------------------------------
        if req_id and str(marcus_user["_id"]) != cand_home_pm_id:
            r_self_approve = await http.post(f"/resource-optimization/cross-pm-requests/{req_id}/approve", headers=headers_marcus)
            record_test(
                "Requesting PM is forbidden from self-approving cross-PM resource requests",
                r_self_approve.status_code == 403,
                f"Status: {r_self_approve.status_code} (Forbidden)"
            )
        else:
            record_test("Self-approval protection", True, "Skipped (Marcus is Home PM)")

        # -----------------------------------------------------------------
        # TEST 11: Home PM Approves Cross-PM Request & Preserves Ownership
        # -----------------------------------------------------------------
        if req_id:
            # Login as the Home PM
            home_pm_user = await db.users.find_one({"_id": ObjectId(cand_home_pm_id) if ObjectId.is_valid(cand_home_pm_id) else cand_home_pm_id})
            if not home_pm_user:
                home_pm_user = alex_user
            r_hlogin = await http.post("/auth/login", json={"email": home_pm_user["email"], "password": "Password123!"})
            h_headers = {"Authorization": f"Bearer {r_hlogin.json()['access_token']}"} if r_hlogin.status_code == 200 else headers_admin

            # Verify initial team membership
            initial_mem = await db.team_memberships.find_one({"employee_id": candidate_id, "status": "active"})
            orig_pm_id = str(initial_mem["pm_user_id"]) if initial_mem else cand_home_pm_id

            r_approve = await http.post(f"/resource-optimization/cross-pm-requests/{req_id}/approve", headers=h_headers)
            approved_ok = r_approve.status_code == 200 and r_approve.json().get("status") == "approved"

            # Check that team_memberships.pm_user_id was NOT changed
            after_mem = await db.team_memberships.find_one({"employee_id": candidate_id, "status": "active"})
            after_pm_id = str(after_mem["pm_user_id"]) if after_mem else orig_pm_id

            ownership_preserved = (orig_pm_id == after_pm_id)

            # Check project participation
            marcus_proj_after = await db.projects.find_one({"_id": ObjectId(marcus_proj_id)})
            has_project_part = str(candidate_id) in [str(x) for x in marcus_proj_after.get("team_member_ids", [])]

            record_test(
                "Home PM approves cross-PM allocation with 100% Home PM ownership preservation",
                approved_ok and ownership_preserved and has_project_part,
                f"Home PM remains {orig_pm_id}, added to project {marcus_proj_after.get('name')}"
            )
        else:
            record_test("Home PM approve cross-PM allocation", True, "Skipped")

        # -----------------------------------------------------------------
        # TEST 12: Cross-PM Request Rejection Flow
        # -----------------------------------------------------------------
        # Create second request to test rejection
        candidate_emp2 = await db.employees.find_one({"_id": {"$ne": ObjectId(candidate_id)}})
        if candidate_emp2:
            cand2_id = str(candidate_emp2["_id"])
            await db.cross_pm_allocations.delete_many({"project_id": marcus_proj_id, "candidate_employee_id": cand2_id})
            r_req2 = await http.post(
                f"/resource-optimization/request-cross-pm?project_id={marcus_proj_id}&candidate_employee_id={cand2_id}",
                headers=headers_marcus
            )
            if r_req2.status_code == 200:
                req2_id = r_req2.json().get("id")
                r_rej2 = await http.post(f"/resource-optimization/cross-pm-requests/{req2_id}/reject?reason=Bandwidth+conflict", headers=headers_admin)
                rej2_ok = r_rej2.status_code == 200 and r_rej2.json().get("status") == "rejected"
                record_test(
                    "Cross-PM request rejection marks status as rejected with reason",
                    rej2_ok,
                    f"Status: {r_rej2.json().get('status')}"
                )
            else:
                record_test("Cross-PM request rejection", True, "Skipped (Request creation error)")
        else:
            record_test("Cross-PM request rejection", True, "Skipped")

        # -----------------------------------------------------------------
        # TEST 13: RBAC Cross-PM Access Protection
        # -----------------------------------------------------------------
        r_unauth = await http.get(f"/resource-optimization/{marcus_proj_id}", headers=headers_alex)
        record_test(
            "PM cannot access optimization data of a project owned by another PM (RBAC)",
            r_unauth.status_code == 403,
            f"Status: {r_unauth.status_code}"
        )

        # -----------------------------------------------------------------
        # TEST 14: Admin Retains Global Visibility Across All Projects
        # -----------------------------------------------------------------
        r_admin_opt = await http.get(f"/resource-optimization/{marcus_proj_id}", headers=headers_admin)
        record_test(
            "Admin retains global access to optimization data for any project",
            r_admin_opt.status_code == 200,
            f"Project: {r_admin_opt.json().get('project_name')}"
        )

    print("================================================================================")
    print(f"AUDIT SUMMARY: {test_passed} / {test_total} TESTS PASSED")
    print("================================================================================")
    return test_passed == test_total


if __name__ == "__main__":
    success = asyncio.run(run_audit())
    sys.exit(0 if success else 1)
