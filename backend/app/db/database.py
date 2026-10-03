# pyrefly: ignore [missing-import]
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

client: AsyncIOMotorClient = None


async def ensure_indexes(db):
    """Create essential indexes for frequently queried fields across collections."""
    try:
        # Users & Employees
        await db.users.create_index("email", unique=True)
        await db.employees.create_index("email", unique=True)
        await db.employees.create_index("user_id")
        
        # Projects & Sprints
        await db.projects.create_index("status")
        await db.projects.create_index("manager_id")
        await db.projects.create_index("team_member_ids")
        await db.sprints.create_index("project_id")

        # Tasks & Issues
        await db.tasks.create_index("project_id")
        await db.tasks.create_index("assignee_id")
        await db.tasks.create_index("status")
        await db.issues.create_index("project_id")
        await db.issues.create_index("assignee_id")

        # ML Predictions & Analytics
        await db.project_predictions.create_index("project_id", unique=True)
        await db.employee_risk_predictions.create_index("employee_id", unique=True)
        await db.recommendations.create_index([("projectId", 1), ("status", 1)])
        await db.recommendations.create_index([("project_id", 1), ("status", 1)])

        # Activities & Notifications
        await db.activities.create_index([("project_id", 1), ("created_at", -1)])
        await db.notifications.create_index([("userId", 1), ("isRead", 1)])
        await db.notifications.create_index([("user_id", 1), ("read", 1)])
    except Exception as e:
        print(f"Warning: Index creation encountered an issue: {e}")


async def connect_db():
    global client
    client = AsyncIOMotorClient(settings.mongodb_url)
    print(f"Connected to MongoDB: {settings.mongodb_url}")
    await ensure_indexes(client[settings.mongodb_db_name])


async def close_db():
    global client
    if client:
        client.close()
        print("MongoDB connection closed.")


def get_database():
    return client[settings.mongodb_db_name]
