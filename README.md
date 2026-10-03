# NexusAI — Enterprise Project Decision Intelligence System

## 1. Project Architecture & Overview

NexusAI is a full-stack Enterprise Project Management and Decision Intelligence platform that augments conventional agile project management workflows with machine learning predictions, explainable recommendation heuristics, automated workload optimization, document intelligence, and a grounded AI decision assistant.

### Architecture Flow:
```
React Frontend (Vite, TypeScript, Recharts, Lucide)
   │
   ▼ HTTP / REST (JWT Bearer Token, Role-Based Access Control)
FastAPI Backend (Python 3.12, Uvicorn, Pydantic V2)
   ├── Auth & RBAC Security Layer (Admin, Project Manager, Team Member)
   ├── Decision & Recommendation Services
   ├── Resource Optimization Engine
   ├── Document AI Extraction Pipeline (PyMuPDF, python-docx, openpyxl)
   ├── AI Decision Assistant (RBAC-Grounded Synthesis + LLM fallback)
   ├── ML Prediction Pipeline (Joblib, Scikit-Learn)
   │     ├── project_risk_model.pkl (RandomForestClassifier)
   │     ├── burnout_risk_model.pkl (RandomForestClassifier)
   │     ├── deadline_delay_model.pkl (GradientBoostingRegressor)
   │     └── budget_overrun_model.pkl (GradientBoostingRegressor)
   └── MongoDB Persistence (Motor AsyncIOMotorClient, Collections & Indexes)
```

---

## 2. Technology Stack

- **Backend:** FastAPI 0.111.0, Uvicorn 0.29.0, Motor 3.4.0, Pydantic 2.7.1, Python-Jose, Passlib (Bcrypt)
- **Database:** MongoDB 6.0+ (Motor async driver)
- **Machine Learning:** Scikit-Learn 1.4.2, NumPy 1.26.4, Pandas 2.2.2, Joblib 1.4.2
- **Document Processing:** PyMuPDF (fitz), python-docx, openpyxl
- **Frontend:** React 19, TypeScript 6.0, Vite 8.2, Axios, Recharts 3.10, Lucide-React
- **Styling:** Modular CSS & Glassmorphism design tokens

---

## 3. Directory Structure

```
d:/NexsusAI/
├── backend/
│   ├── app/
│   │   ├── api/             # 18 REST routers (auth, projects, tasks, predictions, etc.)
│   │   ├── core/            # Config (settings), Deps (RBAC), Security (JWT, bcrypt)
│   │   ├── db/              # MongoDB connection & index auto-provisioning
│   │   ├── models/          # Pydantic V2 schemas and response models
│   │   └── services/        # Recommendation, AI assistant, resource optimizer, etc.
│   ├── main.py              # Application entrypoint & CORS middleware
│   ├── audit_verification.py# Comprehensive backend integration audit suite
│   ├── smoke_test_phase8.py # AI Assistant & ML runtime smoke test
│   └── requirements.txt     # Locked production dependencies
├── frontend/
│   ├── src/
│   │   ├── components/      # Sidebar, Layout, Navigation
│   │   ├── context/         # AuthContext (JWT management, role state)
│   │   ├── pages/           # 14 views (Dashboard, Projects, Analytics, AI Assistant, etc.)
│   │   └── services/        # api.ts Axios client with auth interceptor
│   ├── package.json
│   └── vite.config.ts
├── ml/                      # ML inference modules & feature engineering pipelines
├── models/                  # Serialized .pkl models and scalers
└── uploads/                 # Secure document storage directory
```

---

## 4. Authentication & Role-Based Access Control (RBAC)

NexusAI enforces strict backend-level authorization on all sensitive routes:

| Role | Permissions & Data Isolation |
|---|---|
| **Admin** | Full system visibility; manage all users, projects, employees, and executive analytics. |
| **Project Manager** | Create & manage assigned projects, tasks, issues, sprints, workload optimizations, and scoped reports. |
| **Team Member** | View only assigned projects, tasks, issues, and personal workload. Management analytics, employee-wide burnout, executive reports, and project creation/deletion are strictly forbidden (HTTP 403). |

---

## 5. Machine Learning Models & Capabilities

All models run offline inference via Scikit-Learn without external API dependencies:

1. **Project Risk Prediction:** `RandomForestClassifier` — Predicts risk category (`LOW`, `MEDIUM`, `HIGH`) and health score from project velocity, overdue tasks, and budget metrics.
2. **Employee Burnout Risk:** `RandomForestClassifier` — Evaluates workload ratios, overtime hours, active task counts, and predicts burnout probability.
3. **Deadline Delay Prediction:** `GradientBoostingRegressor` — Estimates completion delays in days based on sprint velocity and remaining effort.
4. **Budget Overrun Prediction:** `GradientBoostingRegressor` — Predicts financial overrun amounts based on expenditure rates and project progress.

*Note on ML Data:* The models are trained on synthetic development datasets simulating enterprise sprint metrics. They are indicators and forecasting aids, not clinical or legally binding determinations.

---

## 6. AI Decision Assistant (Phase 8)

The NexusAI Decision Assistant provides grounded natural language decision intelligence:
- **RBAC Pre-Filtering:** Authorized data is fetched before prompt construction. Team members cannot probe employee-wide burnout or organization financial reserves.
- **Three-Tier Response Structure:** Clearly demarcates **Facts** (MongoDB live state), **ML Predictions** (Scikit-Learn inference), and **Recommendations** (Decision Engine).
- **Deterministic Grounded Fallback:** Operates with 100% functionality even when `AI_API_KEY` is not set or external LLMs fail.
- **Hallucination Prevention:** Inquiries about nonexistent projects are explicitly identified and rejected.

---

## 7. Enterprise Organization & Seeding

NexusAI features a realistic, relational/entity-based Multi-PM Enterprise Organization data model in MongoDB (1 Admin, 12 PMs, 30 Projects, 185 Employees, 540 Tasks, 90 Sprints, 124 Issues, 51 Recommendations):

### Deterministic Enterprise Seeder:
```bash
cd backend
python seed_enterprise_org.py
```

### Test Accounts:
- **Administrator:** `admin@nexusai.dev` (Password: `Password123!`) — Organization-wide visibility
- **Project Manager 1 (Financial Services):** `sarah@nexusai.dev` (Password: `Password123!`) — Manages 3 Banking projects
- **Project Manager 2 (Healthcare):** `marcus.vance@nexusai.dev` (Password: `Password123!`) — Manages 3 Healthcare projects
- **Project Managers 3–12:** `elena.rostova@nexusai.dev`, `david.kim@nexusai.dev`, etc. (Password: `Password123!`)
- **Team Member:** `member1@nexusai.com` (Password: `Password123!`) — Restricted to assigned tasks/projects

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
venv\Scripts\activate  # (Windows) or source venv/bin/activate (Linux/Mac)
pip install -r requirements.txt
python seed_enterprise_org.py
uvicorn main:app --port 8000 --reload
```
API Documentation will be live at `http://localhost:8000/docs`.

### Frontend Setup:
```bash
cd frontend
npm install
npm run dev
```
Access the application at `http://localhost:5173` (or `http://localhost:5174`).

---

## 9. Verification & Testing

The system includes comprehensive automated audit and runtime test suites:
- **Enterprise Multi-PM Scoping & RBAC Audit:** `python test_enterprise_scoping_audit.py` (10/10 phases PASS)
- **End-to-End Workflow Validation:** `python test_final_e2e_flow.py` (15/15 steps PASS)
- **AI Decision Assistant & Grounding Smoke Test:** `python smoke_test_phase8.py` (8/8 scenarios PASS)
- **Production Frontend Build:** `cd frontend && npm run build` (0 TypeScript / build errors)

---

## 10. Notes & Data Governance

1. **Development-Stage Predictive Intelligence:** The ML models are evaluated against controlled application test data and serve as operational forecasting aids, not clinical or legally binding determinations.
2. **Document OCR:** The Document AI pipeline extracts text natively from `.pdf`, `.docx`, `.txt`, `.csv`, and `.xlsx`. Scanned image-only PDFs require an external OCR engine.
3. **Multi-PM Isolation:** All API endpoints strictly enforce PM project isolation at the backend level. Unauthorized cross-PM access returns HTTP 403.
