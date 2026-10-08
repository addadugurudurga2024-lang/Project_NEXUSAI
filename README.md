# NexusAI — Enterprise Project Decision Intelligence System

> **Architecture Core:**  
> **OBSERVE $\rightarrow$ PREDICT $\rightarrow$ IMMUTABLE SNAPSHOT $\rightarrow$ EXPLAIN $\rightarrow$ RECOMMEND $\rightarrow$ OPTIMIZE $\rightarrow$ WHAT-IF SIMULATION $\rightarrow$ DECIDE $\rightarrow$ REAL-WORLD OUTCOME $\rightarrow$ EVALUATE**

---

## 1. Project Architecture & Overview

NexusAI is an **Enterprise Project Management and Decision Intelligence Platform** designed for Multi-PM organizations. It augments traditional agile project management with machine learning predictions, explainable decision recommendations, automated resource workload optimization, an isolated in-memory What-If simulation engine, an audited Decision Log, team capacity-driven PM scoping, and an end-to-end ML Tracking & Performance Evaluation ledger.

### Full Stack Architecture Flow:
```text
React 19 Frontend (Vite 8, TypeScript, Recharts, Lucide Icons)
   │
   ▼ REST API (JWT Bearer Token, Multi-Role RBAC & PM Project/Employee Scoping)
FastAPI Backend (Python 3.12, Uvicorn, Pydantic V2)
   ├── Auth & Team Member Onboarding State Sync (/auth/signup, /auth/onboarding)
   ├── Team Capacity-Driven PM Employee Scoping Layer (/team-capacity, /employees)
   ├── Multi-PM Scoping & Project Isolation Layer (/projects, /tasks, /issues)
   ├── Machine Learning Inference Pipeline (Scikit-Learn, Joblib)
   │     ├── project_risk_model.pkl (RandomForestClassifier, v1.0)
   │     ├── burnout_risk_model.pkl (RandomForestClassifier, v1.0)
   │     ├── deadline_delay_model.pkl (GradientBoostingRegressor, v1.0)
   │     └── budget_overrun_model.pkl (GradientBoostingRegressor, v1.0)
   ├── ML Tracking & Outcome Evaluation Ledger (/predictions)
   │     ├── Immutable Prediction Snapshots (Feature vectors, Model metadata)
   │     ├── Authoritative Real-World Lifecycle Outcomes (Pending vs. Evaluated)
   │     └── Sample-Safe Metrics Engine (MAE, RMSE, Accuracy, F1, Trajectory)
   ├── What-If Simulation Engine (In-Memory Read-Only Sandbox, Zero Live Mutation)
   ├── Decision Intelligence & Audited Decision Log (/decisions)
   ├── Resource Optimization & Cross-PM Borrowing (/resource-optimization)
   ├── AI Decision Assistant (RBAC-Grounded Natural Language Synthesis)
   └── MongoDB Operational Database (Motor Async Driver, 34 Projects, 191 Employees)
         ├── db.projects, db.tasks, db.issues, db.employees
         ├── db.team_memberships (Authoritative PM Capacity & Allocation)
         ├── db.prediction_history (Immutable ML Snapshots & Outcome Audit)
         └── db.decision_records (Audited Management Decisions)
```

---

## 2. Platform Intelligence Lifecycle

NexusAI follows a strict closed-loop intelligence architecture:

1. **OBSERVE**: Aggregates real-time operational data across projects, tasks, sprints, defects, expenditures, and team capacity.
2. **PREDICT & SNAPSHOT**: Runs multi-model ML inference to forecast project risk tiers, completion delays in days, financial budget overruns, and individual team member burnout. Every production prediction automatically records an immutable snapshot into `db.prediction_history` with the exact feature vector and model metadata (`outcome_status: PENDING`).
3. **EXPLAIN**: Breaks down prediction drivers using feature importance weighting, schedule progress gaps, and workload distribution metrics.
4. **RECOMMEND**: Generates actionable, explainable intervention recommendations (e.g. scope trimming, workload rebalancing, critical defect prioritization).
5. **OPTIMIZE**: Detects skill gaps across teams and algorithms cross-PM specialist borrowing opportunities.
6. **WHAT-IF SIMULATION**: Enables Project Managers and Executives to test hypothetical scenario variations (resource additions, removals, borrowing, task reallocations, scope reduction, velocity boosts, budget changes) in an **in-memory read-only sandbox with 100% zero live MongoDB mutation safety**.
7. **DECIDE**: Formalizes simulation outcomes and AI recommendations into audited, immutable Decision Log records with tracked status, alternatives, and quantitative rationale.
8. **REAL-WORLD OUTCOME**: Observes authoritative lifecycle completion (actual end dates, audited financial spend, verified retrospectives) without fabricating ground truth.
9. **EVALUATE & AUDIT**: Quantifies model accuracy (MAE, RMSE, F1, Accuracy, Performance Trajectory) under strict sample-safety rules (`NO_EVALUATED_DATA`, `LIMITED_SAMPLE`, `SUFFICIENT_SAMPLE`).

---

## 3. Technology Stack

- **Backend:** FastAPI 0.111.0, Uvicorn 0.29.0, Motor 3.4.0 (MongoDB async), Pydantic 2.7.1 (V2), Python-Jose (JWT), Passlib (Bcrypt)
- **Database:** MongoDB 6.0+ (Local / Atlas cluster via Motor async driver)
- **Machine Learning:** Scikit-Learn 1.4.2, NumPy 1.26.4, Pandas 2.2.2, Joblib 1.4.2
- **Document Processing:** PyMuPDF (fitz), python-docx, openpyxl
- **Frontend:** React 19, TypeScript 6.0, Vite 8.2, Axios, Recharts 3.10, Lucide-React
- **Styling:** Modular CSS, dark-mode tokens, and glassmorphism UI design

---

## 4. Key Subsystems

### 4.1 ML Tracking & Outcome Evaluation Ledger
- **Immutable Snapshots**: Captures prediction timestamp, feature dictionary, model name/version, and predicted value. Deduplicates identical feature inferences within a 15-minute cooldown.
- **Ground Truth Integrity**: Outcomes are strictly `PENDING` until authoritative lifecycle milestones occur (e.g., actual completion date reached). Ground truth is never fabricated or synthesized.
- **Sample-Safe Evaluation**:
  - $N = 0$: `NO_EVALUATED_DATA`
  - $1 \le N < 5$: `LIMITED_SAMPLE` (preliminary warning indicator)
  - $N \ge 5$: `SUFFICIENT_SAMPLE`
- **Model Trajectory**: Tracks performance over time (`IMPROVING`, `STABLE`, `DETERIORATING`) based solely on real evaluated predictions.

### 4.2 Team Capacity-Driven PM Employee Scoping
- **Authoritative Source of Truth**: The active direct team membership in Team Capacity (`db.team_memberships`) governs which employees a PM manages, analyzes for burnout, and can assign to tasks or projects.
- **Strict Multi-PM Isolation**: PMs cannot view or assign members belonging exclusively to other PMs. Cross-PM borrowing is governed through explicit, audited specialist agreements.

### 4.3 What-If Simulation Engine
- **Supported Scenarios**: `RESOURCE_ADD`, `RESOURCE_REMOVE`, `RESOURCE_REALLOCATION`, `TASK_REALLOCATION`, `SCOPE_REDUCTION`, `SCHEDULE_CAPACITY_CHANGE`, `BUDGET_RESOURCE_CHANGE`.
- **Zero-Mutation Guarantee**: Executes strictly in-memory on read-only MongoDB snapshots. Live data remains untouched.

### 4.4 Decision Intelligence & Decision Log
- **Formalized Management Actions**: Connects ML insights and simulation findings directly to human decisions (`RESOURCE_REALLOCATION`, `SPRINT_RESCOPE`, `SCHEDULE_COMPRESSION`, etc.).
- **Audited Workflow**: Tracks decisions from `PENDING` $\rightarrow$ `APPROVED` / `REJECTED` $\rightarrow$ `EXECUTED` with quantitative rationale.

---

## 5. Security & Role-Based Access Control (RBAC)

| Role | Permissions & Data Isolation |
| :--- | :--- |
| **System Admin** | Global organization authority. Can access all 34 projects, 191 employees, organization-wide ML tracking performance, and all decision logs. |
| **Project Manager** | Full authority over managed projects and Team Capacity members. Accesses project-scoped ML tracking, What-If simulation, decision logging, and team onboarding. Unauthorized cross-PM access returns `403 Forbidden`. |
| **Team Member** | Restricted to assigned projects and tasks. Selects preferred PM upon signup. Cannot access management ML evaluation, employee burnout lists, What-If simulation, or decision creation (`403 Forbidden`). |

