"""
NexusAI Operational Notification Workflow Verification Test Suite
Validates the operational notification workflow according to enterprise requirements:
- EVENT 1: PROJECT_ASSIGNED (team member assigned to new project)
- EVENT 2: ISSUE_ASSIGNED (team member assigned new issue)
- EVENT 3: ISSUE_RESOLVED (issue resolved -> assigned PM notified)
- Duplicate protection across all events
- Multi-PM and RBAC isolation
- Read/Unread tracking
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
    print("NEXUSAI NOTIFICATION WORKFLOW AUTOMATED TEST SUITE")
    print("============================================================")

    # 1. Direct MongoDB cleanup for clean test state
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, follow_redirects=True) as http:
        # Step 0: Log in as PM1 (Sarah Chen), PM2 (Marcus Vance), and Team Member (Alex Rivera / member1)
        # Login Sarah (PM1)
        r_pm1 = await http.post("/auth/login", json={"email": "sarah@nexusai.dev", "password": "Password123!"})
        if r_pm1.status_code != 200:
            print(f"[FAIL] Could not login PM1 (Sarah): {r_pm1.text}")
            return False
        token_pm1 = r_pm1.json()["access_token"]
        headers_pm1 = {"Authorization": f"Bearer {token_pm1}"}

        # Login Marcus (PM2)
        r_pm2 = await http.post("/auth/login", json={"email": "marcus.vance@nexusai.dev", "password": "Password123!"})
        if r_pm2.status_code != 200:
            print(f"[FAIL] Could not login PM2 (Marcus): {r_pm2.text}")
            return False
        token_pm2 = r_pm2.json()["access_token"]
        headers_pm2 = {"Authorization": f"Bearer {token_pm2}"}

        # Find Sarah's user & PM1 team info first, then determine which member account to use
        user_pm1 = await db.users.find_one({"email": "sarah@nexusai.dev"})
        user_pm2 = await db.users.find_one({"email": "marcus.vance@nexusai.dev"})

        # Pick an active Team Capacity member of PM1
        pm1_mem = await db.team_memberships.find_one({"pm_user_id": str(user_pm1["_id"]), "status": "active"})
        emp_member = await db.employees.find_one({"_id": ObjectId(pm1_mem["employee_id"])})
        emp_member_id = str(emp_member["_id"])

        # Find member1@nexusai.com's ACTUAL employee record (Alex Rivera)
        member_login_email = "member1@nexusai.com"
        user_member = await db.users.find_one({"email": member_login_email})
        if user_member is None:
            print(f"[FAIL] member1@nexusai.com user account not found in DB")
            return False

        # Find Alex Rivera's employee record by user_id or email
        emp_member = await db.employees.find_one({"user_id": str(user_member["_id"])})
        if emp_member is None:
            emp_member = await db.employees.find_one({"email": member_login_email})
        if emp_member is None:
            print(f"[FAIL] No employee record found for member1@nexusai.com")
            return False
        emp_member_id = str(emp_member["_id"])

        # Ensure PM1 has an active team_membership for this employee (add temporarily if missing)
        existing_membership = await db.team_memberships.find_one({
            "pm_user_id": str(user_pm1["_id"]),
            "employee_id": emp_member_id,
            "status": "active"
        })
        created_test_membership = False
        if not existing_membership:
            await db.team_memberships.insert_one({
                "pm_user_id": str(user_pm1["_id"]),
                "employee_id": emp_member_id,
                "status": "active",
                "role": "Senior Backend Engineer",
                "joined_at": datetime.now(timezone.utc),
                "_test_created": True,
            })
            created_test_membership = True

        # Login Member1 (Team Member)
        r_member = await http.post("/auth/login", json={"email": member_login_email, "password": "Password123!"})
        if r_member.status_code != 200:
            print(f"[FAIL] Could not login Team Member: {r_member.text}")
            return False
        token_member = r_member.json()["access_token"]
        headers_member = {"Authorization": f"Bearer {token_member}"}
        
        print(f"[SETUP] PM1 User ID: {user_pm1['_id']}, PM2 User ID: {user_pm2['_id']}, Member Emp ID: {emp_member_id}")

        # Clear notifications for clean isolation
        await db.notifications.delete_many({})

        # -------------------------------------------------------------
        # TEST 1: Assign Team Member to new project
        # -------------------------------------------------------------
        print("\n--- TEST 1: Assign Team Member to new project ---")
        proj_payload = {
            "name": f"Enterprise Cloud Infrastructure {int(datetime.now(timezone.utc).timestamp())}",
            "description": "Enterprise multi-cloud scalability initiative",
            "team_member_ids": [emp_member_id],
            "status": "active",
            "start_date": "2026-10-01",
            "end_date": "2026-12-31",
            "budget": 500000.0,
            "priority": "high",
        }
        r_proj = await http.post("/projects", json=proj_payload, headers=headers_pm1)
        assert r_proj.status_code in (200, 201), f"Create project failed: {r_proj.text}"
        project = r_proj.json()
        project_id = project["id"]
        print(f"Created Project: {project['name']} (ID: {project_id})")

        # Verify member received exactly ONE PROJECT_ASSIGNED notification
        r_notifs = await http.get("/dashboard/notifications", headers=headers_member)
        assert r_notifs.status_code == 200, f"Get notifs failed: {r_notifs.text}"
        member_notifs = r_notifs.json()
        proj_notifs = [n for n in member_notifs if n["type"] == "PROJECT_ASSIGNED" and n["related_project_id"] == project_id]
        print(f"Project assignment notifications received by member: {len(proj_notifs)}")
        assert len(proj_notifs) == 1, f"Expected exactly 1 PROJECT_ASSIGNED notification, got {len(proj_notifs)}"
        assert "New Project Assignment" in proj_notifs[0]["title"]
        print("[TEST 1 PASSED] Exactly 1 PROJECT_ASSIGNED notification created for assigned member.")

        # -------------------------------------------------------------
        # TEST 2: Repeat the same project update (duplicate prevention)
        # -------------------------------------------------------------
        print("\n--- TEST 2: Duplicate project assignment protection ---")
        update_payload = {
            "name": project["name"],
            "team_member_ids": [emp_member_id], # same team
            "description": "Updated project description without changing team",
        }
        r_upd = await http.put(f"/projects/{project_id}", json=update_payload, headers=headers_pm1)
        assert r_upd.status_code == 200, f"Update project failed: {r_upd.text}"

        r_notifs2 = await http.get("/dashboard/notifications", headers=headers_member)
        member_notifs2 = r_notifs2.json()
        proj_notifs2 = [n for n in member_notifs2 if n["type"] == "PROJECT_ASSIGNED" and n["related_project_id"] == project_id]
        print(f"Project assignment notifications after duplicate update: {len(proj_notifs2)}")
        assert len(proj_notifs2) == 1, f"Duplicate notification generated! Expected 1, got {len(proj_notifs2)}"
        print("[TEST 2 PASSED] No duplicate PROJECT_ASSIGNED notification created on repeat update.")

        # -------------------------------------------------------------
        # TEST 3: Assign issue to Team Member
        # -------------------------------------------------------------
        print("\n--- TEST 3: Assign issue to Team Member ---")
        issue_payload = {
            "title": "Authentication token refresh failure",
            "description": "JWT refresh token returns 401 intermittently under load",
            "project_id": project_id,
            "assignee_id": emp_member_id,
            "severity": "high",
            "priority": "high",
            "status": "open",
        }
        r_issue = await http.post("/issues", json=issue_payload, headers=headers_pm1)
        assert r_issue.status_code in (200, 201), f"Create issue failed: {r_issue.text}"
        issue = r_issue.json()
        issue_id = issue["id"]
        print(f"Created Issue: {issue['title']} (ID: {issue_id}) assigned to {emp_member_id}")

        r_notifs3 = await http.get("/dashboard/notifications", headers=headers_member)
        member_notifs3 = r_notifs3.json()
        issue_notifs = [n for n in member_notifs3 if n["type"] == "ISSUE_ASSIGNED" and n["related_issue_id"] == issue_id]
        print(f"Issue assignment notifications received by member: {len(issue_notifs)}")
        assert len(issue_notifs) == 1, f"Expected exactly 1 ISSUE_ASSIGNED notification, got {len(issue_notifs)}"
        assert "New Issue Assigned" in issue_notifs[0]["title"]
        print("[TEST 3 PASSED] Exactly 1 ISSUE_ASSIGNED notification created for assigned member.")

        # -------------------------------------------------------------
        # TEST 4: Update unrelated issue fields without changing assignee
        # -------------------------------------------------------------
        print("\n--- TEST 4: Update unrelated issue fields (duplicate prevention) ---")
        issue_upd = {
            "title": "Authentication token refresh failure - Updated Notes",
            "description": "Additional logs attached",
            "assignee_id": emp_member_id, # same assignee
        }
        r_issue_upd = await http.put(f"/issues/{issue_id}", json=issue_upd, headers=headers_pm1)
        assert r_issue_upd.status_code == 200, f"Update issue failed: {r_issue_upd.text}"

        r_notifs4 = await http.get("/dashboard/notifications", headers=headers_member)
        member_notifs4 = r_notifs4.json()
        issue_notifs4 = [n for n in member_notifs4 if n["type"] == "ISSUE_ASSIGNED" and n["related_issue_id"] == issue_id]
        print(f"Issue assignment notifications after unrelated update: {len(issue_notifs4)}")
        assert len(issue_notifs4) == 1, f"Duplicate issue notification generated! Expected 1, got {len(issue_notifs4)}"
        print("[TEST 4 PASSED] No duplicate ISSUE_ASSIGNED notification on unrelated issue updates.")

        # -------------------------------------------------------------
        # TEST 5: Resolve assigned issue -> PM1 receives ISSUE_RESOLVED
        # -------------------------------------------------------------
        print("\n--- TEST 5: Resolve assigned issue ---")
        resolve_payload = {
            "status": "resolved",
            "resolution_notes": "Fixed token expiration race condition in Redis session cache.",
        }
        r_resolve = await http.put(f"/issues/{issue_id}", json=resolve_payload, headers=headers_member)
        assert r_resolve.status_code == 200, f"Resolve issue failed: {r_resolve.text}"

        # PM1 (Sarah) should receive ISSUE_RESOLVED notification
        r_pm1_notifs = await http.get("/dashboard/notifications", headers=headers_pm1)
        assert r_pm1_notifs.status_code == 200
        pm1_notifs = r_pm1_notifs.json()
        resolved_notifs = [n for n in pm1_notifs if n["type"] == "ISSUE_RESOLVED" and n["related_issue_id"] == issue_id]
        print(f"ISSUE_RESOLVED notifications received by PM1 (Sarah): {len(resolved_notifs)}")
        assert len(resolved_notifs) == 1, f"Expected exactly 1 ISSUE_RESOLVED notification for PM1, got {len(resolved_notifs)}"
        assert "Issue Resolved" in resolved_notifs[0]["title"]
        print("[TEST 5 PASSED] Exactly 1 ISSUE_RESOLVED notification received by responsible manager.")

        # -------------------------------------------------------------
        # TEST 6: Resolve an already resolved issue / repeat update
        # -------------------------------------------------------------
        print("\n--- TEST 6: Repeat update on already resolved issue ---")
        r_repeat = await http.put(f"/issues/{issue_id}", json={"status": "resolved", "description": "Minor note"}, headers=headers_member)
        assert r_repeat.status_code == 200

        r_pm1_notifs2 = await http.get("/dashboard/notifications", headers=headers_pm1)
        resolved_notifs2 = [n for n in r_pm1_notifs2.json() if n["type"] == "ISSUE_RESOLVED" and n["related_issue_id"] == issue_id]
        print(f"ISSUE_RESOLVED notifications after repeat update: {len(resolved_notifs2)}")
        assert len(resolved_notifs2) == 1, f"Duplicate resolution notification generated! Expected 1, got {len(resolved_notifs2)}"
        print("[TEST 6 PASSED] No duplicate ISSUE_RESOLVED notification on repeated update.")

        # -------------------------------------------------------------
        # TEST 7: Reopen issue and resolve again
        # -------------------------------------------------------------
        print("\n--- TEST 7: Reopen and re-resolve issue ---")
        # First mark the previous notification as read so a new resolution creates a new unread notification
        await http.put("/dashboard/notifications/read-all", headers=headers_pm1)

        # Reopen
        r_reopen = await http.put(f"/issues/{issue_id}", json={"status": "in_progress"}, headers=headers_pm1)
        assert r_reopen.status_code == 200

        # Resolve again
        r_re_resolve = await http.put(f"/issues/{issue_id}", json={"status": "resolved"}, headers=headers_member)
        assert r_re_resolve.status_code == 200

        r_pm1_notifs3 = await http.get("/dashboard/notifications?unread_only=true", headers=headers_pm1)
        re_resolved_notifs = [n for n in r_pm1_notifs3.json() if n["type"] == "ISSUE_RESOLVED" and n["related_issue_id"] == issue_id]
        print(f"New unread ISSUE_RESOLVED notification after reopening and resolving: {len(re_resolved_notifs)}")
        assert len(re_resolved_notifs) == 1, f"Expected 1 new unread resolution notification, got {len(re_resolved_notifs)}"
        print("[TEST 7 PASSED] Genuine re-resolution creates a fresh ISSUE_RESOLVED notification.")

        # -------------------------------------------------------------
        # TEST 8: Multi-PM RBAC Isolation
        # -------------------------------------------------------------
        print("\n--- TEST 8: Multi-PM RBAC Isolation ---")
        # PM2 (Marcus) must NOT have received Sarah's project assignment or issue resolution notifications
        r_pm2_notifs = await http.get("/dashboard/notifications", headers=headers_pm2)
        assert r_pm2_notifs.status_code == 200
        pm2_notifs = r_pm2_notifs.json()
        unrelated_notifs = [n for n in pm2_notifs if n["related_project_id"] == project_id or n.get("related_issue_id") == issue_id]
        print(f"Notifications received by unrelated PM2 (Marcus): {len(unrelated_notifs)}")
        assert len(unrelated_notifs) == 0, f"Leakage detected! PM2 received unrelated notifications: {unrelated_notifs}"
        print("[TEST 8 PASSED] Multi-PM isolation strictly enforced. PM2 received 0 unrelated notifications.")

        # -------------------------------------------------------------
        # TEST 9: Notification Read/Unread State Management
        # -------------------------------------------------------------
        print("\n--- TEST 9: Read / Unread State Management ---")
        # Check unread count for member
        r_cnt = await http.get("/dashboard/notifications/unread-count", headers=headers_member)
        assert r_cnt.status_code == 200
        unread_before = r_cnt.json()["unread_count"]
        print(f"Member unread count before read-all: {unread_before}")
        assert unread_before > 0

        # Mark all read
        r_read_all = await http.put("/dashboard/notifications/read-all", headers=headers_member)
        assert r_read_all.status_code == 200

        # Check unread count is now 0
        r_cnt2 = await http.get("/dashboard/notifications/unread-count", headers=headers_member)
        assert r_cnt2.status_code == 200
        unread_after = r_cnt2.json()["unread_count"]
        print(f"Member unread count after read-all: {unread_after}")
        assert unread_after == 0
        print("[TEST 9 PASSED] Read/unread endpoints functional and accurate.")

        print("\n============================================================")
        print("ALL NOTIFICATION WORKFLOW INTEGRATION TESTS PASSED (100%)")
        print("============================================================")
        
        # Cleanup test entities
        await db.projects.delete_one({"_id": ObjectId(project_id)})
        await db.issues.delete_one({"_id": ObjectId(issue_id)})
        await db.activities.delete_many({"project_id": project_id})
        await db.notifications.delete_many({"relatedProjectId": project_id})
        await db.notifications.delete_many({"related_project_id": project_id})
        # Remove test-created membership if we added one
        if created_test_membership:
            await db.team_memberships.delete_one({"pm_user_id": str(user_pm1["_id"]), "employee_id": emp_member_id, "_test_created": True})
        return True


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    if not success:
        sys.exit(1)
