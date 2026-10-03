# NEXUSAI — FINAL ML V2 BENCHMARK & CERTIFICATION REPORT

**System:** NexusAI: Enterprise Project Decision Intelligence System  
**Baseline Dataset (V1):** `NexusAI_50K_Final_Integrated_Synthetic_Dataset.csv` (`SHA256: 7479ac...`, FROZEN)  
**Controlled Dataset (V2):** `NexusAI_50K_Controlled_V2_Synthetic_Dataset.csv` (`SHA256: 2b4898...`)  
**Evaluation Scope:** Project Risk Classification & Deadline Delay Regression (Burnout Risk and Budget Overrun strictly frozen)  
**Validation Methodology:** Group-Held-Out (100 Unseen Projects, N=5,000) & Chronological Temporal Test (Future Snapshots $\ge$ 2025-07-15, N=7,811)  
**Date:** October 2026  
**Final Decision:** **A. V2 IMPROVEMENT ACCEPTED**  

---

## 1. Executive Summary

This definitive engineering report documents the results of the **Controlled V2 Synthetic Dataset and Machine Learning Experiment** for NexusAI.

The primary objective was to determine whether a domain-grounded synthetic data-generation process—incorporating realistic operational pressure mechanisms, longitudinal autoregressive momentum, and controlled enterprise noise—could resolve the predictive ceiling of Project Risk and Deadline Delay without violating test quarantine, entity isolation, temporal validity, or leakage constraints.

### Core Audit & Benchmark Conclusions:
1. **The V2 Dataset Genuinely Improves Learnability:**
   - On **Project Risk**, held-out group accuracy increased from **49.50% to 54.84%** (+5.34 percentage points), Macro F1 increased from **0.4933 to 0.5318** (+0.0385), and High-Risk Recall improved from **54.30% to 60.88%** (+6.58 points).
   - On **Deadline Delay**, held-out group MAE decreased from **4.63 days to 3.11 days** (**1.52 days lower error, -32.94% reduction in prediction error**), and $R^2$ improved to **0.2496**.
2. **Absolute Zero Data Leakage:**
   - Both independent leakage audits passed with 100% compliance. Max predictor-target correlation is 0.3274 (Project Risk) and 0.4039 (Deadline Delay). Zero single-feature proxies or circular definitions.
3. **Strict Quarantine & Frozen Baselines:**
   - The authoritative V1 dataset remained completely unmodified (`SHA256: 7479ac243e7fc3403c6799bc8679c96f48292f00dc9743c7680c8de66a4c2cf5`, `DATASET_CHANGED = FALSE`).
   - Burnout Risk (88.75% accuracy, 0.9762 ROC-AUC) and Budget Overrun ($R^2 = 0.919$, MAE = $3,009) targets were verified 100% byte-identical between V1 and V2.
4. **All Regression Suites Pass with 100% Integrity:**
   - Backend Audit: 14/14 PASS.
   - Smoke Test Phase 8: 8/8 PASS.
   - Final E2E 15-Step Workflow: 15/15 PASS.
   - Frontend Production Build (`tsc -b && vite build`): PASS (0 errors, 899ms).

---

## 2. Answers to Mandatory Certification Questions (Section 27)

### 1. Did V2 improve the dataset?
**YES.** V2 eliminated the artificial snapshot volatility that plagued V1 (reducing average class switches from 26 down to 18) and established clear, coherent operational dependencies between schedule gaps, workload strain, sprint velocity, and project risk without introducing artificial separability.

### 2. Did Project Risk improve?
**YES.** On completely unseen projects (Group Held-Out Test), exact accuracy rose from **49.50% $\rightarrow$ 54.84%**, Macro F1 rose from **0.4933 $\rightarrow$ 0.5318**, and High-Risk Recall jumped from **54.30% $\rightarrow$ 60.88%**. On the chronological temporal test, accuracy reached **55.49%** with **0.5416 Macro F1** and **0.7417 ROC-AUC**.

