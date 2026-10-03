import asyncio
from app.db.database import connect_db, get_database

async def check_all_preds():
    await connect_db()
    db = get_database()
    projects = await db.projects.find({}).to_list(100)
    print(f"Total projects: {len(projects)}")
    
    high_count = 0
    med_count = 0
    low_count = 0
    no_pred_count = 0
    
    for p in projects:
        pid = str(p["_id"])
        name = p.get("name")
        pred = await db.project_predictions.find_one({"project_id": pid})
        if pred:
            rc = pred.get("risk_class") or pred.get("risk_level")
            hs = pred.get("health_score")
            delay = pred.get("delay_days") if pred.get("delay_days") is not None else pred.get("predicted_delay_days")
            br = pred.get("budget_overrun_risk") or pred.get("budget_risk")
            if rc == "HIGH": high_count += 1
            elif rc == "MEDIUM": med_count += 1
            elif rc == "LOW": low_count += 1
            print(f"Project '{name}' (ID: {pid}): Risk={rc}, Health={hs}, Delay={delay}, BudgetRisk={br}")
        else:
            no_pred_count += 1
            print(f"Project '{name}' (ID: {pid}): NO PREDICTION")
            
    print(f"\nSummary: HIGH={high_count}, MEDIUM={med_count}, LOW={low_count}, NO_PRED={no_pred_count}")

if __name__ == "__main__":
    asyncio.run(check_all_preds())
