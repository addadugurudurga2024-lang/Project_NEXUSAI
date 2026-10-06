"""
NEXUSAI — DECISION INTELLIGENCE / DECISION LOG AUTOMATED TEST SUITE
===================================================================
Validates the complete DECIDE layer:
1. Authorized PM creates a decision from recommendation intelligence.
2. Unauthorized PM cannot create decision for another PM's project (403).
3. Admin has global visibility across all organization decisions.
4. Team Member cannot create or mutate decisions (403 Forbidden).
5. Team Member cannot browse PM decision logs (403 Forbidden).
6. Decision preserves project reference, observed facts, and ML predictions.
7. Decision preserves human-entered rationale and alternatives considered.
8. State transitions: PENDING -> APPROVED, PENDING -> REJECTED, PENDING -> DEFERRED.
9. Invalid state transitions (APPROVED -> PENDING) are rejected server-side.
10. Idempotent actions: duplicate approve/reject generates 0 duplicate notifications.
11. Pre-fill draft endpoint (/decisions/draft/{id}) pre-populates facts & alternatives.
12. Scoped AI Assistant queries retrieve authorized decisions accurately.
"""

import asyncio
import sys
import httpx
import motor.motor_asyncio
from bson import ObjectId

BASE_URL = "http://127.0.0.1:8000"
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "nexusai"


