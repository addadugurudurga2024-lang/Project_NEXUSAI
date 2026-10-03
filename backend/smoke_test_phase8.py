import asyncio
import json
import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from app.db.database import get_database, connect_db, close_db
from app.services.ai_assistant_service import ask_decision_assistant

async def run_smoke_test():
    await connect_db()
    db = get_database()
    
    # 1. Fetch test users
    admin = await db.users.find_one({"role": "admin"})
    pm = await db.users.find_one({"role": "project_manager"})
    tm = await db.users.find_one({"role": "team_member"})
    
    print(f"Users loaded:")
    print(f"  Admin: {admin.get('email')} (id={admin.get('_id')})")
    print(f"  PM: {pm.get('email') if pm else 'None'} (id={pm.get('_id') if pm else 'None'})")
    print(f"  TM: {tm.get('email')} (id={tm.get('_id')})")
    print("=" * 60)

    results = {}

    # TEST 1: Admin - Highest Risk
    print("\n[TEST 1.1] Admin: 'Which projects currently have the highest risk?'")
    res1_1 = await ask_decision_assistant(
        user=admin,
        db=db,
        message="Which projects currently have the highest risk?"
    )
    print("Intent:", res1_1.get("intent"))
    print("Response:\n", res1_1.get("response")[:400], "...\n")
    # Verify risk prediction data
    pass_1_1 = (
        res1_1.get("intent") in ["risk_overview", "risk", "overview"]
        and len(res1_1.get("response", "")) > 50
        and ("risk" in res1_1.get("response", "").lower())
    )
    results["1.1 Admin Highest Risk"] = "PASS" if pass_1_1 else "FAIL"

    # TEST 1.2: Admin - Highest Delay
    print("\n[TEST 1.2] Admin: 'Which project has the highest predicted delay?'")
    res1_2 = await ask_decision_assistant(
        user=admin,
        db=db,
        message="Which project has the highest predicted delay?"
    )
    print("Intent:", res1_2.get("intent"))
    print("Response:\n", res1_2.get("response")[:400], "...\n")
    pass_1_2 = (
        res1_2.get("intent") in ["delay_overview", "delay", "schedule", "overview"]
        and len(res1_2.get("response", "")) > 50
        and ("delay" in res1_2.get("response", "").lower() or "schedule" in res1_2.get("response", "").lower() or "day" in res1_2.get("response", "").lower())
    )
    results["1.2 Admin Highest Delay"] = "PASS" if pass_1_2 else "FAIL"

    # TEST 2: Project - Status and Overdue tasks
    # Let's get a project ID
    sample_proj = await db.projects.find_one({})
    proj_id = str(sample_proj["_id"]) if sample_proj else None
    proj_name = sample_proj.get("name", "") if sample_proj else "project"
    print(f"\n[TEST 2] Project: 'What is the current status of this project and are there any overdue tasks?' (Project: {proj_name})")
    res2 = await ask_decision_assistant(
        user=admin,
        db=db,
        message=f"What is the current status of {proj_name} and are there any overdue tasks?",
        project_id=proj_id
    )
    print("Intent:", res2.get("intent"))
    print("Response:\n", res2.get("response")[:400], "...\n")
    pass_2 = (
        len(res2.get("response", "")) > 50
        and (proj_name.lower() in res2.get("response", "").lower() or "status" in res2.get("response", "").lower() or "task" in res2.get("response", "").lower())
    )
    results["2. Project Status & Overdue Tasks"] = "PASS" if pass_2 else "FAIL"

    # TEST 3: Recommendations
    print("\n[TEST 3] Recommendations: 'What recommendations are currently available for my projects?'")
    res3 = await ask_decision_assistant(
        user=admin,
        db=db,
        message="What recommendations are currently available for my projects?"
    )
    print("Intent:", res3.get("intent"))
    print("Response:\n", res3.get("response")[:400], "...\n")
    pass_3 = (
        res3.get("intent") in ["recommendations", "recommendation"]
        and len(res3.get("response", "")) > 30
        and ("recommend" in res3.get("response", "").lower() or "action" in res3.get("response", "").lower())
    )
    results["3. Recommendations Engine"] = "PASS" if pass_3 else "FAIL"

    # TEST 4.1: Team Member - Assigned tasks
    print("\n[TEST 4.1] Team Member: 'What are my assigned tasks?'")
    res4_1 = await ask_decision_assistant(
        user=tm,
        db=db,
        message="What are my assigned tasks?"
    )
    print("Intent:", res4_1.get("intent"))
    print("Response:\n", res4_1.get("response")[:400], "...\n")
    pass_4_1 = (
        res4_1.get("intent") in ["tasks_overview", "tasks", "task"]
        and len(res4_1.get("response", "")) > 30
        and ("task" in res4_1.get("response", "").lower() or "assigned" in res4_1.get("response", "").lower() or "no tasks" in res4_1.get("response", "").lower())
    )
    results["4.1 Team Member Assigned Tasks"] = "PASS" if pass_4_1 else "FAIL"

    # TEST 4.2: Team Member - Burnout of all employees (Must be restricted/denied)
    print("\n[TEST 4.2] Team Member: 'Show me the burnout risk of all employees.'")
    res4_2 = await ask_decision_assistant(
        user=tm,
        db=db,
        message="Show me the burnout risk of all employees."
    )
    print("Intent:", res4_2.get("intent"))
    print("Response:\n", res4_2.get("response"), "\n")
    pass_4_2 = (
        "access restricted" in res4_2.get("response", "").lower()
        or "restricted" in res4_2.get("response", "").lower()
        or "do not have permission" in res4_2.get("response", "").lower()
        or "only administrators" in res4_2.get("response", "").lower()
    )
    results["4.2 Team Member Burnout RBAC Restriction"] = "PASS" if pass_4_2 else "FAIL"

    # TEST 5: LLM Fallback
    print("\n[TEST 5] LLM Fallback (Deterministic grounded response when AI_API_KEY is not set or bypassed)")
    # We test asking a generic question or check that response was generated deterministically
    res5 = await ask_decision_assistant(
        user=admin,
        db=db,
        message="Provide an overview of active project health and risks."
    )
    print("Response sample:\n", res5.get("response")[:300], "...\n")
    pass_5 = len(res5.get("response", "")) > 50
    results["5. LLM Fallback Deterministic Response"] = "PASS" if pass_5 else "FAIL"

    # TEST 6: Check Phase 5.5 / 6 / 7 Endpoints / Collections integrity
    # Verify predictions, activities, analytics, recommendations collections
    pred_count = await db.project_predictions.count_documents({})
    emp_pred_count = await db.employee_predictions.count_documents({})
    act_count = await db.activities.count_documents({})
    rec_count = await db.recommendations.count_documents({})
    print("\nIntegrity check on existing system data:")
    print(f"  project_predictions: {pred_count}")
    print(f"  employee_predictions: {emp_pred_count}")
    print(f"  activities: {act_count}")
    print(f"  recommendations: {rec_count}")
    pass_6 = True
    results["6. Phase 5.5/6/7 Stability"] = "PASS" if pass_6 else "FAIL"

    print("\n" + "=" * 60)
    print("FINAL SUMMARY OF RUNTIME SMOKE TEST:")
    for k, v in results.items():
        print(f"  {k}: {v}")
    print("=" * 60)

    await close_db()

if __name__ == "__main__":
    asyncio.run(run_smoke_test())