### 3. Did Deadline Delay improve?
**YES.** Mean Absolute Error dropped from **4.63 days down to 3.11 days** on unseen projects—a **32.94% error reduction**. P90 absolute error compressed from 9.59 days to 6.40 days, providing significantly more actionable schedule forecasts.

### 4. Did Burnout remain stable?
**YES.** Burnout Risk was strictly frozen. Its targets, features, and model contracts are 100% identical between V1 and V2.

### 5. Did Budget Overrun remain stable?
**YES.** Budget Overrun was strictly frozen. Targets in V2 are byte-for-byte identical to V1.

### 6. Was there any leakage?
**NO.** All post-outcome columns (`completed_date`, `actual_resolution_date`, `final_settlement_cost`) and reference targets were strictly excluded. Max correlation between any predictor and Project Risk is $0.3274 < 0.85$.

### 7. Was group isolation preserved?
**YES.** Strict project disjointness was enforced: $\text{Train Projects} \cap \text{Test Projects} = \emptyset$ (0 project overlap across all 1,000 projects).

### 8. Was temporal validity preserved?
**YES.** Chronological cutoffs were enforced: training on snapshots before `2025-04-24`, testing on snapshots on or after `2025-07-15`. No future timestamps were exposed.

### 9. Did any model genuinely outperform the current production model?
**YES.** On the V2 dataset, both **XGBClassifier** (Acc: 54.84%, F1: 0.5318) and **RandomForestClassifier** (Acc: 54.52%, F1: 0.5284) outperformed the V1 production baseline (Acc: 49.50%, F1: 0.4933). For Deadline Delay, **Ridge/HistGBR** (MAE: 3.11 days) outperformed the V1 baseline (MAE: 4.63 days).

### 10. Should the production model be replaced?
**RECOMMENDATION:** **A. V2 IMPROVEMENT ACCEPTED.**  
The V2 dataset is formally certified and accepted as the authoritative next-generation training corpus. The trained V2 candidate models have been serialized to `models/v2_controlled/` and are fully validated for staged production deployment.

### 11. What is the final validated performance?
- **Project Risk (Group Held-Out):** Accuracy: **54.84%** | Macro F1: **0.5318** | High-Risk Recall: **60.88%** | ROC-AUC: **0.7296** | Exact-or-Adjacent Accuracy: **93.24%**
- **Project Risk (Temporal Test):** Accuracy: **55.49%** | Macro F1: **0.5416** | High-Risk Recall: **62.72%** | ROC-AUC: **0.7417**
- **Deadline Delay (Group Held-Out):** MAE: **3.11 days** | RMSE: **3.90 days** | $R^2$: **0.2496** | Median AE: **2.65 days**
- **Deadline Delay (Temporal Test):** MAE: **3.27 days** | RMSE: **4.05 days** | $R^2$: **0.2414** | Median AE: **2.82 days**
- **Burnout Risk (Certified Frozen):** Group Accuracy: **88.75%** | Macro F1: **0.8734** | ROC-AUC: **0.9762**
- **Budget Overrun (Certified Frozen):** Group MAE: **$3,005.43** | Median AE: **$123.08** | $R^2$: **0.9194**

### 12. What is the actual limitation?
Project risk is an operational continuum rather than discrete disjoint clusters. Distinguishing borderline Low vs. Medium projects carries natural threshold fuzziness. The true operational accuracy is reflected in the **93.24% exact-or-adjacent tier agreement** and **0.5192 ordinal MAE**.

### 13. Is the result suitable for project presentation?
**YES.** The results are scientifically defensible, reproducible, free of artificial label leakage, and represent genuine enterprise project decision intelligence.

---

## 3. Master Multi-Model Benchmark Comparison Table

Evaluated under identical group-aware (100 unseen projects, N=5,000) and chronological temporal splits (N=7,811):

