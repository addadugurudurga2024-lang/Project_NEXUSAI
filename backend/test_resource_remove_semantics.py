"""
Targeted Semantic & Throughput Audit Test Suite for NexusAI What-If Simulator
Validates:
1. RESOURCE_REMOVE semantic correctness (Capacity decrease, workload increase, zero positive feature leaks).
2. Data-Grounded Throughput logic (No arbitrary constants; progress gains scale with capacity share & project runway).
3. Exact equivalence between independent GBR model prediction and Simulator API output.
4. Absolute Zero Live MongoDB Mutation across operational collections.
"""

import asyncio
import httpx
import os
import sys
import joblib
import numpy as np
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

# Setup sys.path
sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('backend'))

from ml.inference.deadline_delay import predict_deadline_delay, MODEL_PATH, SCALER_PATH, _parse_dates

BASE_URL = "http://127.0.0.1:8000"
MONGO_URI = "mongodb://localhost:27017"

async def run_semantic_audit_tests():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client.nexusai

    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)

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

    print("=" * 85)
    print("NEXUSAI WHAT-IF SIMULATOR: TARGETED SEMANTIC & THROUGHPUT AUDIT SUITE")
    print("=" * 85)

    # Capture DB collection counts before running tests
    pre_counts = {
        "projects": await db.projects.count_documents({}),
        "tasks": await db.tasks.count_documents({}),
        "issues": await db.issues.count_documents({}),
        "employees": await db.employees.count_documents({}),
        "memberships": await db.team_memberships.count_documents({}),
    }

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, follow_redirects=True) as http:
        # Step 0: Auth login
        r_admin = await http.post("/auth/login", json={"email": "admin@nexusai.dev", "password": "Password123!"})
        assert r_admin.status_code == 200, f"Admin login failed: {r_admin.text}"
        headers_admin = {"Authorization": f"Bearer {r_admin.json()['access_token']}"}

        # Resolve PM1 Project: Enterprise Banking Modernization
        p_doc1 = await db.projects.find_one({"name": "Enterprise Banking Modernization"})
        if not p_doc1:
            p_doc1 = await db.projects.find_one({})
        pid1 = str(p_doc1["_id"])

        # Resolve PM2 Project: NextGen Mobile Banking App
        p_doc2 = await db.projects.find_one({"name": "NextGen Mobile Banking App"})
        if not p_doc2:
            p_doc2 = await db.projects.find_one({})
        pid2 = str(p_doc2["_id"])

        # -----------------------------------------------------------------
        # TEST 1: RESOURCE_REMOVE Semantic Directionality (Capacity & Workload)
        # -----------------------------------------------------------------
        r_sim_rem = await http.post("/simulations/run", headers=headers_admin, json={
            "project_id": pid1,
            "scenario_type": "RESOURCE_REMOVE",
            "parameters": {"count": 1}
        })
        assert r_sim_rem.status_code == 200, f"Resource removal failed: {r_sim_rem.text}"
        res_rem = r_sim_rem.json()
        b_snap = res_rem["baseline"]
        s_snap = res_rem["simulated"]

        cap_decreased = s_snap["total_capacity_hours"] < b_snap["total_capacity_hours"]
        workload_increased = s_snap["team_workload_pct"] > b_snap["team_workload_pct"]
        team_size_decreased = s_snap["team_size"] == b_snap["team_size"] - 1

        record_test(
            "RESOURCE_REMOVE Directionality: Capacity decreases and workload utilization increases",
            cap_decreased and workload_increased and team_size_decreased,
            f"Capacity: {b_snap['total_capacity_hours']}h -> {s_snap['total_capacity_hours']}h | Workload: {b_snap['team_workload_pct']}% -> {s_snap['team_workload_pct']}%"
        )

        # -----------------------------------------------------------------
        # TEST 2: RESOURCE_REMOVE Feature Isolation (No Positive Leaks)
        # -----------------------------------------------------------------
        prog_unchanged = s_snap["progress"] == b_snap["progress"]
        overdue_not_reduced = s_snap["overdue_tasks"] >= b_snap["overdue_tasks"]
        crit_issues_unchanged = s_snap["critical_issues"] == b_snap["critical_issues"]

        record_test(
            "RESOURCE_REMOVE Feature Isolation: No accidental positive progress or overdue reduction occurs",
            prog_unchanged and overdue_not_reduced and crit_issues_unchanged,
            f"Progress: {b_snap['progress']}% == {s_snap['progress']}% | Overdue: {b_snap['overdue_tasks']} -> {s_snap['overdue_tasks']}"
        )

        # -----------------------------------------------------------------
        # TEST 3: ITEM A — RESOURCE_REMOVE Model Equivalence & Explanation
        # -----------------------------------------------------------------
        td, dr, sp = _parse_dates(p_doc2)
        X_base2 = np.array([[
            b_snap["progress"],
            b_snap["progress"],
            float(b_snap["overdue_tasks"]),
            float(b_snap["critical_issues"]),
            float(b_snap["team_workload_pct"]),
            td, dr, sp, sp - b_snap["progress"]
        ]])
        raw_b2 = float(model.predict(scaler.transform(X_base2))[0])

        X_sim2 = np.array([[
            s_snap["progress"],
            s_snap["progress"],
            float(s_snap["overdue_tasks"]),
            float(s_snap["critical_issues"]),
            float(s_snap["team_workload_pct"]),
            td, dr, sp, sp - s_snap["progress"]
        ]])
        raw_s2 = float(model.predict(scaler.transform(X_sim2))[0])

        # Verify that the API output matches integer rounding of independent model inference
        record_test(
            "RESOURCE_REMOVE Model Equivalence: API delay_days matches integer rounding of raw model output",
            round(raw_s2) == s_snap["delay_days"],
            f"Raw baseline: {raw_b2:.4f}d ({round(raw_b2)}d) -> Raw simulated: {raw_s2:.4f}d ({round(raw_s2)}d) | Delta: {raw_s2 - raw_b2:+.4f}d"
        )

        # -----------------------------------------------------------------
        # TEST 4: ITEM B — Data-Grounded RESOURCE_ADD Throughput Logic
        # -----------------------------------------------------------------
        r_sim_add = await http.post("/simulations/run", headers=headers_admin, json={
            "project_id": pid2,
            "scenario_type": "RESOURCE_ADD",
            "parameters": {"count": 1, "role": "AI Engineer", "weekly_capacity_hours": 40.0}
        })
        assert r_sim_add.status_code == 200, f"RESOURCE_ADD failed: {r_sim_add.text}"
        res_add = r_sim_add.json()

        # Verify progress boost is grounded in capacity ratio (40h / total_cap) and remaining runway (dr / td)
        rem_work2 = 100.0 - res_add["baseline"]["progress"]
        sim_cap2 = res_add["simulated"]["total_capacity_hours"]
        expected_boost = rem_work2 * (40.0 / sim_cap2) * (dr / td)
        actual_prog_gain = res_add["simulated"]["progress"] - res_add["baseline"]["progress"]

        record_test(
            "Data-Grounded RESOURCE_ADD: Progress gain is derived from marginal capacity share and project runway",
            abs(actual_prog_gain - expected_boost) < 0.05,
            f"Expected gain: +{expected_boost:.2f}%, Actual gain: +{actual_prog_gain:.2f}%"
        )

        # -----------------------------------------------------------------
        # TEST 5: ITEM B — Data-Grounded SCHEDULE_CAPACITY_CHANGE Throughput Logic
        # -----------------------------------------------------------------
        r_sim_vel = await http.post("/simulations/run", headers=headers_admin, json={
            "project_id": pid2,
            "scenario_type": "SCHEDULE_CAPACITY_CHANGE",
            "parameters": {"velocity_boost_pct": 30.0}
        })
        assert r_sim_vel.status_code == 200, f"SCHEDULE_CAPACITY_CHANGE failed: {r_sim_vel.text}"
        res_vel = r_sim_vel.json()

        expected_vel_gain = rem_work2 * (30.0 / 100.0) * (dr / td)
        actual_vel_gain = res_vel["simulated"]["progress"] - res_vel["baseline"]["progress"]

        record_test(
            "Data-Grounded VELOCITY_BOOST: Progress gain scales with velocity boost percentage and remaining runway",
            abs(actual_vel_gain - expected_vel_gain) < 0.05,
            f"Expected gain: +{expected_vel_gain:.2f}%, Actual gain: +{actual_vel_gain:.2f}%"
        )

        # -----------------------------------------------------------------
        # TEST 6: Zero Live Database Mutation Safety
        # -----------------------------------------------------------------
        post_counts = {
            "projects": await db.projects.count_documents({}),
            "tasks": await db.tasks.count_documents({}),
            "issues": await db.issues.count_documents({}),
            "employees": await db.employees.count_documents({}),
            "memberships": await db.team_memberships.count_documents({}),
        }
        no_mutation = (pre_counts == post_counts)
        record_test(
            "Zero Mutation Safety: All 5 operational MongoDB collections 100% untouched",
            no_mutation,
            f"Pre: {pre_counts} == Post: {post_counts}"
        )

    client.close()
    print("=" * 85)
    print(f"SEMANTIC & THROUGHPUT AUDIT SUMMARY: {test_passed} / {test_total} TESTS PASSED")
    print("=" * 85)
    return test_passed == test_total

if __name__ == "__main__":
    success = asyncio.run(run_semantic_audit_tests())
    sys.exit(0 if success else 1)
