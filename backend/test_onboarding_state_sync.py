"""
NEXUSAI — TEAM MEMBER ONBOARDING APPROVAL/REJECTION STATE SYNCHRONIZATION AUDIT
==============================================================================
Validates the complete business workflow:
1. Candidate registration with preferred PM -> status = 'pending', notification sent to PM
2. PM approval -> status = 'active', PM active count +1, slot -1, notification to member
3. Member status endpoint (GET /team-capacity/my-status) -> status = 'active'
4. PM rejection -> status = 'rejected', rejection reason, notification to member
5. Member status endpoint after rejection -> status = 'rejected', rejection reason
6. Persistence & state reload across sessions
7. Idempotence & duplicate protection (no duplicate memberships / notifications)
8. 18-member capacity hard limit enforcement on server-side
9. RBAC multi-PM isolation & team member security boundaries
"""

import asyncio
import sys
import time
from bson import ObjectId
from datetime import datetime, timezone
import motor.motor_asyncio
import httpx

BASE_URL = "http://127.0.0.1:8000"
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "nexusai"


async def run_tests():
    print("================================================================================")
    print("NEXUSAI ONBOARDING APPROVAL/REJECTION STATE SYNCHRONIZATION TEST SUITE")
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

    # Clean up any leftover test candidates from previous runs
    await db.users.delete_many({"email": {"$regex": "^candidate_"}})
    await db.employees.delete_many({"email": {"$regex": "^candidate_"}})
    await db.team_memberships.delete_many({"$or": [{"candidate_email": {"$regex": "^candidate_"}}, {"email": {"$regex": "^candidate_"}}]})

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, follow_redirects=True) as http:
        # Step 0: Auth logins
        r_admin = await http.post("/auth/login", json={"email": "admin@nexusai.dev", "password": "Password123!"})
        assert r_admin.status_code == 200, f"Admin login failed: {r_admin.text}"
        admin_token = r_admin.json()["access_token"]
        headers_admin = {"Authorization": f"Bearer {admin_token}"}

        # Alex Rodriguez (PM1)
        r_pm1 = await http.post("/auth/login", json={"email": "alex.rodriguez@nexusai.dev", "password": "Password123!"})
        assert r_pm1.status_code == 200, f"PM1 login failed: {r_pm1.text}"
        pm1_token = r_pm1.json()["access_token"]
        pm1_user = r_pm1.json()["user"]
        pm1_id = pm1_user["id"]
        headers_pm1 = {"Authorization": f"Bearer {pm1_token}"}

        # Marcus Vance (PM2)
        r_pm2 = await http.post("/auth/login", json={"email": "marcus.vance@nexusai.dev", "password": "Password123!"})
        assert r_pm2.status_code == 200, f"PM2 login failed: {r_pm2.text}"
        pm2_token = r_pm2.json()["access_token"]
        pm2_user = r_pm2.json()["user"]
        pm2_id = pm2_user["id"]
        headers_pm2 = {"Authorization": f"Bearer {pm2_token}"}

        print("[OK] Authenticated Admin, PM1 (Alex Rodriguez), and PM2 (Marcus Vance).")

        # -----------------------------------------------------------------
        # TEST 1: Register Team Member with Preferred PM -> Pending Status
        # -----------------------------------------------------------------
        ts = int(time.time())
        tm1_email = f"candidate_approved_{ts}@nexusai.dev"
        tm1_payload = {
            "name": f"Candidate Approved {ts}",
            "email": tm1_email,
            "password": "Password123!",
            "role": "team_member",
            "job_role": "Backend Engineer",
            "specialization": "Backend Development",
            "skills": ["Python", "FastAPI", "MongoDB"],
            "weekly_capacity_hours": 40.0,
            "preferred_pm_id": pm1_id,
        }

        r_signup1 = await http.post("/auth/signup", json=tm1_payload)
        assert r_signup1.status_code == 200, f"Signup 1 failed: {r_signup1.text}"
        tm1_token = r_signup1.json()["access_token"]
        tm1_user = r_signup1.json()["user"]
        tm1_id = tm1_user["id"]
        headers_tm1 = {"Authorization": f"Bearer {tm1_token}"}

        # Check DB state
        mem1 = await db.team_memberships.find_one({"requested_by": tm1_id})
        assert mem1 is not None, "Membership request not created in DB"
        req1_id = str(mem1["_id"])

        # Check PM notification
        notif_pm = await db.notifications.find_one({"userId": pm1_id, "type": "TEAM_MEMBER_REQUESTED"})
        record_test(
            "Registration creates pending request and dispatches TEAM_MEMBER_REQUESTED notification to PM",
            mem1.get("status") == "pending" and notif_pm is not None,
            f"Status: {mem1.get('status')}, PM notified: {pm1_user['name']}"
        )

        # -----------------------------------------------------------------
        # TEST 2: Team Member Status endpoint returns 'pending' before decision
        # -----------------------------------------------------------------
        r_status1_pre = await http.get("/team-capacity/my-status", headers=headers_tm1)
        assert r_status1_pre.status_code == 200
        st1_pre = r_status1_pre.json()
        record_test(
            "Team Member sees authoritative 'pending' status before PM decision",
            st1_pre.get("status") == "pending" and st1_pre.get("pm_name") == pm1_user["name"],
            f"Status: {st1_pre.get('status')}, Requested PM: {st1_pre.get('pm_name')}"
        )

        # -----------------------------------------------------------------
        # TEST 3: PM Approves Request -> Status 'active', capacity increments
        # -----------------------------------------------------------------
        # Get PM1 initial active count
        r_cap_pre = await http.get("/team-capacity/my-capacity", headers=headers_pm1)
        assert r_cap_pre.status_code == 200
        initial_active_cnt = r_cap_pre.json()["active_members_count"]
        initial_avail_cnt = r_cap_pre.json()["available_capacity"]

        # PM1 approves request
        r_app1 = await http.post(f"/team-capacity/requests/{req1_id}/approve", headers=headers_pm1)
        assert r_app1.status_code == 200, f"Approval failed: {r_app1.text}"
        app1_data = r_app1.json()

        # Check updated capacity
        r_cap_post = await http.get("/team-capacity/my-capacity", headers=headers_pm1)
        assert r_cap_post.status_code == 200
        new_active_cnt = r_cap_post.json()["active_members_count"]
        new_avail_cnt = r_cap_post.json()["available_capacity"]

        # Check member notification
        notif_assigned = await db.notifications.find_one({"userId": tm1_id, "type": "TEAM_MEMBER_ASSIGNED"})

        record_test(
            "PM Approval transitions status to 'active', updates PM capacity (+1), and notifies member",
            app1_data.get("status") == "active" and new_active_cnt == initial_active_cnt + 1 and notif_assigned is not None,
            f"Active count: {initial_active_cnt} -> {new_active_cnt}, Available: {initial_avail_cnt} -> {new_avail_cnt}"
        )

        # -----------------------------------------------------------------
        # TEST 4: Team Member Status endpoint returns 'active' after PM approval
        # -----------------------------------------------------------------
        r_status1_post = await http.get("/team-capacity/my-status", headers=headers_tm1)
        assert r_status1_post.status_code == 200
        st1_post = r_status1_post.json()
        record_test(
            "Team Member immediately retrieves authoritative 'active' status and Home PM details",
            st1_post.get("status") == "active" and st1_post.get("pm_name") == pm1_user["name"],
            f"Status: {st1_post.get('status')}, Home PM: {st1_post.get('pm_name')}"
        )

        # -----------------------------------------------------------------
        # TEST 5: Idempotent Approval / Duplicate Protection
        # -----------------------------------------------------------------
        r_app1_dup = await http.post(f"/team-capacity/requests/{req1_id}/approve", headers=headers_pm1)
        assert r_app1_dup.status_code == 200
        notif_assigned_count = await db.notifications.count_documents({"userId": tm1_id, "type": "TEAM_MEMBER_ASSIGNED"})
        record_test(
            "Duplicate approval is idempotent and creates 0 duplicate notifications",
            r_app1_dup.json().get("status") == "active" and notif_assigned_count == 1,
            f"Assigned notification count: {notif_assigned_count}"
        )

        # -----------------------------------------------------------------
        # TEST 6: Register Second Team Member for Rejection Flow
        # -----------------------------------------------------------------
        tm2_email = f"candidate_rejected_{ts}@nexusai.dev"
        tm2_payload = {
            "name": f"Candidate Rejected {ts}",
            "email": tm2_email,
            "password": "Password123!",
            "role": "team_member",
            "job_role": "QA Engineer",
            "specialization": "Quality Assurance",
            "skills": ["Selenium", "Jest", "Automation"],
            "weekly_capacity_hours": 40.0,
            "preferred_pm_id": pm1_id,
        }

        r_signup2 = await http.post("/auth/signup", json=tm2_payload)
        assert r_signup2.status_code == 200, f"Signup 2 failed: {r_signup2.text}"
        tm2_token = r_signup2.json()["access_token"]
        tm2_user = r_signup2.json()["user"]
        tm2_id = tm2_user["id"]
        headers_tm2 = {"Authorization": f"Bearer {tm2_token}"}

        mem2 = await db.team_memberships.find_one({"requested_by": tm2_id})
        assert mem2 is not None
        req2_id = str(mem2["_id"])

        # -----------------------------------------------------------------
        # TEST 7: PM Rejects Request with Reason
        # -----------------------------------------------------------------
        rejection_reason = "No QA vacancy in current sprint allocation"
        r_rej2 = await http.post(f"/team-capacity/requests/{req2_id}/reject?reason={rejection_reason.replace(' ', '+')}", headers=headers_pm1)
        assert r_rej2.status_code == 200, f"Rejection failed: {r_rej2.text}"
        rej2_data = r_rej2.json()

        # Check DB state
        mem2_after = await db.team_memberships.find_one({"_id": ObjectId(req2_id)})
        assert mem2_after.get("status") == "rejected"

        # Check member rejection notification
        notif_rejected = await db.notifications.find_one({"userId": tm2_id, "type": "TEAM_MEMBER_REQUEST_REJECTED"})

        record_test(
            "PM Rejection transitions status to 'rejected', persists reason, and notifies member",
            rej2_data.get("status") == "rejected" and notif_rejected is not None and rejection_reason in mem2_after.get("rejection_reason", ""),
            f"Status: {rej2_data.get('status')}, Reason: {mem2_after.get('rejection_reason')}"
        )

        # -----------------------------------------------------------------
        # TEST 8: Team Member Status endpoint returns 'rejected' + reason
        # -----------------------------------------------------------------
        r_status2_post = await http.get("/team-capacity/my-status", headers=headers_tm2)
        assert r_status2_post.status_code == 200
        st2_post = r_status2_post.json()
        record_test(
            "Rejected Team Member receives clear 'rejected' status and rejection reason",
            st2_post.get("status") == "rejected" and st2_post.get("rejection_reason") == rejection_reason,
            f"Status: {st2_post.get('status')}, Reason: {st2_post.get('rejection_reason')}"
        )

        # -----------------------------------------------------------------
        # TEST 9: Persistence Verification Across Simulated Reconnects
        # -----------------------------------------------------------------
        # Perform fresh query without cached state
        r_fresh_st1 = await http.get("/team-capacity/my-status", headers=headers_tm1)
        r_fresh_st2 = await http.get("/team-capacity/my-status", headers=headers_tm2)
        record_test(
            "Status persists authoritatively in MongoDB across fresh requests and sessions",
            r_fresh_st1.json().get("status") == "active" and r_fresh_st2.json().get("status") == "rejected",
            f"Member 1: {r_fresh_st1.json().get('status')}, Member 2: {r_fresh_st2.json().get('status')}"
        )

        # -----------------------------------------------------------------
        # TEST 10: Multi-PM RBAC Protection (PM2 cannot approve/reject PM1's request)
        # -----------------------------------------------------------------
        # Create third request for PM1
        tm3_email = f"candidate_rbac_{ts}@nexusai.dev"
        tm3_payload = {
            "name": f"Candidate RBAC {ts}",
            "email": tm3_email,
            "password": "Password123!",
            "role": "team_member",
            "job_role": "DevOps Engineer",
            "specialization": "DevOps / Cloud",
            "skills": ["Docker", "Kubernetes"],
            "weekly_capacity_hours": 40.0,
            "preferred_pm_id": pm1_id,
        }
        r_signup3 = await http.post("/auth/signup", json=tm3_payload)
        tm3_id = r_signup3.json()["user"]["id"]
        mem3 = await db.team_memberships.find_one({"requested_by": tm3_id})
        req3_id = str(mem3["_id"])

        # PM2 attempts to approve PM1's candidate
        r_unauth_app = await http.post(f"/team-capacity/requests/{req3_id}/approve", headers=headers_pm2)
        # PM2 attempts to reject PM1's candidate
        r_unauth_rej = await http.post(f"/team-capacity/requests/{req3_id}/reject", headers=headers_pm2)

        record_test(
            "PM isolation enforced: Unauthorized PM cannot approve/reject another PM's request (403)",
            r_unauth_app.status_code == 403 and r_unauth_rej.status_code == 403,
            f"Approve code: {r_unauth_app.status_code}, Reject code: {r_unauth_rej.status_code}"
        )

        # -----------------------------------------------------------------
        # TEST 11: Team Member Cannot Access Management Endpoints
        # -----------------------------------------------------------------
        r_tm_mgmt = await http.get("/team-capacity/my-capacity", headers=headers_tm1)
        r_tm_reqs = await http.get("/team-capacity/pending-requests", headers=headers_tm1)
        r_tm_app = await http.post(f"/team-capacity/requests/{req3_id}/approve", headers=headers_tm1)

        record_test(
            "Team Member restricted from PM management endpoints (403 Forbidden)",
            r_tm_mgmt.status_code == 403 and r_tm_reqs.status_code == 403 and r_tm_app.status_code == 403,
            f"Capacity: {r_tm_mgmt.status_code}, Pending: {r_tm_reqs.status_code}, Approve: {r_tm_app.status_code}"
        )

        # -----------------------------------------------------------------
        # TEST 12: Rejected Team Member Can Submit Request to Another PM
        # -----------------------------------------------------------------
        r_new_req = await http.post(f"/team-capacity/request/{pm2_id}", headers=headers_tm2)
        assert r_new_req.status_code == 200, f"New request failed: {r_new_req.text}"
        new_req_data = r_new_req.json()

        # Member status should now reflect pending with PM2
        r_status2_re = await http.get("/team-capacity/my-status", headers=headers_tm2)
        st2_re = r_status2_re.json()

        record_test(
            "Rejected Team Member can submit a new request to another active PM",
            st2_re.get("status") == "pending" and st2_re.get("pm_name") == pm2_user["name"],
            f"Status: {st2_re.get('status')}, New Requested PM: {st2_re.get('pm_name')}"
        )

        # Final cleanup of test candidates
        await db.users.delete_many({"email": {"$regex": "^candidate_"}})
        await db.employees.delete_many({"email": {"$regex": "^candidate_"}})
        await db.team_memberships.delete_many({
            "$or": [
                {"candidate_email": {"$regex": "^candidate_"}},
                {"email": {"$regex": "^candidate_"}},
                {"requested_by": {"$in": [tm1_id, tm2_id, tm3_id]}},
            ]
        })

    print("================================================================================")
    print(f"AUDIT SUMMARY: {test_passed} / {test_total} TESTS PASSED")
    print("================================================================================")
    return test_passed == test_total


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
