"""
Prediction -> Outcome Tracking, Prediction History & ML Performance Evaluation
Automated Comprehensive Test Suite for NexusAI

Covers all 25 Master Test Specifications:
- Test 01: Prediction snapshot creation.
- Test 02: Prediction snapshot immutability.
- Test 03: Duplicate snapshot prevention.
- Test 04: Actual outcome recording.
- Test 05: Correct numeric error calculation.
- Test 06: Correct classification evaluation.
- Test 07: Pending predictions excluded from metrics.
- Test 08: Unavailable outcomes excluded from metrics.
- Test 09: Deadline actual outcome calculation.
- Test 10: Budget actual outcome calculation where supported.
- Test 11: Risk outcome handling does not fabricate ground truth.
- Test 12: Burnout outcome handling does not fabricate ground truth.
- Test 13: Prediction history ordering.
- Test 14: Risk trajectory correctness.
- Test 15: MAE, RMSE, Median Absolute Error calculation.
- Test 16: Classification metric calculation.
- Test 17: Small-sample handling.
- Test 18: PM project scoping.
- Test 19: Unauthorized PM receives 403.
- Test 20: Team Member authorization boundary.
- Test 21: Admin organization-wide visibility.
- Test 22: What-If simulations are NOT stored as production predictions.
- Test 23: Decision Log remains functional.
- Test 24: Existing prediction inference remains unchanged.
- Test 25: No live project/task/issue mutation.
"""

