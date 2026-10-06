# NexusAI — Enterprise Project Decision Intelligence System

> **Architecture Core:**  
> **OBSERVE $\rightarrow$ PREDICT $\rightarrow$ EXPLAIN $\rightarrow$ RECOMMEND $\rightarrow$ OPTIMIZE $\rightarrow$ WHAT-IF SIMULATION $\rightarrow$ DECIDE**

---

## 1. Project Architecture & Overview

NexusAI is an **Enterprise Project Management and Decision Intelligence Platform** designed for Multi-PM organizations. It augments traditional agile project management with machine learning predictions, explainable decision recommendations, automated resource workload optimization, an isolated in-memory What-If simulation engine, an audited Decision Log, and an RBAC-grounded AI assistant.

### Full Stack Architecture Flow:
```text
React 19 Frontend (Vite 8, TypeScript, Recharts, Lucide Icons)
   │
   ▼ REST API (JWT Bearer Token, Multi-Role RBAC & PM Project Scoping)
FastAPI Backend (Python 3.12, Uvicorn, Pydantic V2)
   ├── Auth & Team Member Onboarding State Sync (/auth/signup, /auth/onboarding)
   ├── Multi-PM Scoping & Project Isolation Layer
   ├── Machine Learning Inference Pipeline (Scikit-Learn, Joblib)
   │     ├── project_risk_model.pkl (RandomForestClassifier)
   │     ├── burnout_risk_model.pkl (RandomForestClassifier)
   │     ├── deadline_delay_model.pkl (GradientBoostingRegressor)
   │     └── budget_overrun_model.pkl (GradientBoostingRegressor)
   ├── What-If Simulation Engine (In-Memory Read-Only Sandbox, Zero Live Mutation)
   ├── Decision Intelligence & Audited Decision Log (/decisions)
   ├── Resource Optimization & Cross-PM Borrowing (/resource-optimization)
   ├── AI Decision Assistant (RBAC-Grounded Natural Language Synthesis)
   └── MongoDB Operational Database (Motor Async Driver, 30 Projects, 191 Employees)
```

---

## 2. Platform Intelligence Lifecycle

NexusAI follows a strict closed-loop intelligence architecture:

1. **OBSERVE**: Aggregates real-time operational data across projects, tasks, sprints, defects, expenditures, and team capacity.
2. **PREDICT**: Runs multi-model ML inference ($\text{RandomForest}$ & $\text{GradientBoosting}$) to forecast project risk tiers, completion delays in days, financial budget overruns, and individual team member burnout.
3. **EXPLAIN**: Breaks down prediction drivers using feature importance weighting, schedule progress gaps, and workload distribution metrics.
4. **RECOMMEND**: Generates actionable, explainable intervention recommendations (e.g. scope trimming, workload rebalancing, critical defect prioritization).
5. **OPTIMIZE**: Detects skill gaps across teams and algorithms cross-PM specialist borrowing opportunities.
6. **WHAT-IF SIMULATION**: Enables Project Managers and Executives to test hypothetical scenario variations (resource additions, removals, borrowing, task reallocations, scope reduction, velocity boosts, budget changes) in an **in-memory read-only sandbox with 100% zero live MongoDB mutation safety**.
7. **DECIDE**: Formalizes simulation outcomes and AI recommendations into audited, immutable Decision Log records with tracked status, alternatives, and quantitative rationale.

---

## 3. Technology Stack

- **Backend:** FastAPI 0.111.0, Uvicorn 0.29.0, Motor 3.4.0 (MongoDB async), Pydantic 2.7.1 (V2), Python-Jose (JWT), Passlib (Bcrypt)
- **Database:** MongoDB 6.0+ (Local / Atlas cluster via Motor async driver)
- **Machine Learning:** Scikit-Learn 1.4.2, NumPy 1.26.4, Pandas 2.2.2, Joblib 1.4.2
- **Document Processing:** PyMuPDF (fitz), python-docx, openpyxl
- **Frontend:** React 19, TypeScript 6.0, Vite 8.2, Axios, Recharts 3.10, Lucide-React
- **Styling:** Modular CSS, dark-mode tokens, and glassmorphism UI design

---

## 4. Directory Structure

```text
d:/NexsusAI/
├── backend/
│   ├── app/
│   │   ├── api/             # 20 REST routers (auth, projects, tasks, decisions, simulations, etc.)
│   │   ├── core/            # Config, security (Bcrypt, JWT), deps (RBAC user resolution)
│   │   ├── db/              # MongoDB async driver & index initialization
│   │   ├── models/          # Pydantic V2 schemas (user, project, decision, simulation, etc.)
│   │   └── services/        # Decision, simulation, resource optimizer, AI assistant, etc.
│   ├── main.py              # FastAPI application entrypoint & CORS middleware
│   ├── seed_enterprise_org.py# Deterministic Multi-PM Enterprise Seeder (30 projects, 191 employees)
│   ├── test_what_if_simulation.py               # 13/13 Pass What-If test suite
│   ├── test_what_if_deadline_delay_audit.py     # 8/8 Pass deadline delay regression suite
│   ├── test_resource_remove_semantics.py       # 6/6 Pass semantic & throughput audit suite
│   ├── test_decision_intelligence.py            # 14/14 Pass decision log test suite
│   ├── test_onboarding_state_sync.py            # 10/10 Pass onboarding state sync suite
│   ├── test_enterprise_scoping_audit.py        # 10/10 Pass multi-PM scoping suite
│   └── test_optimization_allocation_audit.py  # 8/8 Pass resource optimization suite
├── frontend/
│   ├── src/
│   │   ├── components/      # Navigation, Sidebar, Glassmorphic Cards
│   │   ├── context/         # AuthContext (JWT state, role RBAC, user profile)
│   │   ├── pages/           # 16 Views (Dashboard, WhatIfSimulation, Decisions, TeamCapacity, etc.)
│   │   └── services/        # Axios API client with bearer interceptors
│   ├── package.json
│   └── vite.config.ts
├── ml/                      # ML inference modules & feature engineering pipelines
└── models/                  # Serialized ML artifacts (.pkl) and StandardScaler models
```

---

## 5. Security & Role-Based Access Control (RBAC)

NexusAI enforces strict backend-level authorization on all sensitive endpoints:

| Role | Permissions & Data Isolation |
| :--- | :--- |
| **System Admin** | Global organization authority. Can simulate across any project, view executive decision logs, and manage all users. |
| **Project Manager** | Full authority over assigned projects. Can run What-If simulations, record formal decisions, reallocate tasks, borrow cross-PM candidates, and approve/reject team member onboarding requests. Isolated from other PMs' projects (HTTP 403). |
| **Team Member** | Restricted to assigned projects and tasks. Selects preferred PM upon signup. Cannot access management analytics, employee burnout lists, What-If simulation engine, or decision logging (HTTP 403). |

---

## 6. What-If Simulation Engine (Phase 2)

Allows PMs and Executives to model hypothetical project, schedule, resource, and budget decisions in-memory:

### Supported Scenario Types:
1. **`RESOURCE_ADD`**: Simulate adding engineers to reduce workload and accelerate delivery progress based on marginal capacity share.
2. **`RESOURCE_REMOVE`**: Simulate staff departures or downsizing to measure capacity loss and workload pressure.
3. **`RESOURCE_REALLOCATION`**: Simulate borrowing cross-PM specialist candidates to close detected role skill gaps.
4. **`TASK_REALLOCATION`**: Hand over task effort hours between team members to relieve individual burnout bottlenecks.
5. **`SCOPE_REDUCTION`**: Descope non-critical tasks from sprint to protect commit deadlines.
6. **`SCHEDULE_CAPACITY_CHANGE`**: Accelerate sprint velocity throughput to compress remaining backlog burn-down.
7. **`BUDGET_RESOURCE_CHANGE`**: Adjust project budget funding runway to absorb cost overruns.

### Zero-Mutation Guarantee:
The simulation service executes strictly in-memory on a read-only MongoDB project snapshot. Live projects, tasks, issues, employees, and team memberships remain **100% untouched**.

---

## 7. Decision Intelligence & Decision Log (Phase 1)

Formalizes management actions resulting from ML predictions, recommendations, and What-If simulations:
- **Decision Types**: `RESOURCE_REALLOCATION`, `SPRINT_RESCOPE`, `SCHEDULE_COMPRESSION`, `BUDGET_INVESTIGATION`, `QUALITY_FREEZE`, `BURNOUT_MITIGATION`, `RISK_ACCEPTANCE`.
- **Auditability**: Records observed facts, baseline vs. simulated predictions, trade-offs, selected alternatives, and decision rationale.
- **Workflow State**: Moves seamlessly from `PENDING` $\rightarrow$ `APPROVED` / `REJECTED` $\rightarrow$ `EXECUTED`.

---

## 8. Setup & Execution Instructions

### Prerequisites
- Python 3.11+
- Node.js 18+
- MongoDB running on `mongodb://localhost:27017`

### Backend Setup:
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows (or source venv/bin/activate on Linux/Mac)
pip install -r requirements.txt
python seed_enterprise_org.py
python main.py  # Runs Uvicorn on http://127.0.0.1:8000
```

### Frontend Setup:
```bash
cd frontend
npm install
npm run dev
```
Access the web dashboard at `http://localhost:5173` (or `http://localhost:5174`).

---

## 9. Verification & Automated Test Suites

Run the complete test suite to verify system integrity:

```bash
cd backend
python test_what_if_simulation.py           # What-If Simulation Engine (13/13 PASS)
python test_what_if_deadline_delay_audit.py # ML Deadline Inference Integrity (8/8 PASS)
python test_resource_remove_semantics.py   # Semantic & Throughput Audit (6/6 PASS)
python test_decision_intelligence.py        # Decision Log System (14/14 PASS)
python test_onboarding_state_sync.py        # Onboarding Approval Workflow (10/10 PASS)
python test_enterprise_scoping_audit.py    # Multi-PM Scoping & RBAC (10/10 PASS)
python test_optimization_allocation_audit.py# Resource Optimization (8/8 PASS)
```

### Frontend Production Build:
```bash
cd frontend
npm run build   # Runs `tsc -b && vite build` (0 errors)
```
