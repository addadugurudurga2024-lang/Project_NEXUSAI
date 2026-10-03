# NexusAI V2 Controlled Model Artifacts — Provenance & Status

This directory contains archived experimental artifacts generated during early V2 dataset evaluation runs.

## Artifact Inventory & Provenance

| Artifact Filename | Serialized Model Family | Purpose / Scope | Selected Benchmark Winner? | Active Production Model? | Provenance / Status |
|---|---|---|:---:|:---:|---|
| `project_risk_model_v2_dataset.pkl` | `RandomForestClassifier` | Candidate model trained on V2 dataset | **NO** (Selected winner: `XGBClassifier`) | **NO** (Production: `models/project_risk_model.pkl`, RF v1) | Pre-benchmark candidate artifact from initial V2 dataset training pass |
| `project_risk_scaler_v2_dataset.pkl` | `StandardScaler` (11 features) | Scaler for candidate RF model | **NO** | **NO** (Production: `models/project_risk_scaler.pkl`) | Scaler associated with candidate RF model |
| `deadline_delay_model_v2_dataset.pkl` | `GradientBoostingRegressor` | Candidate model trained on V2 dataset | **NO** (Selected winner: `Ridge`) | **NO** (Production: `models/deadline_delay_model.pkl`, GBR v1) | Pre-benchmark candidate artifact from initial V2 dataset training pass |
| `deadline_delay_scaler_v2_dataset.pkl` | `StandardScaler` (7 features) | Scaler for candidate GBR model | **NO** | **NO** (Production: `models/deadline_delay_scaler.pkl`) | Scaler associated with candidate GBR model |

## Critical Distinctions

1. **Active Production Models (`models/*.pkl`):**
   - Project Risk: `RandomForestClassifier` (11 features)
   - Deadline Delay: `GradientBoostingRegressor` (9 features)
   - Employee Burnout: `RandomForestClassifier` (6 features)
   - Budget Overrun: `GradientBoostingRegressor` (7 features)
   These are the active models loaded by `backend/` and `ml/inference/`.

2. **V2 Benchmark Selected Candidates (Documented in `v2_ml_benchmark_summary.json`):**
   - Project Risk: `XGBClassifier` (Validation Macro F1: 0.5493)
   - Deadline Delay: `Ridge` (Validation MAE: 3.30 days)

3. **Archived Candidate Artifacts (This Directory):**
   - The files in `models/v2_controlled/` are legacy pre-benchmark candidate models (`RandomForestClassifier` and `GradientBoostingRegressor`) generated during exploratory V2 model family training prior to final multi-model benchmark selection.
   - They are **NOT** the final benchmark winners (`XGBClassifier` / `Ridge`) and are **NOT** active in production.
   - They are preserved for audit lineage and immutability.
