import sys
import os
import asyncio
from datetime import datetime, timedelta
# pyrefly: ignore [missing-import]
from passlib.context import CryptContext
# pyrefly: ignore [missing-import]
from motor.motor_asyncio import AsyncIOMotorClient
import random
from dotenv import load_dotenv

# Load env before importing settings
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env.example'))
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
# pyrefly: ignore [missing-import]
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


async def seed_data():
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client[settings.mongodb_db_name]

    print("Clearing existing data...")
    await db.users.delete_many({})
    await db.projects.delete_many({})
    await db.employees.delete_many({})
    await db.tasks.delete_many({})
    await db.sprints.delete_many({})
    await db.issues.delete_many({})
    await db.project_predictions.delete_many({})
    await db.employee_risk_predictions.delete_many({})
    await db.recommendations.delete_many({})
    await db.notifications.delete_many({})

    print("Seeding Users...")
    seed_password = settings.seed_admin_password
    if not seed_password:
        import string
        import secrets
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        seed_password = ''.join(secrets.choice(alphabet) for i in range(12))
        print(f"\n=========================================")
        print(f"GENERATED DEMO PASSWORD: {seed_password}")
        print(f"=========================================\n")

    admin_user = {
        "name": "Admin User",
        "email": "admin@nexusai.dev",
        "password_hash": get_password_hash(seed_password),
        "role": "admin",
        "created_at": datetime.utcnow()
    }
    result = await db.users.insert_one(admin_user)
    admin_id = str(result.inserted_id)

    pm_user = {
        "name": "Sarah Chen",
        "email": "sarah@nexusai.dev",
        "password_hash": get_password_hash(seed_password),
        "role": "project_manager",
        "created_at": datetime.utcnow()
    }
    result = await db.users.insert_one(pm_user)
    pm_id = str(result.inserted_id)

    print("Seeding Employees...")
    employees = [
        {
            "name": "Alex Rodriguez",
            "email": "alex@nexusai.dev",
            "role": "Backend Engineer",
            "specialization": "Backend",
            "skills": ["Python", "FastAPI", "MongoDB"],
            "weekly_capacity_hours": 40.0,
            "status": "active",
            "created_at": datetime.utcnow()
        },
        {
            "name": "Emma Watson",
            "email": "emma@nexusai.dev",
            "role": "Frontend Engineer",
            "specialization": "Frontend",
            "skills": ["React", "TypeScript", "CSS"],
            "weekly_capacity_hours": 40.0,
            "status": "active",
            "created_at": datetime.utcnow()
        },
        {
            "name": "David Kim",
            "email": "david@nexusai.dev",
            "role": "Cybersecurity Engineer",
            "specialization": "Cybersecurity",
            "skills": ["Security Auditing", "Penetration Testing"],
            "weekly_capacity_hours": 40.0,
            "status": "active",
            "created_at": datetime.utcnow()
        },
        {
            "name": "Maria Garcia",
            "email": "maria@nexusai.dev",
            "role": "QA Engineer",
            "specialization": "QA",
            "skills": ["Automated Testing", "Manual Testing"],
            "weekly_capacity_hours": 40.0,
            "status": "active",
            "created_at": datetime.utcnow()
        }
    ]
    employee_ids = []
    for emp in employees:
        result = await db.employees.insert_one(emp)
        employee_ids.append(str(result.inserted_id))

    print("Seeding Projects...")
    projects = [
        {
            "name": "Alpha E-Commerce Migration",
            "description": "Migrate legacy e-commerce platform to modern microservices architecture.",
            "status": "active",
            "priority": "high",
            "budget": 150000.0,
            "current_expenditure": 45000.0,
            "progress": 30.0,
            "manager_id": pm_id,
            "team_member_ids": employee_ids[:3],
            "created_at": datetime.utcnow(),
            "start_date": (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d"),
            "end_date": (datetime.utcnow() + timedelta(days=60)).strftime("%Y-%m-%d"),
        },
        {
            "name": "Beta Mobile App",
            "description": "Develop a new mobile app for customer loyalty program.",
            "status": "active",
            "priority": "medium",
            "budget": 80000.0,
            "current_expenditure": 75000.0,
            "progress": 60.0,
            "manager_id": pm_id,
            "team_member_ids": [employee_ids[1], employee_ids[3]],
            "created_at": datetime.utcnow(),
            "start_date": (datetime.utcnow() - timedelta(days=60)).strftime("%Y-%m-%d"),
            "end_date": (datetime.utcnow() + timedelta(days=10)).strftime("%Y-%m-%d"),
        },
        {
            "name": "Gamma Data Warehouse",
            "description": "Setup central data warehouse for enterprise reporting.",
            "status": "planning",
            "priority": "low",
            "budget": 50000.0,
            "current_expenditure": 0.0,
            "progress": 0.0,
            "manager_id": admin_id,
            "team_member_ids": [employee_ids[0]],
            "created_at": datetime.utcnow(),
        }
    ]
    project_ids = []
    for proj in projects:
        result = await db.projects.insert_one(proj)
        project_ids.append(str(result.inserted_id))

    # Update employees with assigned projects
    await db.employees.update_one({"_id": result.inserted_id}, {"$set": {"assigned_project_ids": [project_ids[0], project_ids[2]]}})
    # ... more complex mapping can be done here, but simple assignment is fine for now

    print("Seeding Tasks and Sprints...")
    sprint1 = {
        "name": "Sprint 1",
        "project_id": project_ids[0],
        "status": "active",
        "capacity_hours": 120.0,
        "planned_story_points": 40,
        "velocity": 0,
        "created_at": datetime.utcnow()
    }
    result = await db.sprints.insert_one(sprint1)
    sprint1_id = str(result.inserted_id)

    tasks = [
        {
            "title": "Setup API Gateway",
            "project_id": project_ids[0],
            "sprint_id": sprint1_id,
            "assignee_id": employee_ids[0],
            "status": "in_progress",
            "priority": "high",
            "estimated_hours": 16.0,
            "actual_hours": 8.0,
            "due_date": (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%d"),
            "created_at": datetime.utcnow()
        },
        {
            "title": "Design Login UI",
            "project_id": project_ids[0],
            "sprint_id": sprint1_id,
            "assignee_id": employee_ids[1],
            "status": "done",
            "priority": "medium",
            "estimated_hours": 8.0,
            "actual_hours": 8.0,
            "due_date": (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d"),
            "created_at": datetime.utcnow()
        },
        {
            "title": "Fix Authentication Bug",
            "project_id": project_ids[1],
            "assignee_id": employee_ids[2],
            "status": "todo",
            "priority": "critical",
            "estimated_hours": 4.0,
            "actual_hours": 0.0,
            "due_date": (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d"), # Overdue
            "created_at": datetime.utcnow()
        }
    ]
    for task in tasks:
        await db.tasks.insert_one(task)

    print("Seeding Issues...")
    issues = [
        {
            "title": "API Gateway timeout",
            "project_id": project_ids[0],
            "category": "backend",
            "severity": "high",
            "priority": "high",
            "status": "open",
            "created_at": datetime.utcnow()
        },
        {
            "title": "Memory leak in mobile app",
            "project_id": project_ids[1],
            "category": "performance",
            "severity": "critical",
            "priority": "critical",
            "status": "open",
            "created_at": datetime.utcnow()
        }
    ]
    for issue in issues:
        await db.issues.insert_one(issue)

    print("Demo data seeded successfully!")
    print(f"Login Email 1 (Admin): {admin_user['email']}")
    print(f"Login Email 2 (PM): {pm_user['email']}")
    client.close()

if __name__ == "__main__":
    asyncio.run(seed_data())
