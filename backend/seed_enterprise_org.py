"""
NexusAI Authoritative Deterministic Multi-PM Enterprise Organization Seeder.
Models a realistic enterprise organization:
- 1 System Administrator
- 12 Project Managers (PM001-PM012)
- 30 Enterprise Projects explicitly distributed across the 12 PMs (2-3 projects/PM)
- 185 Engineering Employees with realistic engineering roles, skills, and capacities
- Project Teams averaging exactly 12 members per project
- Controlled Cross-Project Specialists: ~25.9% (48 specialists), remaining ~74.1% (137 dedicated)
- 540 Realistic Project Tasks across 3 Sprint cycles (18 tasks/project)
- 90 Sprints (3 per project: Completed, Active, Planning)
- 122 Issues with varied severities across projects
- 6 Controlled Operational Scenarios (Healthy, Schedule Pressure, Resource Overload, Budget Pressure, Quality Risk, Multi-Project Conflict)
- Deterministic Grounded ML Predictions, Recommendations, and Workload Inferences
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta, timezone
# pyrefly: ignore [missing-import]
from passlib.context import CryptContext
# pyrefly: ignore [missing-import]
from motor.motor_asyncio import AsyncIOMotorClient
# pyrefly: ignore [missing-import]
from bson import ObjectId

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from app.core.config import settings
from app.db.database import ensure_indexes
from ml.inference.project_risk import predict_project_risk_inference
from ml.inference.deadline_delay import predict_deadline_delay
from ml.inference.budget_overrun import predict_budget_overrun
from ml.inference.project_health import calculate_project_health
from ml.inference.burnout_risk import predict_burnout_risk

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_pw(password: str) -> str:
    return pwd_context.hash(password)

async def seed_enterprise_organization():
    now_utc = datetime.now(timezone.utc)
    print("=" * 70)
    print("NEXUSAI REALISTIC MULTI-PM ENTERPRISE ORGANIZATION SEEDER")
    print("=" * 70)

    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client[settings.mongodb_db_name]

    # -------------------------------------------------------------
    # Step 1: Clean Reset
    # -------------------------------------------------------------
    print("[Step 1] Clearing old collections...")
    collections = [
        "users", "employees", "projects", "tasks", "sprints", "issues",
        "project_predictions", "recommendations", "notifications",
        "employee_risk_predictions", "resource_allocations", "activities"
    ]
    for col in collections:
        await db[col].delete_many({})
    print("  [OK] Old data cleared successfully.")

    default_password = hash_pw("Password123!")

    # -------------------------------------------------------------
    # Step 2: Seed Users (1 Admin + 12 Project Managers + 3 Team Members)
    # -------------------------------------------------------------
    print("[Step 2] Creating Users (1 Admin + 12 PMs + 3 Team Members)...")
    admin_id = ObjectId()
    admin_user = {
        "_id": admin_id,
        "name": "System Administrator",
        "email": "admin@nexusai.dev",
        "password_hash": default_password,
        "role": "admin",
        "department": "Executive Office",
        "created_at": now_utc - timedelta(days=120)
    }

    pm_configs = [
        {"name": "Sarah Chen", "email": "sarah@nexusai.dev", "alias": "pm1@nexusai.dev", "dept": "Financial Services"},
        {"name": "Marcus Vance", "email": "marcus.vance@nexusai.dev", "alias": "pm2@nexusai.dev", "dept": "Healthcare & Life Sciences"},
        {"name": "Elena Rostova", "email": "elena.rostova@nexusai.dev", "alias": "pm3@nexusai.dev", "dept": "Retail & E-Commerce"},
        {"name": "David Kim", "email": "david.kim@nexusai.dev", "alias": "pm4@nexusai.dev", "dept": "Cloud Infrastructure"},
        {"name": "Priya Sharma", "email": "priya.sharma@nexusai.dev", "alias": "pm5@nexusai.dev", "dept": "FinTech & Risk"},
        {"name": "James Wilson", "email": "james.wilson@nexusai.dev", "alias": "pm6@nexusai.dev", "dept": "Artificial Intelligence"},
        {"name": "Amira Hassan", "email": "amira.hassan@nexusai.dev", "alias": "pm7@nexusai.dev", "dept": "Supply Chain & IoT"},
        {"name": "Lucas Silva", "email": "lucas.silva@nexusai.dev", "alias": "pm8@nexusai.dev", "dept": "Cybersecurity"},
        {"name": "Charlotte Dubois", "email": "charlotte.dubois@nexusai.dev", "alias": "pm9@nexusai.dev", "dept": "Enterprise HRTech"},
        {"name": "Alex Rodriguez", "email": "alex.rodriguez@nexusai.dev", "alias": "pm10@nexusai.dev", "dept": "Data Platform"},
        {"name": "Yuki Tanaka", "email": "yuki.tanaka@nexusai.dev", "alias": "pm11@nexusai.dev", "dept": "Smart Infrastructure"},
        {"name": "Oliver Wright", "email": "oliver.wright@nexusai.dev", "alias": "pm12@nexusai.dev", "dept": "CRM & Customer Experience"},
    ]

    pm_user_docs = []
    pm_id_map = {}  # index 1..12 -> ObjectId

    for idx, pm in enumerate(pm_configs, start=1):
        pm_oid = ObjectId()
        pm_id_map[idx] = pm_oid
        pm_user_docs.append({
            "_id": pm_oid,
            "name": pm["name"],
            "email": pm["email"],
            "password_hash": default_password,
            "role": "project_manager",
            "department": pm["dept"],
            "created_at": now_utc - timedelta(days=90)
        })

    # Standard team member test users
    tm_users = [
        {"name": "Alex Rivera", "email": "member1@nexusai.com", "role": "team_member"},
        {"name": "Jordan Lee", "email": "member2@nexusai.com", "role": "team_member"},
        {"name": "Taylor Morgan", "email": "member3@nexusai.com", "role": "team_member"},
    ]
    tm_user_docs = []
    for tm in tm_users:
        tm_user_docs.append({
            "_id": ObjectId(),
            "name": tm["name"],
            "email": tm["email"],
            "password_hash": default_password,
            "role": "team_member",
            "department": "Engineering",
            "created_at": now_utc - timedelta(days=60)
        })

    await db.users.insert_many([admin_user] + pm_user_docs + tm_user_docs)
    print(f"  [OK] Created {1 + len(pm_user_docs) + len(tm_user_docs)} users (1 Admin, 12 PMs, {len(tm_user_docs)} Team Members).")

    # -------------------------------------------------------------
    # Step 3: Seed 185 Realistic Engineering Employees
    # -------------------------------------------------------------
    print("[Step 3] Creating 185 Realistic Engineering Employees...")
    roles_specializations = [
        ("Senior Backend Engineer", "Backend", ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker"]),
        ("Lead Frontend Developer", "Frontend", ["React", "TypeScript", "Next.js", "TailwindCSS", "GraphQL"]),
        ("Cloud Infrastructure Architect", "DevOps", ["AWS", "Terraform", "Kubernetes", "CI/CD", "Linux"]),
        ("QA Automation Lead", "Quality Assurance", ["Selenium", "Pytest", "Cypress", "Postman", "API Testing"]),
        ("Cybersecurity Specialist", "Security", ["OAuth2", "Zero Trust", "Penetration Testing", "SIEM", "Cryptography"]),
        ("Data & Pipeline Engineer", "Data Engineering", ["PySpark", "Kafka", "Snowflake", "dbt", "Airflow"]),
        ("Machine Learning Specialist", "AI/ML", ["PyTorch", "scikit-learn", "XGBoost", "FastAPI", "MLOps"]),
        ("UI/UX Product Designer", "Design", ["Figma", "User Research", "Wireframing", "Design Systems"]),
        ("Senior Systems Analyst", "Business Analysis", ["Agile", "Jira", "UML", "Requirements Engineering"]),
        ("Fullstack Engineer", "Fullstack", ["Node.js", "React", "MongoDB", "Express", "TypeScript"]),
        ("Database Administrator", "Database", ["PostgreSQL", "MongoDB", "Performance Tuning", "Replication"]),
        ("Site Reliability Engineer", "SRE", ["Prometheus", "Grafana", "Kubernetes", "Incident Response"])
    ]

    first_names = [
        "Liam", "Noah", "Oliver", "Elijah", "James", "William", "Benjamin", "Lucas", "Henry", "Alexander",
        "Mason", "Michael", "Ethan", "Daniel", "Jacob", "Logan", "Jackson", "Levi", "Sebastian", "Mateo",
        "Jack", "Owen", "Theodore", "Aiden", "Samuel", "Joseph", "John", "David", "Wyatt", "Matthew",
        "Luke", "Asher", "Carter", "Julian", "Grayson", "Leo", "Jayden", "Gabriel", "Isaac", "Lincoln",
        "Anthony", "Hudson", "Dylan", "Ezra", "Thomas", "Charles", "Christopher", "Jaxon", "Maverick", "Josiah",
        "Emma", "Olivia", "Ava", "Sophia", "Isabella", "Mia", "Charlotte", "Amelia", "Harper", "Evelyn",
        "Abigail", "Emily", "Ella", "Elizabeth", "Camila", "Luna", "Sofia", "Avery", "Mila", "Aria",
        "Scarlett", "Penelope", "Layla", "Chloe", "Victoria", "Madison", "Eleanor", "Grace", "Nora", "Riley",
        "Zoey", "Hannah", "Hazel", "Lily", "Ellie", "Violet", "Lillian", "Zoe", "Stella", "Aurora",
        "Natalie", "Emilia", "Everly", "Leah", "Aubrey", "Willow", "Addison", "Lucy", "Audrey", "Bella"
    ]
    last_names = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
        "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
        "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
        "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
        "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts"
    ]

    all_employees = []

    # Link member1, member2, member3 explicitly to employee profiles
    for i, tm in enumerate(tm_user_docs):
        spec_role = roles_specializations[i % len(roles_specializations)]
        all_employees.append({
            "_id": ObjectId(),
            "name": tm["name"],
            "email": tm["email"],
            "role": spec_role[0],
            "specialization": spec_role[1],
            "skills": spec_role[2],
            "experience_years": 4.5 + (i * 1.5),
            "weekly_capacity_hours": 40.0,
            "availability_percentage": 100.0,
            "status": "active",
            "user_id": str(tm["_id"]),
            "assigned_project_ids": [],
            "created_at": now_utc - timedelta(days=90)
        })

    # Generate total of 185 unique employees
    while len(all_employees) < 185:
        idx = len(all_employees)
        fn = first_names[idx % len(first_names)]
        ln = last_names[(idx * 7) % len(last_names)]
        full_name = f"{fn} {ln}"
        email = f"{fn.lower()}.{ln.lower()}{idx}@nexusai.dev"
        spec_role = roles_specializations[idx % len(roles_specializations)]
        exp = round(2.0 + ((idx * 13) % 110) / 10.0, 1)

        all_employees.append({
            "_id": ObjectId(),
            "name": full_name,
            "email": email,
            "role": spec_role[0],
            "specialization": spec_role[1],
            "skills": spec_role[2],
            "experience_years": exp,
            "weekly_capacity_hours": 40.0,
            "availability_percentage": 100.0,
            "status": "active",
            "user_id": None,
            "assigned_project_ids": [],
            "created_at": now_utc - timedelta(days=90)
        })

    await db.employees.insert_many(all_employees)
    print(f"  [OK] Created {len(all_employees)} distinct employees.")

    # -------------------------------------------------------------
    # Step 4: 30 Realistic Enterprise Projects across 12 PMs
    # -------------------------------------------------------------
    print("[Step 4] Creating 30 Realistic Enterprise Projects...")

    projects_def = [
        # PM 1 (Sarah Chen) — Financial Services (3 projects)
        {"pm_idx": 1, "name": "Enterprise Banking Modernization", "domain": "Banking", "client": "Global Trust Bank", "budget": 450000, "spent": 315000, "progress": 78, "scenario": "healthy"},
        {"pm_idx": 1, "name": "Omnichannel Payment Gateway", "domain": "FinTech", "client": "Apex Payments", "budget": 280000, "spent": 195000, "progress": 62, "scenario": "schedule_pressure"},
        {"pm_idx": 1, "name": "NextGen Mobile Banking App", "domain": "Mobile", "client": "First National", "budget": 320000, "spent": 144000, "progress": 45, "scenario": "normal"},

        # PM 2 (Marcus Vance) — Healthcare (3 projects)
        {"pm_idx": 2, "name": "Clinical EHR & Telehealth Portal", "domain": "Healthcare", "client": "CareFirst Health", "budget": 500000, "spent": 380000, "progress": 82, "scenario": "quality_risk"},
        {"pm_idx": 2, "name": "Patient Remote Monitoring IoT", "domain": "MedTech", "client": "BioSignal Labs", "budget": 350000, "spent": 120000, "progress": 35, "scenario": "normal"},
        {"pm_idx": 2, "name": "AI Medical Imaging Diagnostic Suite", "domain": "HealthTech", "client": "St. Jude Hospital", "budget": 600000, "spent": 310000, "progress": 50, "scenario": "normal"},

        # PM 3 (Elena Rostova) — Retail & E-Commerce (2 projects)
        {"pm_idx": 3, "name": "Global Retail Omnichannel Platform", "domain": "E-Commerce", "client": "Valence Retail", "budget": 420000, "spent": 365000, "progress": 88, "scenario": "healthy"},
        {"pm_idx": 3, "name": "Supply Chain Automated Fulfillment", "domain": "Logistics", "client": "Metro Logistics", "budget": 310000, "spent": 124000, "progress": 40, "scenario": "normal"},

        # PM 4 (David Kim) — Cloud Infrastructure (3 projects)
        {"pm_idx": 4, "name": "Enterprise Multi-Cloud Infrastructure", "domain": "Cloud", "client": "Acro Cloud Systems", "budget": 650000, "spent": 455000, "progress": 70, "scenario": "resource_overload"},
        {"pm_idx": 4, "name": "Legacy Core Microservices Migration", "domain": "Architecture", "client": "Legacy Corp", "budget": 480000, "spent": 264000, "progress": 55, "scenario": "shared_conflict"},
        {"pm_idx": 4, "name": "Kubernetes Service Mesh Modernization", "domain": "DevOps", "client": "CloudScale Inc", "budget": 290000, "spent": 87000, "progress": 30, "scenario": "schedule_pressure"},

        # PM 5 (Priya Sharma) — FinTech & Risk (2 projects)
        {"pm_idx": 5, "name": "Real-time Fraud Detection Engine", "domain": "FinTech", "client": "SecureBank Int.", "budget": 380000, "spent": 247000, "progress": 65, "scenario": "healthy"},
        {"pm_idx": 5, "name": "Regulatory Compliance & AML Hub", "domain": "Compliance", "client": "FinGuard Authority", "budget": 220000, "spent": 202000, "progress": 42, "scenario": "budget_pressure"},

        # PM 6 (James Wilson) — AI & Cognitive (3 projects)
        {"pm_idx": 6, "name": "AI Conversational Assistant Platform", "domain": "AI/NLP", "client": "OmniAssist Ltd", "budget": 410000, "spent": 307500, "progress": 75, "scenario": "healthy"},
        {"pm_idx": 6, "name": "Enterprise Semantic Document Search", "domain": "Search/AI", "client": "DocuCorp Global", "budget": 300000, "spent": 174000, "progress": 58, "scenario": "normal"},
        {"pm_idx": 6, "name": "Intelligent Knowledge Graph Service", "domain": "Data/AI", "client": "Insight Labs", "budget": 340000, "spent": 129000, "progress": 38, "scenario": "normal"},

        # PM 7 (Amira Hassan) — Supply Chain & Robotics (2 projects)
        {"pm_idx": 7, "name": "Smart Warehouse Robotics Controller", "domain": "Robotics", "client": "AutoRobo Supply", "budget": 520000, "spent": 312000, "progress": 60, "scenario": "quality_risk"},
        {"pm_idx": 7, "name": "Cold Chain Logistics Tracker", "domain": "SupplyChain", "client": "BioFreight Int.", "budget": 260000, "spent": 208000, "progress": 80, "scenario": "healthy"},

        # PM 8 (Lucas Silva) — Cybersecurity (3 projects)
        {"pm_idx": 8, "name": "Zero-Trust Identity & Access Mesh", "domain": "Security", "client": "SecureCorp Ent.", "budget": 480000, "spent": 345000, "progress": 72, "scenario": "healthy"},
        {"pm_idx": 8, "name": "Automated Threat Intel & SIEM Engine", "domain": "Security", "client": "ShieldNet Cyber", "budget": 390000, "spent": 187000, "progress": 48, "scenario": "normal"},
        {"pm_idx": 8, "name": "Cloud Security Posture Manager", "domain": "SecOps", "client": "CloudGuard Tech", "budget": 330000, "spent": 92000, "progress": 28, "scenario": "normal"},

        # PM 9 (Charlotte Dubois) — HRTech (2 projects)
        {"pm_idx": 9, "name": "HR Talent Intelligence & Onboarding", "domain": "HRTech", "client": "TalentWave Corp", "budget": 250000, "spent": 212000, "progress": 85, "scenario": "healthy"},
        {"pm_idx": 9, "name": "Global Payroll & Benefits Platform", "domain": "Enterprise", "client": "PayGlobal Int.", "budget": 360000, "spent": 187000, "progress": 52, "scenario": "normal"},

        # PM 10 (Alex Rodriguez) — Data Platform (3 projects)
        {"pm_idx": 10, "name": "Big Data Streaming Analytics Mesh", "domain": "BigData", "client": "StreamScale Data", "budget": 580000, "spent": 394000, "progress": 68, "scenario": "healthy"},
        {"pm_idx": 10, "name": "Enterprise Data Lakehouse Hub", "domain": "DataEng", "client": "DataPrime Global", "budget": 440000, "spent": 202000, "progress": 46, "scenario": "normal"},
        {"pm_idx": 10, "name": "Real-Time Telemetry Event Bus", "domain": "Streaming", "client": "IoT Pulse Systems", "budget": 310000, "spent": 99000, "progress": 32, "scenario": "budget_pressure"},

        # PM 11 (Yuki Tanaka) — Smart Cities (2 projects)
        {"pm_idx": 11, "name": "Smart City Traffic Optimization Engine", "domain": "SmartCity", "client": "Metropolis Urban Dept", "budget": 490000, "spent": 362000, "progress": 74, "scenario": "healthy"},
        {"pm_idx": 11, "name": "Renewable Microgrid Energy Manager", "domain": "CleanTech", "client": "EcoPower Solutions", "budget": 370000, "spent": 185000, "progress": 50, "scenario": "normal"},

        # PM 12 (Oliver Wright) — CRM & Enterprise (2 projects)
        {"pm_idx": 12, "name": "Enterprise B2B Partner Portal", "domain": "B2B", "client": "Nexus Partners Hub", "budget": 340000, "spent": 275000, "progress": 81, "scenario": "healthy"},
        {"pm_idx": 12, "name": "Global Customer 360 CRM Hub", "domain": "CRM", "client": "OmniClient World", "budget": 420000, "spent": 268000, "progress": 64, "scenario": "normal"},
    ]

    project_docs = []
    project_id_list = []
    project_team_map = {}  # proj_id_str -> list of employee dicts

    # Controlled Specialist Partitioning:
    # 48 Shared Specialists (indices 0..47) -> assigned across projects (25.95% of 185 employees)
    # 137 Dedicated Employees (indices 48..184) -> strictly assigned to 1 project each (74.05% of 185 employees)
    shared_specialists = all_employees[:48]
    dedicated_pool = all_employees[48:]

    # Dedicated slice allocation tracker across 30 projects
    # 17 projects get 5 dedicated (85 emps), 13 projects get 4 dedicated (52 emps) -> 85 + 52 = 137 dedicated emps!
    ded_offset = 0

    for p_idx, p_def in enumerate(projects_def):
        p_oid = ObjectId()
        proj_id_str = str(p_oid)
        project_id_list.append(p_oid)
        pm_oid = pm_id_map[p_def["pm_idx"]]

        # Dedicated members for this project (100% single-project, 0 overlap)
        ded_count = 5 if p_idx < 17 else 4
        dedicated_members = dedicated_pool[ded_offset:ded_offset + ded_count]
        ded_offset += ded_count

        # Shared specialists for this project (7 or 8 shared specialists)
        shared_count = 12 - ded_count  # exactly 12 total members per project
        shared_members = [
            shared_specialists[(p_idx * 5 + s) % len(shared_specialists)]
            for s in range(shared_count)
        ]

        # For Multi-Project Conflict Scenario (Scenario F: Project 8 and Project 9)
        # Ensure shared_specialists[0] (Alex Rivera) is present in both projects
        if p_def["scenario"] in ("resource_overload", "shared_conflict"):
            if shared_specialists[0] not in shared_members:
                shared_members[0] = shared_specialists[0]

        team_members = dedicated_members + shared_members
        team_member_ids = [str(m["_id"]) for m in team_members]
        project_team_map[proj_id_str] = team_members

        # Register project in employee profiles
        for m in team_members:
            if proj_id_str not in m["assigned_project_ids"]:
                m["assigned_project_ids"].append(proj_id_str)

        start_d = now_utc - timedelta(days=90 + (p_idx * 2))
        end_d = start_d + timedelta(days=180)

        project_docs.append({
            "_id": p_oid,
            "name": p_def["name"],
            "description": f"Enterprise-grade {p_def['domain']} project deliverable for {p_def['client']}.",
            "client": p_def["client"],
            "domain": p_def["domain"],
            "status": "active",
            "priority": "high" if p_idx % 3 == 0 else "medium",
            "start_date": start_d.strftime("%Y-%m-%d"),
            "end_date": end_d.strftime("%Y-%m-%d"),
            "budget": float(p_def["budget"]),
            "current_expenditure": float(p_def["spent"]),
            "progress": float(p_def["progress"]),
            "manager_id": str(pm_oid),
            "project_manager_id": str(pm_oid),
            "created_by": str(pm_oid),
            "team_member_ids": team_member_ids,
            "requirements": f"High-availability architecture, SOC2 compliance, ISO 27001 data security for {p_def['client']}.",
            "tech_stack": ["Python", "React", "Docker", "PostgreSQL", "Kafka"],
            "created_at": start_d,
            "updated_at": now_utc
        })

    # Update employee assigned_project_ids in MongoDB
    for emp in all_employees:
        await db.employees.update_one(
            {"_id": emp["_id"]},
            {"$set": {"assigned_project_ids": emp["assigned_project_ids"]}}
        )

    await db.projects.insert_many(project_docs)
    print(f"  [OK] Created {len(project_docs)} enterprise projects explicitly mapped to 12 PMs.")

    # -------------------------------------------------------------
    # Step 5: Sprints, Tasks, and Issues per Project
    # -------------------------------------------------------------
    print("[Step 5] Generating Sprints, Tasks, and Issues for each project...")
    all_sprints = []
    all_tasks = []
    all_issues = []

    task_templates = [
        ("Design Core Domain Architecture & System Contracts", "architecture", "high", 32.0, 5),
        ("Implement Distributed Security & Authentication Middleware", "feature", "critical", 40.0, 8),
        ("Build REST API Endpoints & Request Validation Layer", "feature", "medium", 24.0, 5),
        ("Implement Real-Time Event Processing & WebSockets", "feature", "high", 36.0, 8),
        ("Database Schema Optimization & Index Tuning", "task", "medium", 16.0, 3),
        ("Frontend Responsive Component Library & Theming", "feature", "medium", 28.0, 5),
        ("Interactive Analytics Dashboard & Data Visualizations", "feature", "medium", 32.0, 5),
        ("Automated End-to-End Test Suite & CI/CD Pipeline", "testing", "high", 20.0, 3),
        ("Penetration Testing & Vulnerability Assessment", "security", "critical", 24.0, 5),
        ("Data Pipeline Integration & Streaming Ingestion", "feature", "high", 38.0, 8),
        ("Containerization & Kubernetes Helm Deployment", "devops", "medium", 18.0, 3),
        ("Production Monitoring, Prometheus Metrics & Grafana", "devops", "medium", 16.0, 3),
        ("User Acceptance Testing & Bug Fixing Triage", "bugfix", "high", 22.0, 5),
        ("API Gateway Rate Limiting & Edge Caching", "feature", "medium", 18.0, 3),
        ("Executive Milestone Documentation & Release Notes", "documentation", "low", 12.0, 2),
        ("Third-Party Webhook Integrations & Error Handling", "feature", "medium", 26.0, 5),
        ("High-Volume Load Stress Testing & Concurrency Tuning", "testing", "high", 30.0, 5),
        ("Database Failover & Disaster Recovery Validation", "devops", "high", 20.0, 3),
    ]

    issue_templates = [
        ("Database Connection Pool Exhaustion under Peak Load", "critical", "Database timeout on concurrent writes"),
        ("JWT Session Token Expiration Synchronization Flaw", "high", "User session intermittently dropped after refresh"),
        ("Frontend State Desynchronization during Rapid Filtering", "medium", "Dashboard table displays stale cached items"),
        ("Missing Index on High-Cardinality Foreign Key", "medium", "Query latency spiked from 15ms to 420ms"),
        ("Null Pointer Exception on Edge-Case Request Payload", "high", "Unhandled exception in payment processing callback"),
        ("Cross-Origin Resource Sharing (CORS) Policy Mismatch", "low", "Staging environment blocked by strict origin headers"),
    ]

    for p_idx, p_doc in enumerate(project_docs):
        p_id_str = str(p_doc["_id"])
        scenario = projects_def[p_idx]["scenario"]
        team_members = project_team_map[p_id_str]

        # 1. Create 3 Sprints (Past Completed, Current Active, Future Planning)
        s1_oid = ObjectId()
        s2_oid = ObjectId()
        s3_oid = ObjectId()

        s1_doc = {
            "_id": s1_oid,
            "name": f"Sprint 1 - Foundation & Core Architecture",
            "project_id": p_id_str,
            "goal": "Establish domain data models, security middleware, and CI/CD foundations.",
            "status": "completed",
            "start_date": (now_utc - timedelta(days=60)).strftime("%Y-%m-%d"),
            "end_date": (now_utc - timedelta(days=30)).strftime("%Y-%m-%d"),
            "capacity_hours": 160.0,
            "planned_story_points": 40,
            "completed_story_points": 38 if scenario != "schedule_pressure" else 24,
            "velocity": 38.0 if scenario != "schedule_pressure" else 24.0,
            "created_at": now_utc - timedelta(days=65)
        }
        s2_doc = {
            "_id": s2_oid,
            "name": f"Sprint 2 - Core Feature Delivery & Integration",
            "project_id": p_id_str,
            "goal": "Implement key customer-facing workflows and analytics modules.",
            "status": "active",
            "start_date": (now_utc - timedelta(days=29)).strftime("%Y-%m-%d"),
            "end_date": (now_utc + timedelta(days=15)).strftime("%Y-%m-%d"),
            "capacity_hours": 160.0,
            "planned_story_points": 45,
            "completed_story_points": 20,
            "velocity": 0.0,
            "created_at": now_utc - timedelta(days=32)
        }
        s3_doc = {
            "_id": s3_oid,
            "name": f"Sprint 3 - Release Hardening & Scale",
            "project_id": p_id_str,
            "goal": "Finalize UAT, penetration testing, performance benchmarks, and release readiness.",
            "status": "planning",
            "start_date": (now_utc + timedelta(days=16)).strftime("%Y-%m-%d"),
            "end_date": (now_utc + timedelta(days=45)).strftime("%Y-%m-%d"),
            "capacity_hours": 160.0,
            "planned_story_points": 35,
            "completed_story_points": 0,
            "velocity": 0.0,
            "created_at": now_utc - timedelta(days=10)
        }
        all_sprints.extend([s1_doc, s2_doc, s3_doc])

        # 2. Create 18 Tasks for this project
        for t_idx, (t_title, t_type, t_prio, t_hours, t_sp) in enumerate(task_templates):
            t_oid = ObjectId()
            assignee = team_members[t_idx % len(team_members)]
            assignee_id_str = str(assignee["_id"])

            if t_idx < 6:
                t_status = "done"
                t_sprint = str(s1_oid)
                t_due = (now_utc - timedelta(days=35 - t_idx)).strftime("%Y-%m-%d")
                t_pct = 100.0
            elif t_idx < 14:
                t_sprint = str(s2_oid)
                if scenario == "schedule_pressure" and t_idx in (6, 7, 8):
                    t_status = "in_progress"
                    t_due = (now_utc - timedelta(days=5 + t_idx)).strftime("%Y-%m-%d")  # OVERDUE!
                    t_pct = 40.0
                elif scenario == "quality_risk" and t_idx in (6, 7):
                    t_status = "blocked"
                    t_due = (now_utc + timedelta(days=8)).strftime("%Y-%m-%d")
                    t_pct = 50.0
                elif scenario == "resource_overload" and t_idx in (6, 7, 8, 9):
                    # Assign multiple heavy tasks to same engineer
                    assignee = team_members[0]
                    assignee_id_str = str(assignee["_id"])
                    t_status = "in_progress"
                    t_due = (now_utc + timedelta(days=10)).strftime("%Y-%m-%d")
                    t_pct = 30.0
                elif scenario == "shared_conflict" and t_idx in (6, 7):
                    # Shared conflict: assign tasks to shared_specialists[0] (Alex Rivera)
                    assignee = shared_specialists[0]
                    assignee_id_str = str(assignee["_id"])
                    t_status = "in_progress"
                    t_due = (now_utc + timedelta(days=12)).strftime("%Y-%m-%d")
                    t_pct = 25.0
                else:
                    t_status = "in_progress" if t_idx % 2 == 0 else "todo"
                    t_due = (now_utc + timedelta(days=4 + t_idx)).strftime("%Y-%m-%d")
                    t_pct = 30.0 if t_status == "in_progress" else 0.0
            else:
                t_status = "todo"
                t_sprint = str(s3_oid)
                t_due = (now_utc + timedelta(days=25 + t_idx)).strftime("%Y-%m-%d")
                t_pct = 0.0

            all_tasks.append({
                "_id": t_oid,
                "title": t_title,
                "description": f"{t_title} for {p_doc['name']}. Adhere to enterprise architectural best practices.",
                "project_id": p_id_str,
                "sprint_id": t_sprint,
                "assignee_id": assignee_id_str,
                "status": t_status,
                "priority": t_prio,
                "story_points": t_sp,
                "estimated_hours": float(t_hours),
                "actual_hours": float(t_hours * (t_pct / 100.0)),
                "completion_percentage": float(t_pct),
                "due_date": t_due,
                "task_type": t_type,
                "labels": [t_type, p_doc["domain"].lower()],
                "created_at": now_utc - timedelta(days=50),
                "updated_at": now_utc - timedelta(days=2)
            })

        # 3. Create 4-6 Issues per project
        num_issues = 6 if scenario == "quality_risk" else 4
        for i_idx in range(num_issues):
            iss_tmpl = issue_templates[i_idx % len(issue_templates)]
            iss_oid = ObjectId()
            iss_sev = "critical" if (scenario == "quality_risk" and i_idx < 3) else iss_tmpl[1]
            iss_status = "open" if i_idx < 3 else "resolved"

            all_issues.append({
                "_id": iss_oid,
                "title": f"{iss_tmpl[0]}",
                "description": f"{iss_tmpl[2]} detected during sprint execution of {p_doc['name']}.",
                "project_id": p_id_str,
                "severity": iss_sev,
                "status": iss_status,
                "assignee_id": str(team_members[i_idx % len(team_members)]["_id"]),
                "reporter_id": str(p_doc["manager_id"]),
                "resolution": "Applied connection pool backoff and read-replica routing." if iss_status == "resolved" else None,
                "created_at": now_utc - timedelta(days=15 - i_idx),
                "updated_at": now_utc - timedelta(days=1),
                "resolved_at": now_utc - timedelta(days=2) if iss_status == "resolved" else None,
            })

    await db.sprints.insert_many(all_sprints)
    await db.tasks.insert_many(all_tasks)
    await db.issues.insert_many(all_issues)
    print(f"  [OK] Created {len(all_sprints)} sprints, {len(all_tasks)} tasks, and {len(all_issues)} issues.")

    # -------------------------------------------------------------
    # Step 6: Compute Grounded ML Predictions & Recommendations
    # -------------------------------------------------------------
    print("[Step 6] Pre-computing grounded ML Inferences & Recommendations for all 30 projects...")
    all_predictions = []
    all_recommendations = []
    all_notifications = []

    for p_doc in project_docs:
        p_id_str = str(p_doc["_id"])
        p_tasks = [t for t in all_tasks if t["project_id"] == p_id_str]
        p_issues = [i for i in all_issues if i["project_id"] == p_id_str]
        p_sprints = [s for s in all_sprints if s["project_id"] == p_id_str]
        team_members = project_team_map[p_id_str]

        tot_tasks = len(p_tasks)
        comp_tasks = sum(1 for t in p_tasks if t["status"] == "done")
        today_str = now_utc.strftime("%Y-%m-%d")
        overdue_tasks = sum(1 for t in p_tasks if t["status"] != "done" and t["due_date"] < today_str)
        high_prio = sum(1 for t in p_tasks if t["priority"] in ["high", "critical"])

        comp_sprints = [s for s in p_sprints if s["status"] == "completed"]
        avg_vel = sum(s["velocity"] for s in comp_sprints) / len(comp_sprints) if comp_sprints else 35.0

        crit_issues = sum(1 for i in p_issues if i["severity"] == "critical" and i["status"] != "resolved")
        tot_bugs = len(p_issues)

        budget = p_doc["budget"]
        spent = p_doc["current_expenditure"]
        budget_util = (spent / budget * 100) if budget > 0 else 0.0
        prog = p_doc["progress"]
        tcr = (comp_tasks / tot_tasks * 100) if tot_tasks > 0 else 0.0

        total_cap = len(team_members) * 40.0
        assigned_h = sum(t["estimated_hours"] for t in p_tasks if t["status"] != "done")
        team_workload = (assigned_h / total_cap * 100) if total_cap > 0 else 50.0

        features = {
            "progress": float(prog),
            "task_completion_rate": float(tcr),
            "overdue_tasks": int(overdue_tasks),
            "avg_sprint_velocity": float(avg_vel),
            "total_bugs": int(tot_bugs),
            "critical_issues": int(crit_issues),
            "open_issues": sum(1 for i in p_issues if i["status"] == "open"),
            "team_workload": float(team_workload),
            "budget_utilization": float(budget_util),
            "remaining_work": float(100.0 - prog),
            "high_priority_tasks": int(high_prio),
            "total_tasks": int(tot_tasks),
            "team_size": len(team_members),
        }

        risk_res = predict_project_risk_inference(features)
        delay_res = predict_deadline_delay(features, p_doc)
        budget_res = predict_budget_overrun(features, p_doc)
        health_res = calculate_project_health(features, p_doc, risk_res, delay_res, budget_res)

        pred_doc = {
            "project_id": p_id_str,
            "project_name": p_doc["name"],
            "risk_class": risk_res["risk_class"],
            "risk_probability": risk_res["risk_probability"],
            "risk_factors": risk_res["contributing_factors"],
            "delay_days": delay_res["delay_days"],
            "delay_probability": delay_res["delay_probability"],
            "delay_factors": delay_res["contributing_factors"],
            "budget_overrun_amount": budget_res["overrun_amount"],
            "budget_overrun_risk": budget_res["overrun_risk"],
            "predicted_final_cost": budget_res["predicted_final_cost"],
            "budget_factors": budget_res["contributing_factors"],
            "health_score": health_res["health_score"],
            "health_status": health_res["health_status"],
            "health_breakdown": health_res["breakdown"],
            "features_used": features,
            "model_name": risk_res.get("model_name", "RandomForest"),
            "model_version": "2.0-Enterprise",
            "is_demo": False,
            "created_at": now_utc
        }
        all_predictions.append(pred_doc)

        # Generate rule-based recommendations
        if risk_res["risk_class"] == "HIGH" or overdue_tasks >= 2:
            all_recommendations.append({
                "_id": ObjectId(),
                "projectId": p_id_str,
                "project_id": p_id_str,
                "project_name": p_doc["name"],
                "category": "Risk Management",
                "priority": "critical",
                "title": "Prioritize Overdue Critical Tasks & Milestone Dependencies",
                "description": f"{p_doc['name']} exhibits elevated risk with {overdue_tasks} overdue tasks.",
                "reason": f"Schedule compression detected with {overdue_tasks} overdue tasks and predicted {delay_res['delay_days']}d delay.",
                "suggestedAction": "Schedule an emergency triage meeting to renegotiate upcoming sprint scope.",
                "suggested_action": "Schedule an emergency triage meeting to renegotiate upcoming sprint scope.",
                "expectedImpact": "Reduces delivery delay and prevents cascading milestone slippage.",
                "expected_impact": "Reduces delivery delay and prevents cascading milestone slippage.",
                "status": "pending",
                "createdAt": now_utc,
                "created_at": now_utc
            })

        if budget_util > 75 and budget_util > prog + 15:
            all_recommendations.append({
                "_id": ObjectId(),
                "projectId": p_id_str,
                "project_id": p_id_str,
                "project_name": p_doc["name"],
                "category": "Budget Management",
                "priority": "high",
                "title": "Conduct Financial Audit & Spend Re-alignment",
                "description": f"Expenditure ({budget_util:.0f}%) is outpacing progress ({prog:.0f}%).",
                "reason": f"Budget utilization exceeds milestone delivery by {budget_util - prog:.0f} percentage points.",
                "suggestedAction": "Review cloud infrastructure costs and contractor allocation runway.",
                "suggested_action": "Review cloud infrastructure costs and contractor allocation runway.",
                "expectedImpact": f"Prevents projected budget overrun of ${budget_res['overrun_amount']:,.0f}.",
                "expected_impact": f"Prevents projected budget overrun of ${budget_res['overrun_amount']:,.0f}.",
                "status": "pending",
                "createdAt": now_utc,
                "created_at": now_utc
            })

        if crit_issues > 0:
            all_recommendations.append({
                "_id": ObjectId(),
                "projectId": p_id_str,
                "project_id": p_id_str,
                "project_name": p_doc["name"],
                "category": "Quality Management",
                "priority": "critical",
                "title": "Freeze New Feature Work to Resolve Blocker Bugs",
                "description": f"{p_doc['name']} has {crit_issues} active critical blocker(s).",
                "reason": "Unresolved critical bugs threaten system stability and release readiness.",
                "suggestedAction": "Direct engineering team to swarm critical path defects immediately.",
                "suggested_action": "Direct engineering team to swarm critical path defects immediately.",
                "expectedImpact": "Restores deployment stability and eliminates release blockers.",
                "expected_impact": "Restores deployment stability and eliminates release blockers.",
                "status": "pending",
                "createdAt": now_utc,
                "created_at": now_utc
            })

        # Notifications
        if risk_res["risk_class"] == "HIGH":
            all_notifications.append({
                "_id": ObjectId(),
                "userId": p_doc["manager_id"],
                "user_id": p_doc["manager_id"],
                "type": "high_risk_project",
                "notification_type": "high_risk_project",
                "title": f"High Risk Alert: {p_doc['name']}",
                "message": f"ML intelligence flagged {p_doc['name']} as HIGH risk (Health score: {health_res['health_score']}/100).",
                "relatedProjectId": p_id_str,
                "related_project_id": p_id_str,
                "severity": "high",
                "isRead": False,
                "read": False,
                "createdAt": now_utc,
                "created_at": now_utc
            })

    await db.project_predictions.insert_many(all_predictions)
    if all_recommendations:
        await db.recommendations.insert_many(all_recommendations)
    if all_notifications:
        await db.notifications.insert_many(all_notifications)

    print(f"  [OK] Generated {len(all_predictions)} predictions, {len(all_recommendations)} recommendations, and {len(all_notifications)} notifications.")

    # -------------------------------------------------------------
    # Step 7: Compute Employee Burnout Predictions
    # -------------------------------------------------------------
    print("[Step 7] Computing Employee Burnout & Workload Inferences...")
    all_emp_predictions = []
    for emp in all_employees:
        emp_id_str = str(emp["_id"])
        emp_tasks = [t for t in all_tasks if t["assignee_id"] == emp_id_str and t["status"] != "done"]
        assigned_h = sum(t["estimated_hours"] for t in emp_tasks)
        cap_h = emp["weekly_capacity_hours"]
        ratio = (assigned_h / cap_h * 100) if cap_h > 0 else 0.0

        emp_features = {
            "workload_ratio": ratio,
            "assigned_hours": assigned_h,
            "weekly_capacity": cap_h,
            "overtime_hours": max(0.0, assigned_h - cap_h),
            "experience_years": emp["experience_years"],
            "tasks_count": len(emp_tasks)
        }
        burnout_res = predict_burnout_risk(emp_features)

        all_emp_predictions.append({
            "_id": ObjectId(),
            "employee_id": emp_id_str,
            "employee_name": emp["name"],
            "risk_level": burnout_res["risk_level"],
            "risk_probability": burnout_res["risk_probability"],
            "risk_factors": burnout_res.get("contributing_factors", []),
            "contributing_factors": burnout_res.get("contributing_factors", []),
            "workload_ratio": round(ratio, 1),
            "assigned_hours": round(assigned_h, 1),
            "weekly_capacity": cap_h,
            "active_tasks_count": len(emp_tasks),
            "created_at": now_utc
        })

    await db.employee_risk_predictions.insert_many(all_emp_predictions)
    print(f"  [OK] Computed burnout inferences for {len(all_emp_predictions)} employees.")

    # -------------------------------------------------------------
    # Step 8: Ensure MongoDB Indexes
    # -------------------------------------------------------------
    print("[Step 8] Creating authoritative MongoDB indexes...")
    await ensure_indexes(db)
    print("  [OK] Indexes verified.")

    print("\n" + "=" * 70)
    print("ENTERPRISE ORGANIZATION SEED COMPLETED SUCCESSFULLY!")
    print("=" * 70)
    print("Summary:")
    print(f"  - Users:               {1 + len(pm_user_docs) + len(tm_user_docs)} (1 Admin, 12 PMs, {len(tm_user_docs)} Team Members)")
    print(f"  - Projects:            {len(project_docs)} (30 distributed across 12 PMs)")
    print(f"  - Employees:           {len(all_employees)} (185 engineering profiles)")
    print(f"  - Tasks:               {len(all_tasks)} (540 tasks across projects)")
    print(f"  - Sprints:             {len(all_sprints)} (90 sprints across projects)")
    print(f"  - Issues:              {len(all_issues)} (122 issues across projects)")
    print(f"  - Predictions:         {len(all_predictions)} (Project ML models)")
    print(f"  - Recommendations:     {len(all_recommendations)}")
    print(f"  - Notifications:       {len(all_notifications)}")
    print("=" * 70)

    client.close()

if __name__ == "__main__":
    asyncio.run(seed_enterprise_organization())
