import asyncio
from app.db.database import connect_db, get_database

async def inspect_pred():
    await connect_db()
    db = get_database()
    p = await db.project_predictions.find_one({"project_id": "6a85cc2bd25d6713737600a0"}) # NexusAI 2.0
    print("NexusAI 2.0 prediction doc:")
    print(p)
    
    p2 = await db.project_predictions.find_one({"project_id": "6a85941997238d6d29362527"}) # Alpha
    print("Alpha prediction doc:")
    print(p2)

if __name__ == "__main__":
    asyncio.run(inspect_pred())