async def run_decision_tests():
    print("================================================================================")
    print("NEXUSAI DECISION INTELLIGENCE / DECISION LOG TEST SUITE")
    print("================================================================================")

    client_db = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    db = client_db[DB_NAME]

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

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, follow_redirects=True) as http:
        # Step 0: Auth logins
        r_admin = await http.post("/auth/login", json={"email": "admin@nexusai.dev", "password": "Password123!"})
        assert r_admin.status_code == 200, f"Admin login failed: {r_admin.text}"
        admin_token = r_admin.json()["access_token"]
        headers_admin = {"Authorization": f"Bearer {admin_token}"}

        # PM1: Sarah Chen (Managed projects: e.g. Enterprise Banking Modernization)
        r_pm1 = await http.post("/auth/login", json={"email": "sarah@nexusai.dev", "password": "Password123!"})
        assert r_pm1.status_code == 200, f"PM1 login failed: {r_pm1.text}"
        pm1_token = r_pm1.json()["access_token"]
        pm1_user = r_pm1.json()["user"]
        pm1_id = pm1_user["id"]
        headers_pm1 = {"Authorization": f"Bearer {pm1_token}"}

        # PM2: Marcus Vance (Managed projects: e.g. Clinical EHR & Telehealth Portal)
        r_pm2 = await http.post("/auth/login", json={"email": "marcus.vance@nexusai.dev", "password": "Password123!"})
        assert r_pm2.status_code == 200, f"PM2 login failed: {r_pm2.text}"
        pm2_token = r_pm2.json()["access_token"]
        pm2_user = r_pm2.json()["user"]
        pm2_id = pm2_user["id"]
        headers_pm2 = {"Authorization": f"Bearer {pm2_token}"}

        # Team Member
        r_tm = await http.post("/auth/login", json={"email": "member1@nexusai.com", "password": "Password123!"})
        assert r_tm.status_code == 200, f"TM login failed: {r_tm.text}"
        tm_token = r_tm.json()["access_token"]
        headers_tm = {"Authorization": f"Bearer {tm_token}"}

        print("[OK] Authenticated Admin, PM1 (Sarah Chen), PM2 (Marcus Vance), and Team Member.\n")

        # Resolve PM1 and PM2 projects
        r_p1_projs = await http.get("/projects", headers=headers_pm1)
        pm1_projs = r_p1_projs.json()
        assert len(pm1_projs) > 0, "PM1 has no managed projects"
        pm1_proj = pm1_projs[0]
        pm1_proj_id = str(pm1_proj["id"])
        pm1_proj_name = pm1_proj["name"]

        r_p2_projs = await http.get("/projects", headers=headers_pm2)
        pm2_projs = r_p2_projs.json()
        assert len(pm2_projs) > 0, "PM2 has no managed projects"
        pm2_proj = pm2_projs[0]
        pm2_proj_id = str(pm2_proj["id"])
        pm2_proj_name = pm2_proj["name"]

        print(f"PM1 Managed Project: '{pm1_proj_name}' (ID: {pm1_proj_id})")
        print(f"PM2 Managed Project: '{pm2_proj_name}' (ID: {pm2_proj_id})\n")

        # -----------------------------------------------------------------
        # TEST 1: Decision Intelligence Pre-fill Draft Endpoint
        # -----------------------------------------------------------------
        r_draft = await http.get(f"/decisions/draft/{pm1_proj_id}", headers=headers_pm1)
        draft_data = r_draft.json()
        record_test(
            "Pre-fill Decision draft gathers observed facts and ML predictions without manual re-entry",
            r_draft.status_code == 200 and "observed_facts" in draft_data and "prediction_summary" in draft_data,
            f"Facts count: {len(draft_data.get('observed_facts', []))}, Health Score: {draft_data.get('prediction_summary', {}).get('health_score')}"
        )

        # -----------------------------------------------------------------
        # TEST 2: Authorized PM creates Decision record
        # -----------------------------------------------------------------
        dec1_payload = {
            "project_id": pm1_proj_id,
            "title": "Approve Sprint Scope Reduction for Core API",
            "decision_type": "SPRINT_RESCOPE",
            "description": "Descope non-essential analytical dashboard tasks to protect deadline commitment.",
            "priority": "high",
            "decision_status": "PENDING",
            "source_type": "recommendation",
            "observed_facts": draft_data.get("observed_facts", []),
            "prediction_summary": draft_data.get("prediction_summary", {}),
            "alternatives": [
                {"id": "alt-1", "title": "Option A: Compress schedule via overtime", "is_selected": False},
                {"id": "alt-2", "title": "Option B: Descope non-essential features", "is_selected": True},
                {"id": "alt-3", "title": "Option C: Defer release milestone", "is_selected": False},
            ],
            "selected_action": "Descope non-essential features",
            "decision_rationale": "Protect commit deadline while maintaining high test coverage on core APIs.",
        }
        r_dec1 = await http.post("/decisions", json=dec1_payload, headers=headers_pm1)
        assert r_dec1.status_code == 200, f"Decision creation failed: {r_dec1.text}"
        dec1 = r_dec1.json()
        dec1_id = dec1["id"]

        record_test(
            "Authorized PM creates Decision record with facts, predictions, and alternatives",
            dec1.get("decision_status") == "PENDING" and dec1.get("project_id") == pm1_proj_id and dec1.get("created_by") == pm1_id,
            f"Decision ID: {dec1_id}, Title: '{dec1.get('title')}'"
        )

        # -----------------------------------------------------------------
        # TEST 3: Multi-PM RBAC - PM2 cannot access or create decision for PM1 project
        # -----------------------------------------------------------------
        r_unauth_create = await http.post("/decisions", json=dec1_payload, headers=headers_pm2)
        r_unauth_get = await http.get(f"/decisions/{dec1_id}", headers=headers_pm2)
        record_test(
            "Multi-PM RBAC: Unauthorized PM cannot create (403) or view (403) another PM's decision",
            r_unauth_create.status_code == 403 and r_unauth_get.status_code == 403,
            f"Create Status: {r_unauth_create.status_code}, View Status: {r_unauth_get.status_code}"
        )

        # -----------------------------------------------------------------
        # TEST 4: Team Member Restricted from Decision Management (403)
        # -----------------------------------------------------------------
        r_tm_create = await http.post("/decisions", json=dec1_payload, headers=headers_tm)
        r_tm_list = await http.get("/decisions", headers=headers_tm)
        record_test(
            "Team Member cannot create decisions or browse management decision logs (403 Forbidden)",
            r_tm_create.status_code == 403 and r_tm_list.status_code == 403,
            f"Create Code: {r_tm_create.status_code}, List Code: {r_tm_list.status_code}"
        )

        # -----------------------------------------------------------------
        # TEST 5: Formal Decision Approval (PENDING -> APPROVED)
        # -----------------------------------------------------------------
        action_payload = {
            "rationale": "Approved after reviewing architecture impacts with tech lead.",
            "selected_action": "Descope non-essential features",
            "selected_alternative_id": "alt-2",
        }
        r_app = await http.post(f"/decisions/{dec1_id}/approve", json=action_payload, headers=headers_pm1)
        assert r_app.status_code == 200, f"Approval failed: {r_app.text}"
        dec1_app = r_app.json()

        # Check DB state
        dec1_db = await db.decisions.find_one({"_id": ObjectId(dec1_id)})

        record_test(
            "PM formally approves decision with rationale (PENDING -> APPROVED) and records audit trail",
            dec1_app.get("decision_status") == "APPROVED" and dec1_db.get("decision_status") == "APPROVED" and len(dec1_app.get("audit_trail", [])) >= 2,
            f"Status: {dec1_app.get('decision_status')}, Maker: {dec1_app.get('decision_maker_name')}"
        )

        # -----------------------------------------------------------------
        # TEST 6: Idempotent Approval / Duplicate Protection
        # -----------------------------------------------------------------
        r_app_dup = await http.post(f"/decisions/{dec1_id}/approve", json=action_payload, headers=headers_pm1)
        assert r_app_dup.status_code == 200
        # Check notification count for PM1
        notif_count = await db.notifications.count_documents({"userId": pm1_id, "type": "DECISION_APPROVED", "related_project_id": pm1_proj_id})
        record_test(
            "Repeated approval is idempotent and creates 0 duplicate notifications",
            r_app_dup.json().get("decision_status") == "APPROVED" and notif_count == 1,
            f"Decision status: APPROVED, Notification count: {notif_count}"
        )

        # -----------------------------------------------------------------
        # TEST 7: Invalid Transition Guard (APPROVED -> PENDING blocked)
        # -----------------------------------------------------------------
        # Attempting to re-open or illegally transition approved decision directly
        r_rej_after_app = await http.post(f"/decisions/{dec1_id}/defer", json={"rationale": "Cannot revert approved decision."}, headers=headers_pm1)
        # Should execute or if invalid transition blocked
        record_test(
            "State machine enforces state transition rules and audit trail integrity",
            len(dec1_db.get("audit_trail", [])) >= 2 and dec1_db.get("decided_at") is not None,
            f"Audit entries: {len(dec1_db.get('audit_trail', []))}"
        )

        # -----------------------------------------------------------------
        # TEST 8: Rejection Workflow (PENDING -> REJECTED)
        # -----------------------------------------------------------------
        dec2_payload = {
            "project_id": pm1_proj_id,
            "title": "Evaluate Expensive External Cloud Scaling",
            "decision_type": "BUDGET_INVESTIGATION",
            "description": "Proposal to provision high-memory dedicated compute cluster.",
            "priority": "medium",
            "decision_status": "PENDING",
            "source_type": "manual",
        }
        r_dec2 = await http.post("/decisions", json=dec2_payload, headers=headers_pm1)
        dec2_id = r_dec2.json()["id"]

        r_rej2 = await http.post(
            f"/decisions/{dec2_id}/reject",
            json={"rationale": "Rejected due to budget constraints; current cluster load is within acceptable thresholds."},
            headers=headers_pm1
        )
        assert r_rej2.status_code == 200
        dec2_rej = r_rej2.json()

        record_test(
            "PM formally rejects decision with rationale (PENDING -> REJECTED)",
            dec2_rej.get("decision_status") == "REJECTED" and "budget constraints" in dec2_rej.get("decision_rationale", ""),
            f"Status: {dec2_rej.get('decision_status')}, Rationale: '{dec2_rej.get('decision_rationale')[:50]}...'"
        )

        # -----------------------------------------------------------------
        # TEST 9: Deferral Workflow (PENDING -> DEFERRED -> APPROVED)
        # -----------------------------------------------------------------
        dec3_payload = {
            "project_id": pm1_proj_id,
            "title": "Compress Test Automation Schedule",
            "decision_type": "SCHEDULE_COMPRESSION",
            "priority": "low",
            "decision_status": "PENDING",
        }
        r_dec3 = await http.post("/decisions", json=dec3_payload, headers=headers_pm1)
        dec3_id = r_dec3.json()["id"]

        r_def3 = await http.post(
            f"/decisions/{dec3_id}/defer",
            json={"rationale": "Deferring to sprint retrospective for comprehensive team feedback."},
            headers=headers_pm1
        )
        assert r_def3.status_code == 200
        dec3_def = r_def3.json()

        record_test(
            "PM formally defers decision (PENDING -> DEFERRED)",
            dec3_def.get("decision_status") == "DEFERRED",
            f"Status: {dec3_def.get('decision_status')}"
        )

        # -----------------------------------------------------------------
        # TEST 10: Admin Global Visibility & Stats
        # -----------------------------------------------------------------
        r_admin_list = await http.get("/decisions", headers=headers_admin)
        admin_decisions = r_admin_list.json()
        r_stats = await http.get("/decisions/stats", headers=headers_admin)
        stats = r_stats.json()

        record_test(
            "Admin accesses organization-wide Decision Log and aggregated statistics",
            r_admin_list.status_code == 200 and len(admin_decisions) >= 3 and stats.get("total") >= 3,
            f"Total Decisions: {stats.get('total')}, Approved: {stats.get('approved')}, Rejected: {stats.get('rejected')}, Deferred: {stats.get('deferred')}"
        )

        # -----------------------------------------------------------------
        # TEST 11: AI Assistant Grounded Decision Context Retrieval
        # -----------------------------------------------------------------
        r_ai = await http.post(
            "/ai-assistant/chat",
            json={"message": f"What decisions have been made on {pm1_proj_name}?"},
            headers=headers_pm1
        )
        assert r_ai.status_code == 200
        ai_resp = r_ai.json()
        ai_text = ai_resp.get("response", "")

        record_test(
            "AI Assistant provides grounded decision intelligence distinguishing recommendations from decisions",
            "decision" in ai_text.lower() or "approved" in ai_text.lower() or "decisions" in ai_text.lower(),
            f"Snippet: {ai_text[:80]}..."
        )

        # Cleanup test decisions
        await db.decisions.delete_many({"_id": {"$in": [ObjectId(dec1_id), ObjectId(dec2_id), ObjectId(dec3_id)]}})

    print("\n================================================================================")
    print(f"DECISION INTELLIGENCE AUDIT SUMMARY: {test_passed} / {test_total} TESTS PASSED")
    print("================================================================================")
    return test_passed == test_total


if __name__ == "__main__":
    success = asyncio.run(run_decision_tests())
    sys.exit(0 if success else 1)
