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

## 7. Setup & Execution Instructions

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

## 8. Verification & Testing

The system includes automated audit and runtime test suites:
- **Phase 8 Smoke Test:** `python smoke_test_phase8.py` (8/8 scenarios PASS)
- **Technical Audit Suite:** `python audit_verification.py` (14/14 tasks PASS)
- **Production Build:** `npm run build` (TypeScript compilation & bundle generation clean)

---

## 9. Known Limitations

1. **Synthetic Training Data:** The ML models are built upon synthetic development data; in enterprise deployment, retraining on real historical sprint/Jira logs is recommended.
2. **Document OCR:** The Document AI pipeline extracts text natively from `.pdf`, `.docx`, `.txt`, `.csv`, and `.xlsx`. Scanned image-only PDFs require an external OCR engine (such as Tesseract).
3. **Single Database Instance:** Configured for single-node MongoDB connection; cluster replica sets should use standard connection string parameters in `.env`.
