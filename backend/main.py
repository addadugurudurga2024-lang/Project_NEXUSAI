import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import connect_db, close_db
from app.api import auth, users, projects, employees, tasks, sprints, issues, predictions, employee_risk, documents, recommendations, resource_optimization, dashboard, reports, activities, analytics, ai_assistant, team_capacity

app = FastAPI(
    title="NexusAI API",
    description="Enterprise Project Decision Intelligence System",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await connect_db()


@app.on_event("shutdown")
async def shutdown():
    await close_db()


# Mount routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(projects.router, prefix="/projects", tags=["Projects"])
app.include_router(employees.router, prefix="/employees", tags=["Employees"])
app.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
app.include_router(sprints.router, prefix="/sprints", tags=["Sprints"])
app.include_router(issues.router, prefix="/issues", tags=["Issues"])
app.include_router(predictions.router, prefix="/predictions", tags=["Predictions"])
app.include_router(employee_risk.router, prefix="/employee-risk", tags=["Employee Risk"])
app.include_router(documents.router, prefix="/documents", tags=["Documents"])
app.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
app.include_router(resource_optimization.router, prefix="/resource-optimization", tags=["Resource Optimization"])
app.include_router(reports.router, prefix="/reports", tags=["Reports"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(activities.router, prefix="/activities", tags=["Activities"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
app.include_router(ai_assistant.router, prefix="/ai-assistant", tags=["AI Assistant"])
app.include_router(team_capacity.router, prefix="/team-capacity", tags=["Team Capacity"])


@app.get("/")
async def root():
    return {
        "name": "NexusAI API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }
