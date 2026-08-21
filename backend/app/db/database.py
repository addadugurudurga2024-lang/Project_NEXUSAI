# pyrefly: ignore [missing-import]
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

client: AsyncIOMotorClient = None


async def connect_db():
    global client
    client = AsyncIOMotorClient(settings.mongodb_url)
    print(f"Connected to MongoDB: {settings.mongodb_url}")


async def close_db():
    global client
    if client:
        client.close()
        print("MongoDB connection closed.")


def get_database():
    return client[settings.mongodb_db_name]