---

## 6. Directory Structure

```text
d:/NexsusAI/
├── backend/
│   ├── app/
│   │   ├── api/             # REST routers (auth, projects, tasks, predictions, decisions, etc.)
│   │   │   ├── prediction_tracking.py  # Prediction snapshots & outcome evaluation
│   │   │   ├── predictions.py          # ML inference execution
│   │   │   ├── team_capacity.py        # Team capacity & member allocations
│   │   │   └── ...
│   │   ├── core/            # Config, security (Bcrypt, JWT), deps (RBAC user resolution)
│   │   ├── db/              # MongoDB async driver & compound index initialization
│   │   ├── models/          # Pydantic V2 schemas (user, project, prediction_tracking, etc.)
│   │   └── services/        # Prediction tracking, scoping, simulation, decision intelligence
│   ├── main.py              # FastAPI application entrypoint & startup snapshot initialization
│   ├── seed_enterprise_org.py# Deterministic Multi-PM Enterprise Seeder (34 projects, 191 employees)
│   ├── test_ml_tracking_audit.py               # 15/15 Pass Dedicated ML Tracking Audit Suite
│   ├── test_prediction_outcome_tracking.py     # 25/25 Pass Outcome Tracking & Metrics Suite
│   ├── test_pm_employee_scoping_integrity.py   # 23/23 Pass PM Scoping & Database Integrity Suite
│   ├── test_team_capacity.py                   # 14/14 Pass Team Capacity & Onboarding Suite
│   ├── test_onboarding_state_sync.py           # 11/11 Pass Onboarding State Sync Suite
│   ├── test_what_if_simulation.py              # 13/13 Pass What-If Simulation Suite
│   ├── test_what_if_deadline_delay_audit.py    # 8/8 Pass Deadline Delay Regression Suite
│   ├── test_resource_remove_semantics.py       # 6/6 Pass Resource Semantic & Throughput Suite
│   ├── test_decision_intelligence.py           # 14/14 Pass Decision Intelligence Suite
│   └── test_notification_workflow.py           # 9/9 Pass Notification Workflow Suite
├── frontend/
│   ├── src/
│   │   ├── components/      # Navigation, Sidebar, Glassmorphic Cards
│   │   ├── context/         # AuthContext (JWT state, role RBAC, user profile)
│   │   ├── pages/           # Views (Dashboard, PredictionTracking, WhatIfSimulation, etc.)
│   │   │   ├── PredictionTracking.tsx   # ML Tracking & Performance Evaluation View
│   │   │   ├── PredictionTracking.css   # ML Tracking Styles & Cards
│   │   │   └── ...
│   │   └── services/        # Axios API client with bearer interceptors
│   ├── package.json
│   └── vite.config.ts
├── ml/                      # ML inference modules & feature engineering pipelines
└── models/                  # Serialized ML artifacts (.pkl) and StandardScaler models
```

---

## 7. Setup & Execution Instructions

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
Access the web dashboard at `http://localhost:5173`.

---

## 8. Automated Test Suites & Quality Gates

Run the automated test suites to verify system integrity and zero-defect execution:

```bash
cd backend
python test_ml_tracking_audit.py            # Dedicated ML Tracking Audit (15/15 PASS)
python test_prediction_outcome_tracking.py  # Prediction Snapshot & Outcome Evaluation (25/25 PASS)
python test_pm_employee_scoping_integrity.py# Team Capacity PM Scoping & Integrity (23/23 PASS)
python test_team_capacity.py                # Team Capacity Allocation & Onboarding (14/14 PASS)
python test_onboarding_state_sync.py        # Member Registration & State Sync (11/11 PASS)
python test_what_if_simulation.py           # What-If Simulation Sandbox (13/13 PASS)
python test_notification_workflow.py        # Multi-PM Notification Routing (9/9 PASS)
python test_decision_intelligence.py        # Audited Decision Log (14/14 PASS)
```

### Frontend Production Build:
```bash
cd frontend
npm run build   # Runs `tsc -b && vite build` (0 errors)
```
