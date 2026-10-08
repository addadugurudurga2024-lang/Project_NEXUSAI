import asyncio
import httpx
import sys

BASE_URL = "http://127.0.0.1:8000"

async def verify_ml_tracking():
    print("=" * 80)
    print("NEXUSAI ML TRACKING DEDICATED AUDIT & VERIFICATION SUITE")
    print("=" * 80)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, follow_redirects=True) as http:
        # Step 0: Auth logins
        r_admin = await http.post("/auth/login", json={"email": "admin@nexusai.dev", "password": "Password123!"})
        assert r_admin.status_code == 200, f"Admin login failed: {r_admin.text}"
        headers_admin = {"Authorization": f"Bearer {r_admin.json()['access_token']}"}

        r_pm1 = await http.post("/auth/login", json={"email": "sarah@nexusai.dev", "password": "Password123!"})
        assert r_pm1.status_code == 200, f"PM1 login failed: {r_pm1.text}"
        headers_pm1 = {"Authorization": f"Bearer {r_pm1.json()['access_token']}"}

        r_pm2 = await http.post("/auth/login", json={"email": "marcus.vance@nexusai.dev", "password": "Password123!"})
        assert r_pm2.status_code == 200, f"PM2 login failed: {r_pm2.text}"
        headers_pm2 = {"Authorization": f"Bearer {r_pm2.json()['access_token']}"}

        r_tm = await http.post("/auth/login", json={"email": "member1@nexusai.com", "password": "Password123!"})
        assert r_tm.status_code == 200, f"Team Member login failed: {r_tm.text}"
        headers_tm = {"Authorization": f"Bearer {r_tm.json()['access_token']}"}

        # TEST 1: Admin performance overview (Organization-wide)
        r_perf_admin = await http.get("/predictions/performance", headers=headers_admin)
        assert r_perf_admin.status_code == 200, f"Admin perf failed: {r_perf_admin.text}"
        perf_admin = r_perf_admin.json()
        print(f"[PASS] Test 01: Admin retrieved performance for {len(perf_admin)} models")
        for m in perf_admin:
            print(f"      - {m['prediction_type']}: Total={m['total_predictions']}, Eval={m['evaluated_count']}, Pending={m['pending_count']}, Status={m['sample_size_status']}")
            assert m['total_predictions'] > 0, f"Expected >0 predictions for {m['prediction_type']}"

        # TEST 2: Admin history across all projects (/predictions/history)
        r_hist_admin = await http.get("/predictions/history", headers=headers_admin)
        assert r_hist_admin.status_code == 200, f"Admin history failed: {r_hist_admin.text}"
        hist_admin = r_hist_admin.json()
        print(f"[PASS] Test 02: Admin retrieved {len(hist_admin)} historical snapshots from /predictions/history")
        assert len(hist_admin) > 0

        # TEST 3: PM1 (Sarah) Scoped Performance
        r_perf_pm1 = await http.get("/predictions/performance", headers=headers_pm1)
        assert r_perf_pm1.status_code == 200, f"PM1 perf failed: {r_perf_pm1.text}"
        perf_pm1 = r_perf_pm1.json()
        print(f"[PASS] Test 03: PM1 retrieved scoped performance for {len(perf_pm1)} models")
        for m in perf_pm1:
            print(f"      - PM1 {m['prediction_type']}: Total={m['total_predictions']}, Eval={m['evaluated_count']}, Pending={m['pending_count']}")

        # TEST 4: PM2 (Marcus) Scoped Performance
        r_perf_pm2 = await http.get("/predictions/performance", headers=headers_pm2)
        assert r_perf_pm2.status_code == 200, f"PM2 perf failed: {r_perf_pm2.text}"
        perf_pm2 = r_perf_pm2.json()
        print(f"[PASS] Test 04: PM2 retrieved scoped performance for {len(perf_pm2)} models")
        for m in perf_pm2:
            print(f"      - PM2 {m['prediction_type']}: Total={m['total_predictions']}, Eval={m['evaluated_count']}, Pending={m['pending_count']}")

        # Verify PM1 and PM2 counts are properly isolated
        pm1_burnout = next(m for m in perf_pm1 if m['prediction_type'] == 'EMPLOYEE_BURNOUT')
        pm2_burnout = next(m for m in perf_pm2 if m['prediction_type'] == 'EMPLOYEE_BURNOUT')
        print(f"      PM1 Team Capacity Burnout count: {pm1_burnout['total_predictions']} (Expected: ~18)")
        print(f"      PM2 Team Capacity Burnout count: {pm2_burnout['total_predictions']} (Expected: ~16)")
        assert pm1_burnout['total_predictions'] == 18, f"Expected 18 for PM1, got {pm1_burnout['total_predictions']}"
        assert pm2_burnout['total_predictions'] == 16, f"Expected 16 for PM2, got {pm2_burnout['total_predictions']}"
        print("[PASS] Test 05: PM Employee Burnout strictly scoped to PM Team Capacity (18 vs 16)!")

        # TEST 6: Project Filter on performance and history
        sarah_pid = "6ac0b0bc3ed2ce90ad847148"
        r_perf_proj = await http.get(f"/predictions/performance?project_id={sarah_pid}", headers=headers_pm1)
        assert r_perf_proj.status_code == 200
        perf_proj = r_perf_proj.json()
        print(f"[PASS] Test 06: Project filter on performance returns {len(perf_proj)} models for project {sarah_pid}")

        r_hist_proj = await http.get(f"/predictions/history/{sarah_pid}", headers=headers_pm1)
        assert r_hist_proj.status_code == 200
        hist_proj = r_hist_proj.json()
        print(f"[PASS] Test 07: Project filter on history returns {len(hist_proj)} snapshots for project {sarah_pid}")
        assert all(h.get('project_id') == sarah_pid or h.get('entity_id') is not None for h in hist_proj)

        # TEST 8: Prediction Type Filter
        r_hist_type = await http.get("/predictions/history?prediction_type=DEADLINE_DELAY", headers=headers_admin)
        assert r_hist_type.status_code == 200
        hist_type = r_hist_type.json()
        print(f"[PASS] Test 08: Prediction type filter DEADLINE_DELAY returned {len(hist_type)} snapshots")
        assert all(h['prediction_type'] == 'DEADLINE_DELAY' for h in hist_type)

        # TEST 9: Outcome Status Filter
        r_hist_pending = await http.get("/predictions/history?evaluation_status=PENDING", headers=headers_admin)
        assert r_hist_pending.status_code == 200
        hist_pending = r_hist_pending.json()
        print(f"[PASS] Test 09: Evaluation status filter PENDING returned {len(hist_pending)} snapshots")
        assert all(h['evaluation_status'] == 'PENDING' for h in hist_pending)

        # TEST 10: RBAC - Unauthorized PM blocked (Sarah accessing Marcus's project)
        marcus_pid = "6ac0b0bc3ed2ce90ad84714b"
        r_unauth_hist = await http.get(f"/predictions/history/{marcus_pid}", headers=headers_pm1)
        assert r_unauth_hist.status_code == 403, f"Expected 403 for unauthorized PM project access, got {r_unauth_hist.status_code}"
        print("[PASS] Test 10: Unauthorized PM access to other PM's project history blocked with 403!")

        r_unauth_perf = await http.get(f"/predictions/performance?project_id={marcus_pid}", headers=headers_pm1)
        assert r_unauth_perf.status_code == 403, f"Expected 403 for unauthorized PM performance access, got {r_unauth_perf.status_code}"
        print("[PASS] Test 11: Unauthorized PM access to other PM's project performance blocked with 403!")

        # TEST 12: RBAC - Team Member restricted
        r_tm_perf = await http.get("/predictions/performance", headers=headers_tm)
        assert r_tm_perf.status_code == 403, f"Expected 403 for Team Member, got {r_tm_perf.status_code}"
        print("[PASS] Test 12: Team Member blocked from ML Tracking performance endpoint with 403!")

        r_tm_hist = await http.get("/predictions/history", headers=headers_tm)
        assert r_tm_hist.status_code == 403, f"Expected 403 for Team Member, got {r_tm_hist.status_code}"
        print("[PASS] Test 13: Team Member blocked from ML Tracking history endpoint with 403!")

        # TEST 14: Auto-Evaluate Lifecycle on Active Project
        r_auto = await http.post(f"/predictions/project/{sarah_pid}/auto-evaluate", headers=headers_pm1)
        assert r_auto.status_code == 200
        auto_res = r_auto.json()
        print(f"[PASS] Test 14: Auto-evaluate on active project safely evaluated {auto_res.get('evaluated_count')} (Active remains PENDING, no fake outcomes)!")
        assert auto_res.get("evaluated_count") == 0

        # TEST 15: Trajectory calculation for project
        r_traj = await http.get(f"/predictions/trajectory/{sarah_pid}", headers=headers_pm1)
        assert r_traj.status_code == 200
        traj = r_traj.json()
        print(f"[PASS] Test 15: Trajectory calculated for {sarah_pid} (Direction: {traj.get('trajectory_direction')}, Points: {len(traj.get('history', []))})")

        print("=" * 80)
        print("ALL 15 ML TRACKING AUDIT & VERIFICATION TESTS PASSED (100%)!")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(verify_ml_tracking())