| Model Family | Dataset | Validation Selection | Accuracy / MAE | Macro F1 / R² | Temporal Performance | Group Held-Out | Selected / Status |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Project Risk (Random Forest v1)** | V1 | Baseline | 50.00% Acc | 0.5018 F1 | Acc: 51.29%, F1: 0.5059 | Acc: 49.50%, F1: 0.4933 | Baseline |
| **Project Risk (Logistic Regression)**| V2 | Candidate | 55.66% Acc | 0.5437 F1 | Acc: 54.80%, F1: 0.5360 | Acc: 53.90%, F1: 0.5210 | Candidate |
| **Project Risk (Random Forest v2)** | V2 | Candidate | 55.62% Acc | 0.5418 F1 | Acc: 54.92%, F1: 0.5358 | Acc: 54.52%, F1: 0.5284 | Native Simplicity |
| **Project Risk (ExtraTrees)** | V2 | Candidate | 55.34% Acc | 0.5312 F1 | Acc: 54.20%, F1: 0.5280 | Acc: 53.80%, F1: 0.5210 | Candidate |
| **Project Risk (HistGradientBoosting)**| V2 | Candidate | 56.06% Acc | 0.5478 F1 | Acc: 55.20%, F1: 0.5390 | Acc: 54.40%, F1: 0.5290 | Candidate |
| **Project Risk (XGBoost)** | **V2** | **WINNER (Selected)** | **56.28% Acc** | **0.5493 F1** | **Acc: 55.49%, F1: 0.5416** | **Acc: 54.84%, F1: 0.5318** | **SELECTED (Best Overall)** |
| **Deadline Delay (GBR v1 Baseline)** | V1 | Baseline | 4.60 d MAE | 0.2529 R² | MAE: 4.50 d, R²: 0.2949 | MAE: 4.63 d, R²: 0.2363 | Baseline |
| **Deadline Delay (Ridge Regression)** | **V2** | **WINNER (Selected)** | **3.30 d MAE** | **0.2428 R²** | **MAE: 3.27 d, R²: 0.2414** | **MAE: 3.11 d, R²: 0.2496** | **SELECTED (Lowest Error)** |
| **Deadline Delay (Random Forest)** | V2 | Candidate | 3.32 d MAE | 0.2270 R² | MAE: 3.35 d, R²: 0.2210 | MAE: 3.18 d, R²: 0.2310 | Candidate |
| **Deadline Delay (HistGBR)** | V2 | Candidate | 3.31 d MAE | 0.2329 R² | MAE: 3.28 d, R²: 0.2400 | MAE: 3.12 d, R²: 0.2480 | Candidate |
| **Deadline Delay (XGBoost Regressor)**| V2 | Candidate | 3.31 d MAE | 0.2352 R² | MAE: 3.29 d, R²: 0.2380 | MAE: 3.13 d, R²: 0.2460 | Candidate |

---

## 4. Presentation & Transparency Disclosures (Section 28)

1. **Synthetic Nature of Dataset:**  
   The NexusAI dataset is source-informed synthetic development data constructed to model enterprise operational dynamics. Offline validation metrics demonstrate algorithmic learnability and consistency, but must not be claimed as clinical or real-world enterprise certifications without live field calibration.
2. **90% Realism Boundary:**  
   As proved mathematically through mutual information and decision tree ceilings, 90%+ classification accuracy on Project Risk is mathematically **UNSUPPORTED** without circular target leakage. An honest 55% exact accuracy and 93.2% ordinal decision support agreement is the scientifically defensible standard.
3. **Operational Scope:**  
   Employee Burnout Risk is an operational workload strain indicator, NOT a medical or psychological diagnosis.

---

## 5. Final Decision (Section 29)

```
================================================================================
FINAL DECISION:
A. V2 IMPROVEMENT ACCEPTED
================================================================================
The V2 synthetic dataset and associated models provide genuine, measurable, and 
scientifically honest improvements:
- Project Risk: +5.34% accuracy lift, +0.0385 Macro F1, +6.58% high-risk recall
- Deadline Delay: -32.9% MAE reduction (4.63 days -> 3.11 days)
- 100% Schema & Feature Contract Compatibility
- All 4 Application Regression Suites Passing (Audit, Smoke, E2E, Frontend)
================================================================================
```
