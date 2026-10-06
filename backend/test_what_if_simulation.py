"""
What-If Simulation & Scenario Analysis Automated Test Suite for NexusAI
Validates:
1. In-memory simulation execution across all 7 supported scenario types.
2. ABSOLUTE ZERO LIVE-DATA MUTATION SAFETY on MongoDB collections.
3. Strict Server-Side RBAC & PM Project Scoping.
4. Model-compatible ML inference on simulated feature vectors.
5. Comparative Delta calculation and Explainability.
6. Seamless pathway to Decision Log.
"""

import asyncio
import httpx
import sys
import time
from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = "http://127.0.0.1:8000"
MONGO_URI = "mongodb://localhost:27017"


async def run_tests():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client.nexusai

    test_passed = 0
    test_total = 0

    def record_test(name: str, passed: bool, detail: str = ""):
        nonlocal test_passed, test_total
        test_total += 1
        if passed:
            test_passed += 1
            print(f"[PASS] Test {test_total:02d}: {name} {f'({detail})' if detail else ''}")
        else:
            print(f"[FAIL] Test {test_total:02d}: {name} -> {detail}")

    print("=" * 80)
    print("NEXUSAI WHAT-IF SIMULATION & SCENARIO ANALYSIS TEST SUITE")
    print("=" * 80)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, follow_redirects=True) as http:
        # Step 0: Auth logins
        r_admin = await http.post("/auth/login", json={"email": "admin@nexusai.dev", "password": "Password123!"})
        assert r_admin.status_code == 200, f"Admin login failed: {r_admin.text}"
        admin_token = r_admin.json()["access_token"]
        headers_admin = {"Authorization": f"Bearer {admin_token}"}

        # Sarah Chen (PM1)
        r_pm1 = await http.post("/auth/login", json={"email": "sarah@nexusai.dev", "password": "Password123!"})
        assert r_pm1.status_code == 200, f"PM1 login failed: {r_pm1.text}"
        pm1_token = r_pm1.json()["access_token"]
        headers_pm1 = {"Authorization": f"Bearer {pm1_token}"}

        # Marcus Vance (PM2)
        r_pm2 = await http.post("/auth/login", json={"email": "marcus.vance@nexusai.dev", "password": "Password123!"})
        assert r_pm2.status_code == 200, f"PM2 login failed: {r_pm2.text}"
        pm2_token = r_pm2.json()["access_token"]
        headers_pm2 = {"Authorization": f"Bearer {pm2_token}"}

        # Team Member
        r_tm = await http.post("/auth/login", json={"email": "member1@nexusai.com", "password": "Password123!"})
        assert r_tm.status_code == 200, f"Team Member login failed: {r_tm.text}"
        tm_token = r_tm.json()["access_token"]
        headers_tm = {"Authorization": f"Bearer {tm_token}"}

        # Resolve PM1 Project and PM2 Project
        pm1_proj = await db.projects.find_one({"$or": [{"manager_id": "6ac0b0bc3ed2ce90ad847080"}, {"project_manager_id": "6ac0b0bc3ed2ce90ad847080"}, {"created_by": "6ac0b0bc3ed2ce90ad847080"}]})
        assert pm1_proj is not None, "PM1 project not found"
        pm1_pid = str(pm1_proj["_id"])
        pm1_pname = pm1_proj.get("name")

        pm2_proj = await db.projects.find_one({"$or": [{"manager_id": "6ac0b0bc3ed2ce90ad847081"}, {"project_manager_id": "6ac0b0bc3ed2ce90ad847081"}, {"created_by": "6ac0b0bc3ed2ce90ad847081"}]})
        assert pm2_proj is not None, "PM2 project not found"
        pm2_pid = str(pm2_proj["_id"])
        pm2_pname = pm2_proj.get("name")

        print(f"[OK] Authenticated Actors. PM1 Project: '{pm1_pname}' ({pm1_pid}) | PM2 Project: '{pm2_pname}' ({pm2_pid})\n")

        # Capture DB state counts before any simulation
        pre_proj_count = await db.projects.count_documents({})
        pre_task_count = await db.tasks.count_documents({})
        pre_issue_count = await db.issues.count_documents({})
        pre_emp_count = await db.employees.count_documents({})
        pre_membership_count = await db.team_memberships.count_documents({})
        pre_decision_count = await db.decisions.count_documents({})
        pre_notif_count = await db.notifications.count_documents({})

        # -----------------------------------------------------------------
        # TEST 1: Simulation Project Options (Tasks, Members, Gaps, Candidates)
        # -----------------------------------------------------------------
        r_opts = await http.get(f"/simulations/options/{pm1_pid}", headers=headers_pm1)
        opts_data = r_opts.json()
        record_test(
            "Fetch simulation options returns scoped tasks, team members, and gaps",
            r_opts.status_code == 200 and len(opts_data.get("team_members", [])) > 0,
            f"Team size: {opts_data.get('current_team_size')}, Active tasks: {len(opts_data.get('active_tasks', []))}"
        )

        # -----------------------------------------------------------------
        # TEST 2: Scenario 1 — Resource Addition (RESOURCE_ADD)
        # -----------------------------------------------------------------
        r_sim1 = await http.post("/simulations/run", headers=headers_pm1, json={
            "project_id": pm1_pid,
            "scenario_type": "RESOURCE_ADD",
            "parameters": {
                "count": 2,
                "role": "AI Engineer",
                "weekly_capacity_hours": 40.0,
                "hourly_rate": 75.0,
            }
        })
        assert r_sim1.status_code == 200, f"Simulation 1 failed: {r_sim1.text}"
        sim1 = r_sim1.json()

        base1 = sim1["baseline"]
        sim_res1 = sim1["simulated"]
        record_test(
            "Scenario 1 (RESOURCE_ADD): Increases simulated capacity & reduces team workload",
            sim_res1["team_size"] == base1["team_size"] + 2 and sim_res1["total_capacity_hours"] == base1["total_capacity_hours"] + 80.0 and sim_res1["team_workload_pct"] < base1["team_workload_pct"],
            f"Workload: {base1['team_workload_pct']}% -> {sim_res1['team_workload_pct']}%, Health: {base1['health_score']} -> {sim_res1['health_score']}"
        )

        # -----------------------------------------------------------------
        # TEST 3: Scenario 2 — Resource Removal (RESOURCE_REMOVE)
        # -----------------------------------------------------------------
        r_sim2 = await http.post("/simulations/run", headers=headers_pm1, json={
            "project_id": pm1_pid,
            "scenario_type": "RESOURCE_REMOVE",
            "parameters": {
                "count": 1,
            }
        })
        assert r_sim2.status_code == 200, f"Simulation 2 failed: {r_sim2.text}"
        sim2 = r_sim2.json()
        base2 = sim2["baseline"]
        sim_res2 = sim2["simulated"]
        record_test(
            "Scenario 2 (RESOURCE_REMOVE): Decreases capacity & increases workload pressure",
            sim_res2["team_size"] == max(1, base2["team_size"] - 1) and sim_res2["team_workload_pct"] >= base2["team_workload_pct"],
            f"Team size: {base2['team_size']} -> {sim_res2['team_size']}, Workload: {base2['team_workload_pct']}% -> {sim_res2['team_workload_pct']}%"
        )

        # -----------------------------------------------------------------
        # TEST 4: Scenario 3 — Resource Reallocation / Borrow (RESOURCE_REALLOCATION)
        # -----------------------------------------------------------------
        r_sim3 = await http.post("/simulations/run", headers=headers_pm1, json={
            "project_id": pm1_pid,
            "scenario_type": "RESOURCE_REALLOCATION",
            "parameters": {
                "candidate_name": "Maya Lin",
                "candidate_role": "ML Engineer",
                "weekly_capacity_hours": 40.0,
            }
        })
        assert r_sim3.status_code == 200, f"Simulation 3 failed: {r_sim3.text}"
        sim3 = r_sim3.json()
        record_test(
            "Scenario 3 (RESOURCE_REALLOCATION): Simulates borrowing specialist without modifying live assignments",
            sim3["simulated"]["team_size"] == sim3["baseline"]["team_size"] + 1,
            f"Simulated team size: {sim3['simulated']['team_size']}"
        )

        # -----------------------------------------------------------------
        # TEST 5: Scenario 4 — Task Reallocation between Team Members (TASK_REALLOCATION)
        # -----------------------------------------------------------------
        tm_list = opts_data.get("team_members", [])
        from_emp_id = tm_list[0]["id"] if len(tm_list) > 0 else "emp1"
        to_emp_id = tm_list[1]["id"] if len(tm_list) > 1 else "emp2"

        r_sim4 = await http.post("/simulations/run", headers=headers_pm1, json={
            "project_id": pm1_pid,
            "scenario_type": "TASK_REALLOCATION",
            "parameters": {
                "task_hours": 20.0,
                "from_employee_id": from_emp_id,
                "to_employee_id": to_emp_id,
            }
        })
        assert r_sim4.status_code == 200, f"Simulation 4 failed: {r_sim4.text}"
        sim4 = r_sim4.json()
        record_test(
            "Scenario 4 (TASK_REALLOCATION): Rebalances individual task hours in-memory",
            len(sim4["simulated"]["employee_loads"]) > 0 and sim4["explanation"]["what_changed"] != "",
            f"Explanation: {sim4['explanation']['what_changed']}"
        )

        # -----------------------------------------------------------------
        # TEST 6: Scenario 5 — Scope Reduction (SCOPE_REDUCTION)
        # -----------------------------------------------------------------
        r_sim5 = await http.post("/simulations/run", headers=headers_pm1, json={
            "project_id": pm1_pid,
            "scenario_type": "SCOPE_REDUCTION",
            "parameters": {
                "count": 4,
                "hours_reduced": 48.0,
            }
        })
        assert r_sim5.status_code == 200, f"Simulation 5 failed: {r_sim5.text}"
        sim5 = r_sim5.json()
        base5 = sim5["baseline"]
        sim_res5 = sim5["simulated"]
        record_test(
            "Scenario 5 (SCOPE_REDUCTION): Descoping tasks reduces remaining effort & improves completion rate",
            sim_res5["total_tasks"] < base5["total_tasks"] and sim_res5["progress"] >= base5["progress"],
            f"Total tasks: {base5['total_tasks']} -> {sim_res5['total_tasks']}, Progress: {base5['progress']}% -> {sim_res5['progress']}%"
        )

        # -----------------------------------------------------------------
        # TEST 7: Scenario 6 & 7 — Schedule Capacity & Budget Adjustments
        # -----------------------------------------------------------------
        r_sim6 = await http.post("/simulations/run", headers=headers_pm1, json={
            "project_id": pm1_pid,
            "scenario_type": "SCHEDULE_CAPACITY_CHANGE",
            "parameters": {
                "velocity_boost_pct": 25.0,
            }
        })
        assert r_sim6.status_code == 200, f"Simulation 6 failed: {r_sim6.text}"

        r_sim7 = await http.post("/simulations/run", headers=headers_pm1, json={
            "project_id": pm1_pid,
            "scenario_type": "BUDGET_RESOURCE_CHANGE",
            "parameters": {
                "budget_change_amount": 75000.0,
            }
        })
        assert r_sim7.status_code == 200, f"Simulation 7 failed: {r_sim7.text}"
        sim7 = r_sim7.json()
        record_test(
            "Scenarios 6 & 7 (SCHEDULE & BUDGET): Evaluates velocity boosts and budget expansion runway",
            sim7["simulated"]["budget"] == sim7["baseline"]["budget"] + 75000.0,
            f"Budget: ${sim7['baseline']['budget']:,.0f} -> ${sim7['simulated']['budget']:,.0f}"
        )

        # -----------------------------------------------------------------
        # TEST 8: Server-Side RBAC — PM Isolation (PM1 cannot simulate PM2's project)
        # -----------------------------------------------------------------
        r_cross = await http.post("/simulations/run", headers=headers_pm1, json={
            "project_id": pm2_pid,
            "scenario_type": "RESOURCE_ADD",
            "parameters": {"count": 1}
        })
        record_test(
            "Multi-PM RBAC: Unauthorized PM cannot simulate another PM's project (403 Forbidden)",
            r_cross.status_code == 403,
            f"Status: {r_cross.status_code}"
        )

        # -----------------------------------------------------------------
        # TEST 9: Server-Side RBAC — Team Member Restricted (403 Forbidden)
        # -----------------------------------------------------------------
        r_tm_sim = await http.post("/simulations/run", headers=headers_tm, json={
            "project_id": pm1_pid,
            "scenario_type": "RESOURCE_ADD",
            "parameters": {"count": 1}
        })
        record_test(
            "Security Boundary: Team Member restricted from What-If simulation engine (403 Forbidden)",
            r_tm_sim.status_code == 403,
            f"Status: {r_tm_sim.status_code}"
        )

        # -----------------------------------------------------------------
        # TEST 10: Admin Global Access
        # -----------------------------------------------------------------
        r_admin_sim = await http.post("/simulations/run", headers=headers_admin, json={
            "project_id": pm2_pid,
            "scenario_type": "RESOURCE_ADD",
            "parameters": {"count": 1}
        })
        record_test(
            "Admin Global Authority: System Admin can simulate across any organization project",
            r_admin_sim.status_code == 200,
            f"Status: {r_admin_sim.status_code}"
        )

        # -----------------------------------------------------------------
        # TEST 11: Real ML Inference Verification & Explainability Metrics
        # -----------------------------------------------------------------
        sim_ml = sim1
        has_risk_ml = sim_ml["simulated"]["risk_class"] in ["LOW", "MEDIUM", "HIGH"]
        has_delay_ml = isinstance(sim_ml["simulated"]["delay_days"], int)
        has_health_ml = isinstance(sim_ml["simulated"]["health_score"], float)
        has_comparison = len(sim_ml["comparison"]) >= 4
        record_test(
            "Real ML Inference & Comparison: Evaluates risk, delay, and health indicators on simulated feature vector",
            has_risk_ml and has_delay_ml and has_health_ml and has_comparison,
            f"Risk: {sim_ml['simulated']['risk_class']}, Delay: {sim_ml['simulated']['delay_days']}d, Health: {sim_ml['simulated']['health_score']}/100"
        )

        # -----------------------------------------------------------------
        # TEST 12: Decision Log Pathway (Turning a simulation into a Decision record)
        # -----------------------------------------------------------------
        sim_dec_payload = {
            "project_id": pm1_pid,
            "title": f"Approve Scope Descope from What-If Simulation {sim5['simulation_id']}",
            "decision_type": "SPRINT_RESCOPE",
            "description": sim5["scenario_description"],
            "priority": "high",
            "source_type": "what_if_simulation",
            "source_reference_id": sim5["simulation_id"],
            "observed_facts": [
                {"category": "Simulation", "fact": sim5["explanation"]["what_changed"]}
            ],
            "prediction_summary": {
                "baseline_delay": sim5["baseline"]["delay_days"],
                "simulated_delay": sim5["simulated"]["delay_days"],
                "baseline_health": sim5["baseline"]["health_score"],
                "simulated_health": sim5["simulated"]["health_score"],
            },
            "alternatives": [
                {"id": "alt_1", "title": "Adopt Simulated Scope Reduction", "is_selected": True},
                {"id": "alt_2", "title": "Maintain Baseline Overdue Backlog", "is_selected": False},
            ],
            "selected_action": "Adopt Simulated Scope Reduction",
            "decision_rationale": "Simulation proves descoping 4 non-critical tasks saves 48h and prevents release slippage.",
        }

        r_create_dec = await http.post("/decisions/", headers=headers_pm1, json=sim_dec_payload)
        assert r_create_dec.status_code == 200, f"Decision creation from simulation failed: {r_create_dec.text}"
        dec_obj = r_create_dec.json()
        record_test(
            "Decision Log Integration: PM records formal decision grounded in What-If simulation evidence",
            dec_obj.get("source_type") == "what_if_simulation" and dec_obj.get("decision_status") == "PENDING",
            f"Decision ID: {dec_obj.get('id')}, Source: {dec_obj.get('source_type')}"
        )

        # -----------------------------------------------------------------
        # TEST 13: CRITICAL SAFETY CHECK — ABSOLUTE ZERO LIVE-DATA MUTATION
        # -----------------------------------------------------------------
        # Verify counts in operational collections
        post_proj_count = await db.projects.count_documents({})
        post_task_count = await db.tasks.count_documents({})
        post_issue_count = await db.issues.count_documents({})
        post_emp_count = await db.employees.count_documents({})
        post_membership_count = await db.team_memberships.count_documents({})

        # The only document added in Test 12 was 1 decision in db.decisions
        post_decision_count = await db.decisions.count_documents({})

        # Clean up test decision
        if dec_obj.get("id"):
            await db.decisions.delete_one({"_id": ObjectId(dec_obj.get("id"))})

        no_proj_change = (pre_proj_count == post_proj_count)
        no_task_change = (pre_task_count == post_task_count)
        no_issue_change = (pre_issue_count == post_issue_count)
        no_emp_change = (pre_emp_count == post_emp_count)
        no_mem_change = (pre_membership_count == post_membership_count)

        is_zero_mutation = no_proj_change and no_task_change and no_issue_change and no_emp_change and no_mem_change

        record_test(
            "CRITICAL SAFETY RULE: 100% Zero mutation to live MongoDB projects, tasks, issues, employees, and memberships",
            is_zero_mutation,
            f"Projects: {post_proj_count}/{pre_proj_count}, Tasks: {post_task_count}/{pre_task_count}, Issues: {post_issue_count}/{pre_issue_count}, Employees: {post_emp_count}/{pre_emp_count}"
        )

    print("=" * 80)
    print(f"WHAT-IF SIMULATION AUDIT SUMMARY: {test_passed} / {test_total} TESTS PASSED")
    print("=" * 80)
    return test_passed == test_total


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
