import asyncio
import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
from datetime import datetime
from bson import ObjectId
import httpx
from app.db.database import connect_db, get_database
from app.core.security import create_access_token

API_BASE = "http://127.0.0.1:8000"

async def run_e2e_tests():
    await connect_db()
    db = get_database()

    print("=" * 70)
    print("NEXUSAI FINAL END-TO-END WORKFLOW VERIFICATION")
    print("=" * 70)

    # 1. Fetch users and employees
    admin = await db.users.find_one({"role": "admin"})
    pm = await db.users.find_one({"role": "project_manager"})
    
    # Find or set up a test employee linked to a user account
    test_user_email = "member2@nexusai.com"
    tm_user = await db.users.find_one({"email": test_user_email})
    if not tm_user:
        tm_user = await db.users.find_one({"role": "team_member"})
        test_user_email = tm_user["email"]

    # Ensure this user has an employee record
    emp = await db.employees.find_one({"email": test_user_email})
    if not emp:
        emp = await db.employees.find_one({})
        await db.employees.update_one({"_id": emp["_id"]}, {"$set": {"user_id": str(tm_user["_id"]), "email": test_user_email}})
        emp = await db.employees.find_one({"_id": emp["_id"]})
    else:
        if not emp.get("user_id"):
            await db.employees.update_one({"_id": emp["_id"]}, {"$set": {"user_id": str(tm_user["_id"])}})

    admin_token = create_access_token({"sub": str(admin["_id"]), "email": admin["email"], "role": admin["role"]})
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    tm_token = create_access_token({"sub": str(tm_user["_id"]), "email": tm_user["email"], "role": tm_user["role"]})
    tm_headers = {"Authorization": f"Bearer {tm_token}"}

    results = {}

    async with httpx.AsyncClient(timeout=30) as client:
        # -------------------------------------------------------------
        # WORKFLOW 1: Project -> Run AI Analysis
        # -------------------------------------------------------------
        print("\n[WORKFLOW 1] Testing Project -> Run AI Analysis...")
        project = await db.projects.find_one({})
        pid = str(project["_id"])
        pname = project.get("name")
        print(f"  Target Project: {pname} (ID: {pid})")

        rec_cnt_before = await db.recommendations.count_documents({"project_id": pid})

        # Run AI Analysis via API
        resp = await client.post(f"{API_BASE}/predictions/analyze/project/{pid}", headers=admin_headers)
        print(f"  POST /predictions/analyze/project/{pid} status:", resp.status_code)
        assert resp.status_code == 200, f"Analysis failed: {resp.text}"
        data = resp.json()

        # Verify prediction persistence in MongoDB
        persisted_pred = await db.project_predictions.find_one({"project_id": pid})
        assert persisted_pred is not None, "Prediction doc not found in MongoDB!"
        print(f"  ✓ Prediction persisted: Risk={persisted_pred.get('risk_class')}, Health Score={persisted_pred.get('health_score')}")

        # Verify recommendation persistence
        recs = await db.recommendations.find({"project_id": pid}).to_list(10)
        print(f"  ✓ Recommendations in MongoDB for this project: {len(recs)} (was {rec_cnt_before})")
        assert len(recs) > 0, "No recommendations generated/persisted!"

        # Verify activity creation
        activities = await db.project_activities.find({"project_id": pid, "activity_type": "AI_ANALYSIS_COMPLETED"}).to_list(10)
        print(f"  ✓ AI Analysis Completed Activity logged: {len(activities)} event(s)")
        assert len(activities) > 0, "Activity AI_ANALYSIS_COMPLETED not found!"

        # Verify latest endpoint
        latest_resp = await client.get(f"{API_BASE}/predictions/projects/{pid}/latest", headers=admin_headers)
        assert latest_resp.status_code == 200
        print(f"  ✓ GET /predictions/projects/{pid}/latest returned 200 with Health={latest_resp.json().get('health_score')}")
        results["Workflow 1: Run AI Analysis"] = "PASS"

        # -------------------------------------------------------------
        # WORKFLOW 2: Project Assignment -> Notification & Read flow
        # -------------------------------------------------------------
        print("\n[WORKFLOW 2] Testing Project Assignment -> Notification flow...")
        emp_id = str(emp["_id"])
        
        # Add employee to project
        current_members = project.get("team_member_ids", [])
        if emp_id not in current_members:
            new_members = current_members + [emp_id]
        else:
            new_members = [m for m in current_members if m != emp_id]
            await client.put(f"{API_BASE}/projects/{pid}", headers=admin_headers, json={"team_member_ids": new_members})
            new_members = new_members + [emp_id]

        upd_resp = await client.put(f"{API_BASE}/projects/{pid}", headers=admin_headers, json={"team_member_ids": new_members})
        assert upd_resp.status_code == 200, f"Project update failed: {upd_resp.text}"

        # Verify notification created for tm_user
        notif_query = {
            "$or": [{"userId": str(tm_user["_id"])}, {"user_id": str(tm_user["_id"])}, {"userId": emp_id}, {"user_id": emp_id}],
            "type": "project_assignment"
        }
        notif = await db.notifications.find_one(notif_query, sort=[("createdAt", -1)])
        assert notif is not None, "Project assignment notification was not created!"
        print(f"  ✓ Notification found in MongoDB: '{notif.get('title')}' -> '{notif.get('message')}'")

        # Login as that employee & verify notifications endpoint
        tm_notifs_resp = await client.get(f"{API_BASE}/dashboard/notifications", headers=tm_headers)
        assert tm_notifs_resp.status_code == 200
        tm_notifs = tm_notifs_resp.json()
        print(f"  ✓ Team Member retrieved {len(tm_notifs)} notification(s)")

        # Verify unread count
        unread_resp = await client.get(f"{API_BASE}/dashboard/notifications/unread-count", headers=tm_headers)
        assert unread_resp.status_code == 200
        initial_unread = unread_resp.json()["unread_count"]
        print(f"  ✓ Team Member initial unread count: {initial_unread}")
        assert initial_unread > 0, "Unread count should be > 0"

        # Mark notification as read
        notif_id = str(notif["_id"])
        read_resp = await client.put(f"{API_BASE}/dashboard/notifications/{notif_id}/read", headers=tm_headers)
        assert read_resp.status_code == 200
        print(f"  ✓ Marked notification {notif_id} as read")

        # Verify unread count decreased
        unread_after = (await client.get(f"{API_BASE}/dashboard/notifications/unread-count", headers=tm_headers)).json()["unread_count"]
        print(f"  ✓ Team Member unread count after marking read: {unread_after} (decreased from {initial_unread})")
        assert unread_after == initial_unread - 1, f"Expected {initial_unread - 1} unread, got {unread_after}"
        results["Workflow 2: Project Assignment Notification"] = "PASS"

        # -------------------------------------------------------------
        # WORKFLOW 3: Task Assignment -> Notification
        # -------------------------------------------------------------
        print("\n[WORKFLOW 3] Testing Task Assignment -> Notification...")
        task_resp = await client.post(f"{API_BASE}/tasks/", headers=admin_headers, json={
            "project_id": pid,
            "title": f"E2E Task Assignment Test {int(datetime.utcnow().timestamp())}",
            "assignee_id": emp_id,
            "priority": "high",
            "status": "todo",
            "estimated_hours": 8.0,
            "due_date": "2026-10-30"
        })
        assert task_resp.status_code == 200, f"Task creation failed: {task_resp.text}"
        task_data = task_resp.json()
        task_id = task_data["id"]
        print(f"  ✓ Task created: '{task_data['title']}' (ID: {task_id}) assigned to {emp.get('name')}")

        # Verify notification created
        task_notif = await db.notifications.find_one({
            "$or": [{"userId": str(tm_user["_id"])}, {"user_id": str(tm_user["_id"])}, {"userId": emp_id}, {"user_id": emp_id}],
            "type": "task_assignment"
        }, sort=[("createdAt", -1)])
        assert task_notif is not None, "Task assignment notification not found!"
        print(f"  ✓ Task notification found: '{task_notif.get('title')}' -> '{task_notif.get('message')}'")
        results["Workflow 3: Task Assignment Notification"] = "PASS"

        # -------------------------------------------------------------
        # WORKFLOW 4: Issue Assignment -> Notification
        # -------------------------------------------------------------
        print("\n[WORKFLOW 4] Testing Issue Assignment -> Notification...")
        issue_resp = await client.post(f"{API_BASE}/issues/", headers=admin_headers, json={
            "project_id": pid,
            "title": f"E2E Issue Assignment Test {int(datetime.utcnow().timestamp())}",
            "assignee_id": emp_id,
            "severity": "critical",
            "priority": "critical",
            "status": "open"
        })
        assert issue_resp.status_code == 200, f"Issue creation failed: {issue_resp.text}"
        issue_data = issue_resp.json()
        print(f"  ✓ Critical Issue created: '{issue_data['title']}' assigned to {emp.get('name')}")

        # Verify notification created for TM
        issue_notif = await db.notifications.find_one({
            "$or": [{"userId": str(tm_user["_id"])}, {"user_id": str(tm_user["_id"])}, {"userId": emp_id}, {"user_id": emp_id}],
            "type": "issue_assignment"
        }, sort=[("createdAt", -1)])
        assert issue_notif is not None, "Issue assignment notification not found!"
        print(f"  ✓ Issue notification found: '{issue_notif.get('title')}' -> '{issue_notif.get('message')}'")
        results["Workflow 4: Issue Assignment Notification"] = "PASS"

        # -------------------------------------------------------------
        # WORKFLOW 5: AI Assistant Grounding & RBAC
        # -------------------------------------------------------------
        print("\n[WORKFLOW 5] Testing AI Assistant Grounding & Scoping...")
        # 5.1 Real project question
        q1_resp = await client.post(f"{API_BASE}/ai-assistant/chat", headers=admin_headers, json={"message": f"What is the status of project {pname}?"})
        assert q1_resp.status_code == 200
        print(f"  ✓ Real project question: intent={q1_resp.json().get('intent')}")
        assert pname.lower() in q1_resp.json().get("response", "").lower()

        # 5.2 Task count question
        q2_resp = await client.post(f"{API_BASE}/ai-assistant/chat", headers=admin_headers, json={"message": "How many tasks do we have?"})
        assert q2_resp.status_code == 200
        print(f"  ✓ Task count question: intent={q2_resp.json().get('intent')}")
        assert "tasks" in q2_resp.json().get("response", "").lower()

        # 5.3 Risk question
        q3_resp = await client.post(f"{API_BASE}/ai-assistant/chat", headers=admin_headers, json={"message": "Which projects have the highest risk?"})
        assert q3_resp.status_code == 200
        print(f"  ✓ Risk question: intent={q3_resp.json().get('intent')}")
        assert "risk" in q3_resp.json().get("response", "").lower()

        # 5.4 Overdue tasks question
        q4_resp = await client.post(f"{API_BASE}/ai-assistant/chat", headers=admin_headers, json={"message": "How many overdue tasks are there?"})
        assert q4_resp.status_code == 200
        print(f"  ✓ Overdue task question: intent={q4_resp.json().get('intent')}")

        # 5.5 Nonexistent project question
        q5_resp = await client.post(f"{API_BASE}/ai-assistant/chat", headers=admin_headers, json={"message": "What is the status of project AtlantisX999?"})
        assert q5_resp.status_code == 200
        print(f"  ✓ Nonexistent project handled: response={q5_resp.json().get('response')[:80]}...")
        assert "couldn't find" in q5_resp.json().get("response", "").lower() or "not found" in q5_resp.json().get("intent", "").lower()

        # 5.6 Unauthorized information request (Team member asking for org-wide burnout)
        q6_resp = await client.post(f"{API_BASE}/ai-assistant/chat", headers=tm_headers, json={"message": "Show me the burnout risk of all employees."})
        assert q6_resp.status_code == 200
        print(f"  ✓ Unauthorized request handled: response={q6_resp.json().get('response')[:80]}...")
        assert "restricted" in q6_resp.json().get("response", "").lower() or "team member" in q6_resp.json().get("response", "").lower()
        results["Workflow 5: AI Assistant Grounding & RBAC"] = "PASS"

        # -------------------------------------------------------------
        # WORKFLOW 6: Analytics Consistency & Zero Validation
        # -------------------------------------------------------------
        print("\n[WORKFLOW 6] Testing Analytics Consistency & Zero Validation...")
        projs_list = (await client.get(f"{API_BASE}/projects/", headers=admin_headers)).json()
        dash_sum = (await client.get(f"{API_BASE}/dashboard/summary", headers=admin_headers)).json()
        exec_an = (await client.get(f"{API_BASE}/analytics/executive", headers=admin_headers)).json()
        proj_an = (await client.get(f"{API_BASE}/analytics/projects", headers=admin_headers)).json()
        team_an = (await client.get(f"{API_BASE}/analytics/team", headers=admin_headers)).json()
        risk_an = (await client.get(f"{API_BASE}/analytics/risks", headers=admin_headers)).json()
        trends_an = (await client.get(f"{API_BASE}/analytics/trends?days=30", headers=admin_headers)).json()

        print(f"  Projects Page Count:     {len(projs_list)}")
        print(f"  Dashboard Project Count: {dash_sum['projects']['total']}")
        print(f"  Executive Analytics:     {exec_an['projects']['total']}")

        assert len(projs_list) == dash_sum["projects"]["total"], "Projects Page != Dashboard total"
        assert dash_sum["projects"]["total"] == exec_an["projects"]["total"], "Dashboard != Executive Analytics total"
        assert exec_an["projects"]["total"] > 0, "Total projects should not be 0!"
        assert exec_an["employees"]["total"] > 0, "Total employees should not be 0!"
        assert len(proj_an) == exec_an["projects"]["total"], "Project analytics length mismatch"
        assert team_an["summary"]["total"] > 0, "Team analytics should have employees"
        assert risk_an["project_risk"]["high"] + risk_an["project_risk"]["medium"] + risk_an["project_risk"]["low"] > 0, "Risk analytics has 0 predictions"
        assert len(trends_an.get("series", [])) > 0, "Trends series data is empty"

        print("  ✓ All 5 Analytics Tabs return live populated data without false zeros!")
        results["Workflow 6: Analytics Consistency"] = "PASS"

        # -------------------------------------------------------------
        # WORKFLOW 7: Dashboard Widgets & Live KPIs
        # -------------------------------------------------------------
        print("\n[WORKFLOW 7] Testing Dashboard Widgets & Live KPIs...")
        print(f"  KPI Projects: Active={dash_sum['projects']['active']}, High Risk={dash_sum['projects']['high_risk']}")
        print(f"  KPI Tasks:    Total={dash_sum['tasks']['total']}, Overdue={dash_sum['tasks']['overdue']}")
        print(f"  KPI Issues:   Open={dash_sum['issues']['open']}, Critical={dash_sum['issues']['critical']}")
        print(f"  Recent Recommendations count: {len(dash_sum.get('recent_recommendations', []))}")
        print(f"  Recent Issues count:          {len(dash_sum.get('recent_issues', []))}")

        assert dash_sum["projects"]["total"] > 0
        assert dash_sum["tasks"]["total"] > 0
        assert len(dash_sum.get("recent_recommendations", [])) > 0
        assert len(dash_sum.get("recent_issues", [])) > 0
        print("  ✓ Dashboard KPIs, recent recommendations, and issue widgets verified live!")
        results["Workflow 7: Dashboard Widgets"] = "PASS"

    print("\n" + "=" * 70)
    print("FINAL SUMMARY OF WORKFLOW VERIFICATIONS:")
    for wf, status in results.items():
        print(f"  {wf}: {status}")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_e2e_tests())
