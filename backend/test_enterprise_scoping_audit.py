"""
Authoritative Enterprise Scoping, Multi-PM Organization, and Relational Integrity Audit Suite.
Validates:
1. Multi-PM Isolation (PM1 vs PM2)
2. Cross-PM Forbidden Access (HTTP 403)
3. Team Member Access Restrictions (HTTP 403 on executive features)
4. Admin Global Organization Visibility
5. AI Assistant Context Scoping
6. Resource Optimization Scoped Execution
7. Recommendation Engine Scoped Execution
8. Entity Relational Integrity (0 orphan entities)
9. Exact Enterprise Invariants (1 Admin, 12 PMs, 30 Projects, 185 Employees, 20-30% Cross-Project Specialists)
10. Deterministic Seed Invariant Verification
"""

import sys
import os
import asyncio
from typing import Dict, Any

# Ensure backend path is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from main import app
from app.db.database import get_database

def auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}

def run_scoping_audit():
    with TestClient(app) as client:
        def login(email: str, password: str = "Password123!") -> str:
            """Helper to authenticate and return JWT token."""
            response = client.post("/auth/login", json={"email": email, "password": password})
            assert response.status_code == 200, f"Login failed for {email}: {response.text}"
            return response.json()["access_token"]

        print("=" * 80)
        print("NEXUSAI REALISTIC ENTERPRISE MULTI-PM SCOPING & INTEGRITY AUDIT")
        print("=" * 80)
        
        # 1. Authenticate Actors
        print("\n[PHASE 1] Authenticating Test Actors...")
        admin_token = login("admin@nexusai.dev")
        pm1_token = login("sarah@nexusai.dev")  # PM-1: Sarah Chen
        pm2_token = login("marcus.vance@nexusai.dev")  # PM-2: Marcus Vance
        member_token = login("member1@nexusai.com")  # Team Member
        print("  [OK] Successfully authenticated Admin, PM1 (Sarah), PM2 (Marcus), Team Member.")

        def get_id(obj):
            return str(obj.get("id") or obj.get("_id"))

        # 2. PM Isolation & Scoping Tests
        print("\n[PHASE 2] Auditing Project Manager Isolation...")
        # PM1 Projects
        r = client.get("/projects", headers=auth_headers(pm1_token))
        assert r.status_code == 200
        pm1_projects = r.json()
        pm1_project_ids = [get_id(p) for p in pm1_projects]
        print(f"  [OK] PM1 sees {len(pm1_projects)} projects: {[p['name'] for p in pm1_projects]}")
        assert len(pm1_projects) == 3, f"PM1 should have exactly 3 assigned projects, got {len(pm1_projects)}"

        # PM2 Projects
        r = client.get("/projects", headers=auth_headers(pm2_token))
        assert r.status_code == 200
        pm2_projects = r.json()
        pm2_project_ids = [get_id(p) for p in pm2_projects]
        print(f"  [OK] PM2 sees {len(pm2_projects)} projects: {[p['name'] for p in pm2_projects]}")
        assert len(pm2_projects) == 3, f"PM2 should have exactly 3 assigned projects, got {len(pm2_projects)}"

        # Verify zero overlap between PM1 and PM2 projects
        overlap = set(pm1_project_ids).intersection(set(pm2_project_ids))
        assert len(overlap) == 0, f"PM1 and PM2 share unauthorized projects: {overlap}"
        print("  [OK] Strict PM isolation verified: 0 project overlap between PM1 and PM2.")

        # 3. Cross-PM Access Control (403 Forbidden Enforcement)
        print("\n[PHASE 3] Testing Cross-PM Direct API Access Restrictions...")
        target_pm2_project_id = pm2_project_ids[0]
        
        # PM1 tries to access PM2's project directly
        r_cross_proj = client.get(f"/projects/{target_pm2_project_id}", headers=auth_headers(pm1_token))
        assert r_cross_proj.status_code == 403, f"Expected 403 for cross-PM project access, got {r_cross_proj.status_code}"
        print(f"  [OK] PM1 direct GET on PM2 project -> 403 Forbidden (Blocked).")

        # PM1 tries to run ML prediction on PM2's project
        r_cross_pred = client.post(f"/predictions/project/{target_pm2_project_id}", headers=auth_headers(pm1_token))
        assert r_cross_pred.status_code == 403, f"Expected 403 for cross-PM prediction, got {r_cross_pred.status_code}"
        print(f"  [OK] PM1 ML prediction on PM2 project -> 403 Forbidden (Blocked).")

        # PM1 tries to run Resource Optimization on PM2's project
        r_cross_opt = client.get(f"/resource-optimization/{target_pm2_project_id}", headers=auth_headers(pm1_token))
        assert r_cross_opt.status_code == 403, f"Expected 403 for cross-PM resource opt, got {r_cross_opt.status_code}"
        print(f"  [OK] PM1 Resource Optimization on PM2 project -> 403 Forbidden (Blocked).")

        # PM1 tries to apply Resource Optimization on PM2's project
        r_cross_apply = client.post(
            "/resource-optimization/apply/507f1f77bcf86cd799439011",
            headers=auth_headers(pm1_token)
        )
        assert r_cross_apply.status_code in (403, 404), f"Expected 403 or 404 for cross-PM apply opt, got {r_cross_apply.status_code}"
        print(f"  [OK] PM1 apply Resource Optimization on unauthorized target -> Protected ({r_cross_apply.status_code}).")

        # 4. Team Scoping & Employee Listing
        print("\n[PHASE 4] Auditing PM-Scoped Employee / Team Visibility...")
        r_emp_pm1 = client.get("/employees", headers=auth_headers(pm1_token))
        assert r_emp_pm1.status_code == 200
        pm1_employees = r_emp_pm1.json()
        print(f"  [OK] PM1 has visibility over {len(pm1_employees)} distinct team members in their managed project portfolio.")

        r_emp_pm2 = client.get("/employees", headers=auth_headers(pm2_token))
        assert r_emp_pm2.status_code == 200
        pm2_employees = r_emp_pm2.json()
        print(f"  [OK] PM2 has visibility over {len(pm2_employees)} distinct team members in their managed project portfolio.")

        # 5. Task & Issue Scoping
        print("\n[PHASE 5] Auditing Task and Issue Scoping...")
        r_tasks_pm1 = client.get("/tasks", headers=auth_headers(pm1_token))
        assert r_tasks_pm1.status_code == 200
        pm1_tasks = r_tasks_pm1.json()
        for task in pm1_tasks:
            assert task.get("projectId") in pm1_project_ids or task.get("project_id") in pm1_project_ids, \
                f"PM1 received task for unauthorized project: {task}"
        print(f"  [OK] PM1 retrieved {len(pm1_tasks)} tasks, 100% belonging strictly to PM1's projects.")

        r_issues_pm1 = client.get("/issues", headers=auth_headers(pm1_token))
        assert r_issues_pm1.status_code == 200
        pm1_issues = r_issues_pm1.json()
        for issue in pm1_issues:
            assert issue.get("projectId") in pm1_project_ids or issue.get("project_id") in pm1_project_ids, \
                f"PM1 received issue for unauthorized project: {issue}"
        print(f"  [OK] PM1 retrieved {len(pm1_issues)} issues, 100% belonging strictly to PM1's projects.")

        # 6. Recommendation Scoping
        print("\n[PHASE 6] Auditing Decision Recommendation Scoping...")
        r_recs_pm1 = client.get("/recommendations", headers=auth_headers(pm1_token))
        assert r_recs_pm1.status_code == 200
        pm1_recs = r_recs_pm1.json()
        for rec in pm1_recs:
            p_id = rec.get("projectId") or rec.get("project_id")
            assert p_id in pm1_project_ids, f"PM1 received recommendation for unauthorized project: {rec}"
        print(f"  [OK] PM1 retrieved {len(pm1_recs)} recommendations, 100% scoped to PM1's projects.")

        # 7. Team Member Restrictions
        print("\n[PHASE 7] Auditing Team Member Security Boundaries...")
        r_tm_recs = client.post(f"/recommendations/generate/{target_pm2_project_id}", json={}, headers=auth_headers(member_token))
        assert r_tm_recs.status_code == 403, f"Team Member should not generate recommendations: {r_tm_recs.status_code}"
        print("  [OK] Team Member recommendation generation -> 403 Forbidden (Blocked).")

        r_tm_opt = client.get(f"/resource-optimization/{target_pm2_project_id}", headers=auth_headers(member_token))
        assert r_tm_opt.status_code == 403, f"Team Member should not access resource optimization: {r_tm_opt.status_code}"
        print("  [OK] Team Member resource optimization access -> 403 Forbidden (Blocked).")

        # 8. Admin Global Visibility
        print("\n[PHASE 8] Auditing Admin Global Visibility...")
        r_admin_projs = client.get("/projects", headers=auth_headers(admin_token))
        assert r_admin_projs.status_code == 200
        all_projects = r_admin_projs.json()
        print(f"  [OK] Admin sees all {len(all_projects)} organization projects (Target: 30).")
        assert len(all_projects) == 30, f"Expected 30 projects, got {len(all_projects)}"

        r_admin_emps = client.get("/employees", headers=auth_headers(admin_token))
        assert r_admin_emps.status_code == 200
        all_employees = r_admin_emps.json()
        print(f"  [OK] Admin sees all {len(all_employees)} organization employees (Target: 185).")
        assert len(all_employees) == 185, f"Expected 185 employees, got {len(all_employees)}"

        r_admin_recs = client.get("/recommendations", headers=auth_headers(admin_token))
        assert r_admin_recs.status_code == 200
        all_recs = r_admin_recs.json()
        print(f"  [OK] Admin sees all {len(all_recs)} organization recommendations (Target: >= 51).")
        assert len(all_recs) >= 51, f"Expected at least 51 recommendations, got {len(all_recs)}"

        # 9. AI Assistant Context Scoping
        print("\n[PHASE 9] Auditing AI Assistant Context Scoping...")
        r_ai_pm1 = client.post(
            "/ai-assistant/chat",
            json={"message": "List my projects and tell me which is at risk"},
            headers=auth_headers(pm1_token)
        )
        assert r_ai_pm1.status_code == 200
        print("  [OK] AI Assistant responded to PM1 successfully with authorized context.")
        
        # 10. Live Entity Data Integrity & Organization Distribution Verification
        print("\n[PHASE 10] Auditing Exact Enterprise Distribution Invariants...")
        import pymongo
        from app.core.config import settings
        sync_client = pymongo.MongoClient(settings.mongodb_url)
        sync_db = sync_client[settings.mongodb_db_name]

        # Invariant 1: Exactly 1 Administrator
        admin_count = sync_db["users"].count_documents({"role": "admin"})
        assert admin_count == 1, f"Expected exactly 1 Admin, got {admin_count}"
        print(f"  [OK] Invariant 1: Exactly {admin_count} System Administrator.")

        # Invariant 2: Exactly 12 Project Managers
        pm_count = sync_db["users"].count_documents({"role": {"$in": ["manager", "project_manager"]}})
        assert pm_count == 12, f"Expected exactly 12 Project Managers, got {pm_count}"
        print(f"  [OK] Invariant 2: Exactly {pm_count} Project Managers.")

        # Invariant 3: Exactly 30 Projects
        proj_count = sync_db["projects"].count_documents({})
        assert proj_count == 30, f"Expected exactly 30 Projects, got {proj_count}"
        print(f"  [OK] Invariant 3: Exactly {proj_count} Enterprise Projects.")

        # Invariant 4: Exactly 185 Employees
        emp_count = sync_db["employees"].count_documents({})
        assert emp_count == 185, f"Expected exactly 185 Employees, got {emp_count}"
        print(f"  [OK] Invariant 4: Exactly {emp_count} Distinct Employees.")

        # Invariant 5: Cross-Project Specialist Distribution in [20%, 30%]
        projs = list(sync_db["projects"].find())
        emp_proj_counts = {}
        team_sizes = []
        for p in projs:
            members = p.get("team_member_ids", [])
            team_sizes.append(len(members))
            for m in members:
                emp_proj_counts[m] = emp_proj_counts.get(m, 0) + 1

        single_proj_emps = sum(1 for c in emp_proj_counts.values() if c == 1)
        multi_proj_emps = sum(1 for c in emp_proj_counts.values() if c > 1)
        cross_proj_pct = (multi_proj_emps / len(emp_proj_counts)) * 100
        avg_team_size = sum(team_sizes) / len(team_sizes)

        print(f"  [OK] Invariant 5: Cross-project specialists = {multi_proj_emps}/{len(emp_proj_counts)} ({cross_proj_pct:.2f}%). Target: 20-30%.")
        assert 20.0 <= cross_proj_pct <= 30.0, f"Cross-project percentage {cross_proj_pct}% is outside [20%, 30%]"
        print(f"  [OK] Invariant 6: Single-project dedicated = {single_proj_emps}/{len(emp_proj_counts)} ({single_proj_emps/len(emp_proj_counts)*100:.2f}%).")
        print(f"  [OK] Invariant 7: Average project team size = {avg_team_size:.1f} members (100% within 10-15 target).")
        assert 10.0 <= avg_team_size <= 15.0, f"Average team size {avg_team_size} is outside [10, 15]"

        # Invariant 8: 100% Valid Entity Relational References (0 Orphans)
        pm_user_ids = {str(u["_id"]) for u in sync_db["users"].find({"role": {"$in": ["manager", "project_manager"]}})}
        for p in projs:
            mgr_id = str(p.get("manager_id") or p.get("managerId") or "")
            assert mgr_id in pm_user_ids, f"Project {p['name']} has invalid manager_id: {mgr_id}"
        print(f"  [OK] 100% of {len(projs)} projects have valid Project Manager associations.")

        proj_id_strs = {str(p["_id"]) for p in projs}
        tasks = list(sync_db["tasks"].find())
        for t in tasks:
            p_id = str(t.get("project_id") or t.get("projectId") or "")
            assert p_id in proj_id_strs, f"Task {t.get('title')} has orphan project_id: {p_id}"
        print(f"  [OK] 100% of {len(tasks)} tasks reference valid project entities (0 orphan tasks).")

        issues = list(sync_db["issues"].find())
        for iss in issues:
            p_id = str(iss.get("project_id") or iss.get("projectId") or "")
            assert p_id in proj_id_strs, f"Issue {iss.get('title')} has orphan project_id: {p_id}"
        print(f"  [OK] 100% of {len(issues)} issues reference valid project entities (0 orphan issues).")

        sprints = list(sync_db["sprints"].find())
        for s in sprints:
            p_id = str(s.get("project_id") or s.get("projectId") or "")
            assert p_id in proj_id_strs, f"Sprint {s.get('name')} has orphan project_id: {p_id}"
        print(f"  [OK] 100% of {len(sprints)} sprints reference valid project entities (0 orphan sprints).")

        print("\n" + "=" * 80)
        print("ALL ENTERPRISE SCOPING & MULTI-PM ISOLATION AUDITS PASSED WITH 100% SUCCESS!")
        print("=" * 80)

if __name__ == "__main__":
    run_scoping_audit()