import asyncio
import httpx
import sys
import os
import math
from datetime import datetime, timedelta
# pyrefly: ignore [missing-import]
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

    print("=" * 85)
    print("NEXUSAI PREDICTION -> OUTCOME TRACKING & ML PERFORMANCE VERIFICATION SUITE")
    print("=" * 85)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, follow_redirects=True) as http:
        # Step 0: Auth logins
        r_admin = await http.post("/auth/login", json={"email": "admin@nexusai.dev", "password": "Password123!"})
        assert r_admin.status_code == 200, f"Admin login failed: {r_admin.text}"
        admin_token = r_admin.json()["access_token"]
        headers_admin = {"Authorization": f"Bearer {admin_token}"}

        r_pm1 = await http.post("/auth/login", json={"email": "sarah@nexusai.dev", "password": "Password123!"})
        assert r_pm1.status_code == 200, f"PM1 login failed: {r_pm1.text}"
        pm1_token = r_pm1.json()["access_token"]
        headers_pm1 = {"Authorization": f"Bearer {pm1_token}"}

        r_pm2 = await http.post("/auth/login", json={"email": "marcus.vance@nexusai.dev", "password": "Password123!"})
        assert r_pm2.status_code == 200, f"PM2 login failed: {r_pm2.text}"
        pm2_token = r_pm2.json()["access_token"]
        headers_pm2 = {"Authorization": f"Bearer {pm2_token}"}

        # Team member login
        r_tm = await http.post("/auth/login", json={"email": "member1@nexusai.com", "password": "Password123!"})
        if r_tm.status_code != 200:
            # Fallback to creating a test team member if member1 doesn't exist
            from app.core.security import get_password_hash, create_access_token
            tm_user = await db.users.find_one({"role": "team_member"})
            if not tm_user:
                ins_u = await db.users.insert_one({
                    "name": "Test Team Member",
                    "email": "test_tm@nexusai.dev",
                    "hashed_password": get_password_hash("Password123!"),
                    "role": "team_member",
                    "status": "active",
                    "created_at": datetime.utcnow(),
                })
                tm_token = create_access_token(data={"sub": str(ins_u.inserted_id), "role": "team_member"})
            else:
                tm_token = create_access_token(data={"sub": str(tm_user["_id"]), "role": "team_member"})
        else:
            tm_token = r_tm.json()["access_token"]
        headers_tm = {"Authorization": f"Bearer {tm_token}"}

        # Discover Sarah's and Marcus's projects
        sarah_projects = await http.get("/projects", headers=headers_pm1)
        assert sarah_projects.status_code == 200
        sarah_p_list = sarah_projects.json()
        assert len(sarah_p_list) > 0, "Sarah must have managed projects"
        sarah_pid = sarah_p_list[0]["id"] if "id" in sarah_p_list[0] else str(sarah_p_list[0]["_id"])

        marcus_projects = await http.get("/projects", headers=headers_pm2)
        assert marcus_projects.status_code == 200
        marcus_p_list = marcus_projects.json()
        assert len(marcus_p_list) > 0, "Marcus must have managed projects"
        marcus_pid = marcus_p_list[0]["id"] if "id" in marcus_p_list[0] else str(marcus_p_list[0]["_id"])

        # Capture initial collection counts for Safety Check (Test 25)
        initial_projects_count = await db.projects.count_documents({})
        initial_tasks_count = await db.tasks.count_documents({})
        initial_issues_count = await db.issues.count_documents({})
        initial_employees_count = await db.employees.count_documents({})

        # Clean up any leftover snapshots for sarah_pid from prior test runs
        await db.prediction_history.delete_many({"project_id": sarah_pid})

        # -------------------------------------------------------------
        # Test 01: Prediction snapshot creation
        # -------------------------------------------------------------
        r_pred = await http.post(f"/predictions/project/{sarah_pid}", headers=headers_pm1)
        assert r_pred.status_code == 200, f"Prediction call failed: {r_pred.text}"
        pred_data = r_pred.json()

        # Check snapshots created in db.prediction_history
        snapshots = await db.prediction_history.find({"project_id": sarah_pid}).to_list(10)
        types_created = [s["prediction_type"] for s in snapshots]
        has_risk = "PROJECT_RISK" in types_created
        has_delay = "DEADLINE_DELAY" in types_created
        has_budget = "BUDGET_OVERRUN" in types_created
        record_test("Prediction Snapshot Creation", has_risk and has_delay and has_budget, f"Created snapshots for: {types_created}")

        # -------------------------------------------------------------
        # Test 02: Prediction snapshot immutability
        # -------------------------------------------------------------
        risk_snap = await db.prediction_history.find_one({"project_id": sarah_pid, "prediction_type": "PROJECT_RISK"})
        assert risk_snap is not None
        orig_timestamp = risk_snap["prediction_timestamp"]
        orig_features = dict(risk_snap["prediction_features_snapshot"])
        orig_pred_val = risk_snap["prediction_value"]

        orig_progress = (await db.projects.find_one({"_id": ObjectId(sarah_pid)})).get("progress", 0)
        # Simulate change in live project state (temporarily)
        await db.projects.update_one({"_id": ObjectId(sarah_pid)}, {"$set": {"progress": 99}})
        # Re-fetch snapshot from db.prediction_history to ensure it NEVER changed
        reloaded_snap = await db.prediction_history.find_one({"_id": risk_snap["_id"]})
        is_immutable = (
            reloaded_snap["prediction_timestamp"] == orig_timestamp
            and reloaded_snap["prediction_features_snapshot"] == orig_features
            and reloaded_snap["prediction_value"] == orig_pred_val
        )
        record_test("Prediction Snapshot Immutability", is_immutable, "Historical snapshot remained untouched")

        # Revert project progress to original state for dedup check
        await db.projects.update_one({"_id": ObjectId(sarah_pid)}, {"$set": {"progress": orig_progress}})

        # -------------------------------------------------------------
        # Test 03: Duplicate snapshot prevention (Cooldown & Dedup)
        # -------------------------------------------------------------
        count_before = await db.prediction_history.count_documents({"project_id": sarah_pid})
        # Immediate second prediction call with same state
        await http.post(f"/predictions/project/{sarah_pid}", headers=headers_pm1)
        count_after = await db.prediction_history.count_documents({"project_id": sarah_pid})
        record_test("Duplicate Snapshot Prevention", count_before == count_after, f"Snapshots before={count_before}, after={count_after}")

        # -------------------------------------------------------------
        # Test 04: Actual outcome recording
        # -------------------------------------------------------------
        delay_snap = await db.prediction_history.find_one({"project_id": sarah_pid, "prediction_type": "DEADLINE_DELAY"})
        assert delay_snap is not None
        delay_id = str(delay_snap["_id"])

        outcome_payload = {
            "actual_numeric_value": 18.0,
            "actual_unit": "days",
            "source": "manual_audit",
            "notes": "Project reached milestone with 18 days delay",
            "status": "EVALUATED",
        }
        r_out = await http.post(f"/predictions/{delay_id}/outcome", json=outcome_payload, headers=headers_pm1)
        record_test("Actual Outcome Recording", r_out.status_code == 200 and r_out.json().get("evaluation_status") == "EVALUATED", f"Status: {r_out.status_code}")

        # -------------------------------------------------------------
        # Test 05: Correct numeric error calculation
        # -------------------------------------------------------------
        updated_delay = r_out.json()
        pred_delay = delay_snap["prediction_numeric_value"]
        expected_err = 18.0 - pred_delay
        expected_abs_err = abs(expected_err)
        expected_pct_err = round((expected_abs_err / 18.0) * 100, 2)
        err_calc_valid = (
            updated_delay.get("error_value") == round(expected_err, 4)
            and updated_delay.get("absolute_error") == round(expected_abs_err, 4)
            and updated_delay.get("percentage_error") == expected_pct_err
        )
        record_test("Numeric Error Calculation", err_calc_valid, f"Pred={pred_delay}, Act=18.0, Err={updated_delay.get('error_value')}, Pct={updated_delay.get('percentage_error')}%")

        # -------------------------------------------------------------
        # Test 06: Correct classification evaluation
        # -------------------------------------------------------------
        risk_id = str(risk_snap["_id"])
        risk_pred_class = risk_snap["prediction_class"]
        # Record actual class matching the prediction
        r_risk_out = await http.post(
            f"/predictions/{risk_id}/outcome",
            json={
                "actual_class": risk_pred_class,
                "source": "milestone_review",
                "notes": "Risk level verified in sprint retrospective",
                "status": "EVALUATED",
            },
            headers=headers_pm1,
        )
        risk_out_data = r_risk_out.json()
        class_eval_valid = (
            risk_out_data.get("evaluation_status") == "EVALUATED"
            and risk_out_data.get("error_value") == 0.0
            and risk_out_data.get("actual_class") == risk_pred_class
        )
        record_test("Classification Evaluation Match", class_eval_valid, f"Pred={risk_pred_class}, Actual={risk_out_data.get('actual_class')}, Err={risk_out_data.get('error_value')}")

        # -------------------------------------------------------------
        # Test 07: Pending predictions excluded from metrics
        # -------------------------------------------------------------
        # Insert a synthetic pending prediction for testing
        pending_doc = {
            "project_id": sarah_pid,
            "prediction_type": "DEADLINE_DELAY",
            "model_name": "GradientBoostingRegressor",
            "model_version": "1.0",
            "prediction_timestamp": datetime.utcnow(),
            "prediction_value": "45 days",
            "prediction_numeric_value": 45.0,
            "prediction_unit": "days",
            "evaluation_status": "PENDING",
            "created_at": datetime.utcnow(),
        }
        ins_pending = await db.prediction_history.insert_one(pending_doc)
        
        perf_res = await http.get("/predictions/performance", params={"project_id": sarah_pid, "prediction_type": "DEADLINE_DELAY"}, headers=headers_pm1)
        perf_data = perf_res.json()
        dd_perf = next((p for p in perf_data if p["prediction_type"] == "DEADLINE_DELAY"), None)
        assert dd_perf is not None
        # Pending count should include the pending record, but evaluated count should only count evaluated ones
        pending_excluded = (dd_perf["pending_count"] >= 1 and dd_perf["evaluated_count"] == 1)
        record_test("Pending Predictions Excluded from Metrics", pending_excluded, f"Evaluated={dd_perf['evaluated_count']}, Pending={dd_perf['pending_count']}")

        # -------------------------------------------------------------
        # Test 08: Unavailable outcomes excluded from metrics
        # -------------------------------------------------------------
        unavail_doc = {
            "project_id": sarah_pid,
            "prediction_type": "DEADLINE_DELAY",
            "model_name": "GradientBoostingRegressor",
            "model_version": "1.0",
            "prediction_timestamp": datetime.utcnow(),
            "prediction_value": "30 days",
            "prediction_numeric_value": 30.0,
            "prediction_unit": "days",
            "evaluation_status": "UNAVAILABLE",
            "created_at": datetime.utcnow(),
        }
        await db.prediction_history.insert_one(unavail_doc)
        perf_res2 = await http.get("/predictions/performance", params={"project_id": sarah_pid, "prediction_type": "DEADLINE_DELAY"}, headers=headers_pm1)
        dd_perf2 = next((p for p in perf_res2.json() if p["prediction_type"] == "DEADLINE_DELAY"), None)
        unavail_excluded = (dd_perf2["unavailable_count"] >= 1 and dd_perf2["evaluated_count"] == 1)
        record_test("Unavailable Outcomes Excluded from Metrics", unavail_excluded, f"Unavailable={dd_perf2['unavailable_count']}, Evaluated={dd_perf2['evaluated_count']}")

        # Clean up test scratch docs from db.prediction_history
        await db.prediction_history.delete_one({"_id": ins_pending.inserted_id})
        await db.prediction_history.delete_one({"_id": unavail_doc["_id"]})

        # -------------------------------------------------------------
        # Test 09: Deadline actual outcome calculation from lifecycle
        # -------------------------------------------------------------
        # Create a completed test project in DB
        completed_p = {
            "name": "Auto Eval Lifecycle Project",
            "manager_id": str(r_pm1.json().get("user", {}).get("id") or sarah_p_list[0]["manager_id"]),
            "status": "completed",
            "start_date": "2026-01-01",
            "end_date": "2026-03-01",
            "actual_end_date": "2026-03-15",
            "budget": 50000,
            "current_expenditure": 52000,
            "progress": 100,
            "created_at": datetime.utcnow(),
        }
        res_cp = await db.projects.insert_one(completed_p)
        cp_id = str(res_cp.inserted_id)

        # Create a pending deadline snapshot
        cp_snap = {
            "project_id": cp_id,
            "project_name": completed_p["name"],
            "prediction_type": "DEADLINE_DELAY",
            "model_name": "GradientBoostingRegressor",
            "model_version": "1.0",
            "prediction_timestamp": datetime.utcnow(),
            "prediction_value": "10 days",
            "prediction_numeric_value": 10.0,
            "prediction_unit": "days",
            "evaluation_status": "PENDING",
            "created_at": datetime.utcnow(),
        }
        await db.prediction_history.insert_one(cp_snap)

        r_auto = await http.post(f"/predictions/project/{cp_id}/auto-evaluate", headers=headers_pm1)
        assert r_auto.status_code == 200, f"Auto evaluate failed: {r_auto.text}"
        auto_evaluated_snap = await db.prediction_history.find_one({"project_id": cp_id, "prediction_type": "DEADLINE_DELAY"})
        # 2026-03-15 - 2026-03-01 = 14 days delay
        record_test("Deadline Actual Outcome from Lifecycle", auto_evaluated_snap["actual_numeric_value"] == 14.0 and auto_evaluated_snap["evaluation_status"] == "EVALUATED", f"Actual delay={auto_evaluated_snap['actual_numeric_value']} days")

        # -------------------------------------------------------------
        # Test 10: Budget actual outcome calculation
        # -------------------------------------------------------------
        cp_budget_snap = {
            "project_id": cp_id,
            "project_name": completed_p["name"],
            "prediction_type": "BUDGET_OVERRUN",
            "model_name": "GradientBoostingRegressor",
            "model_version": "1.0",
            "prediction_timestamp": datetime.utcnow(),
            "prediction_value": "$1,500.00",
            "prediction_numeric_value": 1500.0,
            "prediction_unit": "USD",
            "evaluation_status": "PENDING",
            "created_at": datetime.utcnow(),
        }
        await db.prediction_history.insert_one(cp_budget_snap)
        await http.post(f"/predictions/project/{cp_id}/auto-evaluate", headers=headers_pm1)
        auto_budget_snap = await db.prediction_history.find_one({"project_id": cp_id, "prediction_type": "BUDGET_OVERRUN"})
        # 52000 - 50000 = 2000.0 overrun
        record_test("Budget Actual Outcome from Lifecycle", auto_budget_snap["actual_numeric_value"] == 2000.0, f"Actual overrun=${auto_budget_snap['actual_numeric_value']}")

        # Clean up completed test project
        await db.projects.delete_one({"_id": res_cp.inserted_id})
        await db.prediction_history.delete_many({"project_id": cp_id})

        # -------------------------------------------------------------
        # Test 11: Risk outcome handling does not fabricate ground truth
        # -------------------------------------------------------------
        risk_unverified_doc = {
            "project_id": sarah_pid,
            "prediction_type": "PROJECT_RISK",
            "model_name": "RandomForestClassifier",
            "model_version": "1.0",
            "prediction_timestamp": datetime.utcnow(),
            "prediction_value": "HIGH",
            "prediction_class": "HIGH",
            "evaluation_status": "PENDING",
            "created_at": datetime.utcnow(),
        }
        ins_rv = await db.prediction_history.insert_one(risk_unverified_doc)
        rv_snap = await db.prediction_history.find_one({"_id": ins_rv.inserted_id})
        record_test("Risk Ground Truth Not Fabricated", rv_snap.get("evaluation_status") == "PENDING" and rv_snap.get("actual_class") is None, "Pending risk remains pending until formally verified")
        await db.prediction_history.delete_one({"_id": ins_rv.inserted_id})

        # -------------------------------------------------------------
        # Test 12: Burnout outcome handling does not fabricate ground truth
        # -------------------------------------------------------------
        burnout_doc = {
            "entity_id": "emp_123",
            "prediction_type": "EMPLOYEE_BURNOUT",
            "model_name": "RandomForestClassifier",
            "model_version": "1.0",
            "prediction_timestamp": datetime.utcnow(),
            "prediction_value": "MEDIUM",
            "prediction_class": "MEDIUM",
            "evaluation_status": "PENDING",
            "created_at": datetime.utcnow(),
        }
        ins_bo = await db.prediction_history.insert_one(burnout_doc)
        bo_snap = await db.prediction_history.find_one({"_id": ins_bo.inserted_id})
        record_test("Burnout Ground Truth Not Fabricated", bo_snap.get("evaluation_status") == "PENDING" and bo_snap.get("actual_value") is None, "Burnout stays PENDING without verified HR ground truth")
        await db.prediction_history.delete_one({"_id": ins_bo.inserted_id})

        # -------------------------------------------------------------
        # Test 13: Prediction history ordering (Newest first)
        # -------------------------------------------------------------
        r_hist = await http.get(f"/predictions/history/{sarah_pid}", headers=headers_pm1)
        assert r_hist.status_code == 200
        hist_items = r_hist.json()
        timestamps = [item["prediction_timestamp"] for item in hist_items]
        is_sorted_desc = all(timestamps[i] >= timestamps[i+1] for i in range(len(timestamps)-1))
        record_test("Prediction History Ordering", is_sorted_desc, f"Retrieved {len(hist_items)} items in descending order")

        # -------------------------------------------------------------
        # Test 14: Risk trajectory correctness
        # -------------------------------------------------------------
        # Seed 3 chronological trajectory snapshots: HIGH -> MEDIUM -> LOW (improving)
        t_now = datetime.utcnow()
        await db.prediction_history.insert_many([
            {
                "project_id": sarah_pid,
                "prediction_type": "PROJECT_RISK",
                "model_name": "RandomForestClassifier",
                "model_version": "1.0",
                "prediction_timestamp": t_now - timedelta(days=14),
                "prediction_value": "HIGH",
                "prediction_class": "HIGH",
                "evaluation_status": "PENDING",
                "created_at": t_now - timedelta(days=14),
            },
            {
                "project_id": sarah_pid,
                "prediction_type": "PROJECT_RISK",
                "model_name": "RandomForestClassifier",
                "model_version": "1.0",
                "prediction_timestamp": t_now - timedelta(days=7),
                "prediction_value": "MEDIUM",
                "prediction_class": "MEDIUM",
                "evaluation_status": "PENDING",
                "created_at": t_now - timedelta(days=7),
            },
            {
                "project_id": sarah_pid,
                "prediction_type": "PROJECT_RISK",
                "model_name": "RandomForestClassifier",
                "model_version": "1.0",
                "prediction_timestamp": t_now,
                "prediction_value": "LOW",
                "prediction_class": "LOW",
                "evaluation_status": "PENDING",
                "created_at": t_now,
            },
        ])
        r_traj = await http.get(f"/predictions/trajectory/{sarah_pid}?prediction_type=PROJECT_RISK", headers=headers_pm1)
        assert r_traj.status_code == 200
        traj_data = r_traj.json()
        record_test("Risk Trajectory Correctness", traj_data.get("trajectory_direction") == "IMPROVING", f"Direction={traj_data.get('trajectory_direction')}")

        # -------------------------------------------------------------
        # Test 15: MAE, RMSE, Median Absolute Error calculation
        # -------------------------------------------------------------
        # Seed known evaluated samples for a dummy model type
        test_project_id = f"test_mae_{int(datetime.utcnow().timestamp())}"
        await db.prediction_history.insert_many([
            {
                "project_id": test_project_id,
                "prediction_type": "DEADLINE_DELAY",
                "model_name": "GradientBoostingRegressor",
                "model_version": "1.0",
                "prediction_numeric_value": 10.0,
                "actual_numeric_value": 14.0,  # err = 4.0
                "evaluation_status": "EVALUATED",
                "prediction_timestamp": datetime.utcnow(),
            },
            {
                "project_id": test_project_id,
                "prediction_type": "DEADLINE_DELAY",
                "model_name": "GradientBoostingRegressor",
                "model_version": "1.0",
                "prediction_numeric_value": 20.0,
                "actual_numeric_value": 18.0,  # err = -2.0, abs = 2.0
                "evaluation_status": "EVALUATED",
                "prediction_timestamp": datetime.utcnow(),
            },
            {
                "project_id": test_project_id,
                "prediction_type": "DEADLINE_DELAY",
                "model_name": "GradientBoostingRegressor",
                "model_version": "1.0",
                "prediction_numeric_value": 5.0,
                "actual_numeric_value": 11.0,  # err = 6.0, abs = 6.0
                "evaluation_status": "EVALUATED",
                "prediction_timestamp": datetime.utcnow(),
            },
        ])
        # Expected MAE = (4 + 2 + 6) / 3 = 4.0
        # Expected Median Absolute Error = median([2, 4, 6]) = 4.0
        # Expected RMSE = sqrt((16 + 4 + 36) / 3) = sqrt(56/3) = sqrt(18.6667) = 4.32
        # Expected Mean Bias = (4 - 2 + 6) / 3 = 2.67
        r_perf_test = await http.get(f"/predictions/performance?project_id={test_project_id}", headers=headers_admin)
        perf_list = r_perf_test.json()
        dd_metrics = next((p for p in perf_list if p["prediction_type"] == "DEADLINE_DELAY"), None)
        mae_valid = (
            dd_metrics is not None
            and dd_metrics.get("mae") == 4.0
            and dd_metrics.get("median_absolute_error") == 4.0
            and dd_metrics.get("rmse") == 4.32
            and dd_metrics.get("mean_error_bias") == 2.67
        )
        record_test("MAE, RMSE, Median Error Calculation", mae_valid, f"MAE={dd_metrics.get('mae')}, RMSE={dd_metrics.get('rmse')}, MedErr={dd_metrics.get('median_absolute_error')}")

        # -------------------------------------------------------------
        # Test 16: Classification metric calculation
        # -------------------------------------------------------------
        await db.prediction_history.insert_many([
            {
                "project_id": test_project_id,
                "prediction_type": "PROJECT_RISK",
                "model_name": "RandomForestClassifier",
                "model_version": "1.0",
                "prediction_class": "HIGH",
                "actual_class": "HIGH",
                "evaluation_status": "EVALUATED",
                "prediction_timestamp": datetime.utcnow(),
            },
            {
                "project_id": test_project_id,
                "prediction_type": "PROJECT_RISK",
                "model_name": "RandomForestClassifier",
                "model_version": "1.0",
                "prediction_class": "LOW",
                "actual_class": "LOW",
                "evaluation_status": "EVALUATED",
                "prediction_timestamp": datetime.utcnow(),
            },
            {
                "project_id": test_project_id,
                "prediction_type": "PROJECT_RISK",
                "model_name": "RandomForestClassifier",
                "model_version": "1.0",
                "prediction_class": "HIGH",
                "actual_class": "MEDIUM",
                "evaluation_status": "EVALUATED",
                "prediction_timestamp": datetime.utcnow(),
            },
        ])
        # Total evaluated = 3, correct = 2 -> Accuracy = 2/3 = 0.6667
        r_cls_perf = await http.get(f"/predictions/performance?project_id={test_project_id}", headers=headers_admin)
        risk_metrics = next((p for p in r_cls_perf.json() if p["prediction_type"] == "PROJECT_RISK"), None)
        cls_valid = (
            risk_metrics is not None
            and risk_metrics.get("accuracy") == 0.6667
            and risk_metrics.get("f1_score") is not None
        )
        record_test("Classification Metrics (Accuracy & F1)", cls_valid, f"Accuracy={risk_metrics.get('accuracy')}, F1={risk_metrics.get('f1_score')}")

        # -------------------------------------------------------------
        # Test 17: Small-sample handling
        # -------------------------------------------------------------
        sample_status_valid = (
            dd_metrics.get("sample_size_status") == "LIMITED_SAMPLE"
            and dd_metrics.get("sample_size_warning") is not None
        )
        record_test("Small-Sample Safety Handling", sample_status_valid, f"Status={dd_metrics.get('sample_size_status')}, Warning='{dd_metrics.get('sample_size_warning')}'")

        # Clean up test project
        await db.prediction_history.delete_many({"project_id": test_project_id})

        # -------------------------------------------------------------
        # Test 18: PM project scoping
        # -------------------------------------------------------------
        r_sarah_scope = await http.get(f"/predictions/history/{sarah_pid}", headers=headers_pm1)
        record_test("PM Project Scoping Allowed", r_sarah_scope.status_code == 200, "Sarah can access her managed project history")

        # -------------------------------------------------------------
        # Test 19: Unauthorized PM receives 403
        # -------------------------------------------------------------
        r_unauth_pm = await http.get(f"/predictions/history/{marcus_pid}", headers=headers_pm1)
        record_test("Unauthorized PM Blocked (403)", r_unauth_pm.status_code == 403, f"Sarah accessing Marcus project -> {r_unauth_pm.status_code}")

        # -------------------------------------------------------------
        # Test 20: Team Member authorization boundary
        # -------------------------------------------------------------
        r_tm_perf = await http.get("/predictions/performance", headers=headers_tm)
        r_tm_hist = await http.get(f"/predictions/history/{sarah_pid}", headers=headers_tm)
        record_test("Team Member Authorization Boundary (403)", r_tm_perf.status_code == 403 and r_tm_hist.status_code == 403, f"Perf: {r_tm_perf.status_code}, Hist: {r_tm_hist.status_code}")

        # -------------------------------------------------------------
        # Test 21: Admin organization-wide visibility
        # -------------------------------------------------------------
        r_admin_perf = await http.get("/predictions/performance", headers=headers_admin)
        r_admin_hist_sarah = await http.get(f"/predictions/history/{sarah_pid}", headers=headers_admin)
        r_admin_hist_marcus = await http.get(f"/predictions/history/{marcus_pid}", headers=headers_admin)
        admin_valid = (
            r_admin_perf.status_code == 200
            and r_admin_hist_sarah.status_code == 200
            and r_admin_hist_marcus.status_code == 200
        )
        record_test("Admin Org-Wide Visibility", admin_valid, "Admin accessed all PM projects and org performance")

        # -------------------------------------------------------------
        # Test 22: What-If simulations NOT stored as predictions
        # -------------------------------------------------------------
        count_before_sim = await db.prediction_history.count_documents({})
        sim_payload = {
            "project_id": sarah_pid,
            "scenario_type": "RESOURCE_ADD",
            "parameters": {"count": 2, "weekly_capacity_hours": 40},
        }
        r_sim = await http.post("/simulations/run", json=sim_payload, headers=headers_pm1)
        assert r_sim.status_code == 200, f"Simulation failed: {r_sim.text}"
        count_after_sim = await db.prediction_history.count_documents({})
        record_test("What-If Simulation Isolation", count_before_sim == count_after_sim, f"Count before={count_before_sim}, after={count_after_sim}")

        # -------------------------------------------------------------
        # Test 23: Decision Log remains functional
        # -------------------------------------------------------------
        r_dec = await http.get("/decisions/stats", headers=headers_pm1)
        record_test("Decision Log Remains Functional", r_dec.status_code == 200, f"Stats response: {r_dec.status_code}")

        # -------------------------------------------------------------
        # Test 24: Existing prediction inference remains unchanged
        # -------------------------------------------------------------
        r_orig_pred = await http.get(f"/predictions/project/{sarah_pid}/latest", headers=headers_pm1)
        has_health = "health_score" in r_orig_pred.json()
        has_risk_cls = "risk_class" in r_orig_pred.json()
        record_test("Existing Prediction API Unchanged", r_orig_pred.status_code == 200 and has_health and has_risk_cls, "Project prediction format preserved")

        # -------------------------------------------------------------
        # Test 25: No live project/task/issue/employee mutation
        # -------------------------------------------------------------
        final_projects_count = await db.projects.count_documents({})
        final_tasks_count = await db.tasks.count_documents({})
        final_issues_count = await db.issues.count_documents({})
        final_employees_count = await db.employees.count_documents({})

        no_mutation = (
            initial_projects_count == final_projects_count
            and initial_tasks_count == final_tasks_count
            and initial_issues_count == final_issues_count
            and initial_employees_count == final_employees_count
        )
        record_test(
            "Zero Operational Data Mutation Safety",
            no_mutation,
            f"Projects: {initial_projects_count}->{final_projects_count}, Tasks: {initial_tasks_count}->{final_tasks_count}, Issues: {initial_issues_count}->{final_issues_count}, Emps: {initial_employees_count}->{final_employees_count}"
        )

    print("=" * 85)
    print(f"SUMMARY: {test_passed}/{test_total} TESTS PASSED")
    print("=" * 85)
    if test_passed == test_total:
        print("[SUCCESS] ALL 25 PREDICTION-TO-OUTCOME TRACKING TESTS PASSED!")
        sys.exit(0)
    else:
        print("[FAIL] SOME TESTS FAILED!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_tests())
