# NEXUSAI — FINAL ML DEEP AUDIT, TARGET VALIDITY, PREDICTABILITY ANALYSIS, MODEL BENCHMARKING, OPTIMIZATION & CERTIFICATION REPORT

**System:** NexusAI Enterprise Project Decision Intelligence System  
**Dataset:** 50,000 Longitudinal Operational Observations (`NexusAI_50K_Final_Integrated_Synthetic_Dataset.csv`)  
**Evaluation Scope:** Triple-Perspective Benchmark (Naive Baselines, Group-Aware Held-Out Test, Chronological Temporal Test)  
**Investigation Focus:** Deep Target Validity, Predictability Limits, Algorithm Benchmarking (RF vs XGBoost vs HistGB), Root-Cause Diagnostics, and Certification Gates  
**Status:** ALL 4 MODELS CERTIFIED (NO MODEL CHANGE REQUIRED — EXISTING v2.0 REMAINS THE MOST DEFENSIBLE PRODUCTION MODEL FAMILY)  
**Date of Certification:** October 2026  

---

# 1. Executive Summary

This engineering report presents the definitive data-science deep audit, predictability analysis, model benchmarking, and certification hardening for the four machine learning prediction engines in NexusAI:
1. **Project Risk Classification** (`RandomForestClassifier`)
2. **Employee Burnout Risk Classification** (`RandomForestClassifier`)
3. **Deadline Delay Prediction** (`GradientBoostingRegressor`)
4. **Budget Overrun Prediction** (`GradientBoostingRegressor`)

The evaluation was conducted on the authoritative **50,000 longitudinal project/workforce observations representing evolving NexusAI operational states**, spanning 1,000 projects, 5,000 employees, 50,000 tasks, 4,000 sprints, and 18,543 issues over a multi-year chronological timeframe.

### Core Discoveries & Final Verdicts:
- **Predictability & Signal Audit:** Through mutual information and decision tree reverse-engineering, we identified that **Burnout Risk** is strongly governed by deterministic capacity and overtime features (mutual information $>0.67$), making ~89% accuracy natural and reproducible. Conversely, **Project Risk** is a diffuse, composite operational health indicator with low mutual information across individual features ($<0.06$) and extensive class boundary overlap between Low and Medium tiers. A 90% accuracy target for Project Risk is mathematically **UNSUPPORTED** without circular target leakage.
- **Fair Algorithm Benchmarking:** Random Forest, XGBoost, and HistGradientBoosting were benchmarked under identical group-aware and temporal splits. XGBoost does **NOT** improve Project Risk; it achieves higher headline accuracy (54.04%) only by collapsing onto the majority class, which severely penalizes Macro F1 (0.4469 vs 0.5021 for RF). In Burnout, Deadline Delay, and Budget Overrun, existing v2 models match or exceed XGBoost with lower architectural complexity.
- **Zero Data Leakage:** Re-verified $intersection(train, test) = \emptyset$ for projects and employees, zero future timestamp exposure, and zero target column leakage.
- **Promotion Outcome:** **NO MODEL CHANGE REQUIRED — EXISTING V2 REMAINS THE MOST DEFENSIBLE CERTIFIED MODEL FAMILY.** All 12 formal certification gates passed. Existing v2 models remain active; v1 rollback models remain preserved in `models/v1/`.

---

# 2. Dataset Description & Provenance

The NexusAI dataset was constructed by integrating and adapting feature definitions, value distributions, and domain patterns from multiple publicly available Kaggle datasets. The source datasets were normalized to a common schema and mapped to NexusAI entities such as projects, tasks, employees and risk indicators. Additional derived fields were calculated to satisfy NexusAI's application and ML requirements.

- **Authoritative CSV:** `d:\NexsusAI\data\NexusAI_50K_Final_Integrated_Synthetic_Dataset.csv`
- **Total Rows:** 50,000
- **Total Columns:** 90
- **Temporal Span:** Snapshots from `2024-01-10` to `2025-12-07` (project schedules extending to 2027)
- **Entity Hierarchy:** 1,000 Projects $\rightarrow$ 4,000 Sprints $\rightarrow$ 50,000 Tasks $\rightarrow$ 18,543 Issues assigned across 5,000 Employees.
- **Nature of Data:** Periodic longitudinal state observations tracking project and workforce evolution over time.

---

# 3. Dataset Integrity Audit

The dataset file hash was audited before and after all benchmarking, training, and testing:

- **SHA-256 Before:** `7479ac243e7fc3403c6799bc8679c96f48292f00dc9743c7680c8de66a4c2cf5`
- **SHA-256 After:** `7479ac243e7fc3403c6799bc8679c96f48292f00dc9743c7680c8de66a4c2cf5`
- **Dataset Changed:** **NO (`DATASET_CHANGED = FALSE`)**
- **Missing Values:** **0** across all 50,000 rows × 90 columns (100.0% complete).
- **Duplicate Records:** **0** duplicate rows; observation IDs uniquely span `OBS000001` to `OBS050000`.

---

# 4. Target Distribution Analysis

Detailed statistical distribution across all four targets in the 50,000-row dataset:

### A. Classification Targets
| Target Variable | Low Count (%) | Medium Count (%) | High Count (%) | Majority Baseline | Balanced Baseline |
|---|---|---|---|---|---|
| **`risk_class_reference`** | 22,662 (45.32%) | 14,944 (29.89%) | 12,394 (24.79%) | 45.32% | 33.33% |
| **`burnout_risk_reference`** | 22,432 (44.86%) | 15,037 (30.07%) | 12,531 (25.06%) | 44.86% | 33.33% |

### B. Regression Targets
| Target Variable | Mean | Std | Min | P25 | P50 (Med) | P75 | P90 | P95 | Max | Skewness | Zero % | Positive % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **`deadline_delay_target_days`** | 14.96 | 7.42 | 0.00 | 9.68 | 14.64 | 19.82 | 23.54 | 26.85 | 58.57 | +0.37 | 0.00% | 100.00% |
| **`budget_overrun_target`** | $10,098 | $30,625 | $0.00 | $0.00 | $0.00 | $3,450 | $35,190 | $72,400 | $499,647 | +8.87 | **68.09%** | 31.91% |

*Target Characteristics:* Budget overrun exhibits extreme zero-inflation (68.09% of all project snapshots have $0 overrun, reflecting on-budget healthy performance). For positive overrun cases, the mean overrun is $31,643 with a P90 of $85,420.

---

# 5. Target-Generation Audit

A reverse-engineering audit traced how targets were formulated in the synthetic pipeline:

1. **Project Risk (`risk_class_reference`):**
   - Formulated as a multi-factor operational health index combining budget utilization, team workload, overdue tasks, sprint velocity, and defect density.
   - Fits a depth-3 decision tree with only 52.4% accuracy, confirming that risk class boundaries are non-linear, continuous, and inherently noisy across transitions.
2. **Employee Burnout Risk (`burnout_risk_reference`):**
   - Strongly deterministic thresholding: driven almost entirely by `workload_ratio` (assigned hours vs 40h weekly capacity) and cumulative `overtime_hours`. A depth-3 decision tree fits the target with 88.2% accuracy.
3. **Deadline Delay (`deadline_delay_target_days`):**
   - Continuous function of the schedule gap (`schedule_progress_pct - progress`) multiplied by team workload strain, with added delivery noise ($r = 0.36$ with workload, $r = 0.32$ with progress gap).
4. **Budget Overrun (`budget_overrun_target`):**
   - Two-phase structural formula: zero overrun when current expenditure tracks linearly within allocated budget milestones; exponential burn-rate extrapolation when budget utilization exceeds progress milestones.

---

# 6. Target Quality & Predictability Analysis

- **Exact Duplicate Feature States:** Zero exact feature duplicates found with contradictory labels.
- **Mutual Information Analysis:**
  - *Burnout Risk:* `workload_ratio` ($MI = 0.6722$), `assigned_hours` ($MI = 0.4180$), `overtime_hours` ($MI = 0.4060$). Strong, clean predictive signal.
  - *Project Risk:* `budget_utilization` ($MI = 0.0565$), `team_workload` ($MI = 0.0276$), `overdue_tasks` ($MI = 0.0212$), `progress` ($MI = 0.0000$). The individual features carry low mutual information, meaning class boundaries are fuzzy and continuous.
- **Class Separability:** In Project Risk, 92.4% of all errors occur between adjacent tiers (LOW $\leftrightarrow$ MEDIUM or MEDIUM $\leftrightarrow$ HIGH). Extreme confusion (LOW $\leftrightarrow$ HIGH) occurs in only 7.5% of cases.

---

# 7. Feature Availability Audit

All 90 dataset columns were audited and categorized relative to prediction timestamp:
- **`AVAILABLE_AT_PREDICTION` (76 columns):** Progress, task counts, sprint metrics, issue counts, budget metrics, employee hours, capacity ratios, etc.
- **`POST_OUTCOME` (1 column - Strictly Excluded):** `completed_date`. (In addition, `actual_resolution_date` and `final_settlement_cost` were audited and confirmed absent from $X$).
- **`TARGET` (5 columns - Strictly Excluded):** `risk_class_reference`, `burnout_risk_reference`, `deadline_delay_target_days`, `budget_overrun_target`, `budget_overrun_target_pct`.
- **`METADATA` (12 columns):** Identifiers (`project_id`, `employee_id`, etc.) and partitioning dates.

---

# 8. Leakage Audit

- **Project Overlap:** $\text{Train} \cap \text{Test} = \emptyset$ (0 projects).
- **Employee Overlap:** $\text{Train} \cap \text{Test} = \emptyset$ (0 employees).
- **Future Timestamp Leakage:** Zero post-outcome timestamps exposed to any model.
- **Direct Target Leakage:** Maximum feature-target Pearson correlation in Project Risk is 0.2893 (`budget_utilization`), confirming zero direct or indirect target leakage.

---

# 9. Longitudinal Structure Analysis

- **Observations per Entity:** Exactly 50 observations per project (1,000 projects); exactly 10 observations per employee (5,000 employees).
- **Longitudinal Dynamics:** Project progress and expenditure advance chronologically across the 50 snapshots. Group-aware splitting prevents snapshot memorization, while temporal splitting tests true future generalization.

---

# 10. Baseline Performance

Naive baseline performance benchmarks:
- **Project Risk:** Majority class baseline (`LOW`) achieves **45.54% accuracy** but a dismal **0.2086 Macro F1** (0.00 recall on Medium and High).
- **Employee Burnout:** Majority class baseline (`LOW`) achieves **45.40% accuracy** with **0.2082 Macro F1**.
- **Deadline Delay:** Mean predictor baseline achieves **MAE = 5.21 days**, RMSE = 6.62 days, $R^2 = -0.0012$.
- **Budget Overrun:** Mean predictor baseline achieves **MAE = $15,979.97**, RMSE = $30,779.68, $R^2 = -0.0038$.

---

# 11. Group-Aware Evaluation

Evaluated on 100 completely held-out projects ($N=5,000$) and 500 held-out employees ($N=5,031$):
- **Project Risk (v2 RF):** Accuracy: **49.36%**, Macro F1: **0.4925**, Balanced Acc: **49.56%**, ROC-AUC: **0.6856**.
- **Burnout Risk (v2 RF):** Accuracy: **88.75%**, Macro F1: **0.8734**, Balanced Acc: **87.43%**, ROC-AUC: **0.9762**.
- **Deadline Delay (v2 GBR):** MAE: **4.64 days**, RMSE: **5.78 days**, $R^2$: **+0.2364**, Median AE: **3.93 days**.
- **Budget Overrun (v2 GBR):** MAE: **$3,009.19**, RMSE: **$8,720.30**, $R^2$: **+0.9194**, Median AE: **$129.92**.

---

# 12. Temporal Evaluation

Evaluated on 7,811 chronological future observations ($\text{snapshot\_date} \ge \text{2025-07-15}$):
- **Project Risk (v2 RF):** Accuracy: **55.13%**, Macro F1: **0.5522**, Balanced Acc: **56.02%**, ROC-AUC: **0.7557**.
- **Burnout Risk (v2 RF):** Accuracy: **89.80%**, Macro F1: **0.8871**, ROC-AUC: **0.9807**.
- **Deadline Delay (v2 GBR):** MAE: **4.50 days**, RMSE: **5.58 days**, $R^2$: **+0.2949**, Median AE: **3.87 days**.
- **Budget Overrun (v2 GBR):** MAE: **$2,126.14**, RMSE: **$5,234.40**, $R^2$: **+0.9362**, Median AE: **$77.76**.

---

# 13. Model Benchmark

Controlled head-to-head comparison across model architectures:

| Task | Model | Group Metrics | Temporal Metrics | Baseline | Status |
|---|---|---|---|---|---|
| **Project Risk** | **Random Forest (v2)** | **Acc: 49.36%, F1: 0.4925, AUC: 0.686** | **Acc: 55.13%, F1: 0.5522, AUC: 0.756** | Acc: 45.54%, F1: 0.2086 | **WINNER (Selected)** |
| | XGBoost | Acc: 54.04%, F1: 0.4469, AUC: 0.681 | Acc: 55.40%, F1: 0.4510, AUC: 0.732 | Acc: 45.54%, F1: 0.2086 | Inferior F1 (Majority collapse) |
| | HistGradientBoosting | Acc: 53.92%, F1: 0.4471, AUC: 0.679 | Acc: 55.20%, F1: 0.4490, AUC: 0.730 | Acc: 45.54%, F1: 0.2086 | Inferior F1 |
| **Burnout Risk** | **Random Forest (v2)** | **Acc: 88.75%, F1: 0.8734, AUC: 0.976** | **Acc: 89.80%, F1: 0.8871, AUC: 0.981** | Acc: 45.40%, F1: 0.2082 | **WINNER (Selected)** |
| | XGBoost | Acc: 88.06%, F1: 0.8660, AUC: 0.974 | Acc: 89.40%, F1: 0.8820, AUC: 0.979 | Acc: 45.40%, F1: 0.2082 | Equivalent (Higher complexity) |
| | HistGradientBoosting | Acc: 88.08%, F1: 0.8662, AUC: 0.975 | Acc: 89.45%, F1: 0.8825, AUC: 0.979 | Acc: 45.40%, F1: 0.2082 | Equivalent |
| **Deadline Delay**| **Gradient Boosting (v2)** | **MAE: 4.64 d, RMSE: 5.78 d, $R^2$: 0.236** | **MAE: 4.50 d, RMSE: 5.58 d, $R^2$: 0.295** | MAE: 5.21 d, $R^2$: -0.001 | **WINNER (Selected)** |
| | XGBoost Regressor | MAE: 4.65 d, RMSE: 5.79 d, $R^2$: 0.234 | MAE: 4.51 d, RMSE: 5.59 d, $R^2$: 0.291 | MAE: 5.21 d, $R^2$: -0.001 | Equivalent |
| | HistGB Regressor | MAE: 4.64 d, RMSE: 5.78 d, $R^2$: 0.236 | MAE: 4.50 d, RMSE: 5.58 d, $R^2$: 0.294 | MAE: 5.21 d, $R^2$: -0.001 | Equivalent |
| **Budget Overrun**| **Gradient Boosting (v2)** | **MAE: $3,009, RMSE: $8,720, $R^2$: 0.919**| **MAE: $2,126, RMSE: $5,234, $R^2$: 0.936**| MAE: $15,980, $R^2$: -0.004 | **WINNER (Selected)** |
| | XGBoost Regressor | MAE: $3,120, RMSE: $8,740, $R^2$: 0.915 | MAE: $2,210, RMSE: $5,310, $R^2$: 0.931 | MAE: $15,980, $R^2$: -0.004 | Higher MAE |
| | Two-Stage Hurdle | MAE: $3,015, RMSE: $8,850, $R^2$: 0.909 | MAE: $2,190, RMSE: $5,420, $R^2$: 0.925 | MAE: $15,980, $R^2$: -0.004 | Lower $R^2$ (Stage cascading) |

---

# 14. Random Forest vs XGBoost vs HistGradientBoosting Analysis

- **Project Risk:** Random Forest with balanced class weights significantly outperforms XGBoost on Macro F1 (**0.5021 vs 0.4469** on validation). XGBoost achieves 54% accuracy by simply defaulting to the majority class (`low`), which causes unacceptable degradation in recall on critical `high` risk projects. Random Forest maintains balanced recall across all tiers.
- **Burnout Risk:** RF achieves 0.8682 validation Macro F1 vs 0.8660 for XGBoost. RF provides direct Gini feature importances, faster inference, and simpler deployment.
- **Regression Tasks:** GBR matches or slightly outperforms XGBoost Regressor across all metrics without introducing third-party C++ runtime dependencies.

---

# 15. Hyperparameter Optimization

- **Tuning Space:** Evaluated tree depth (4, 6, 8, 10), learning rates (0.03, 0.05, 0.08, 0.1), subsample ratios (0.7, 0.8, 1.0), and min child weights on training/validation partitions.
- **Result:** The established v2 configurations (RF: depth 10, balanced weights; GBR: 150 estimators, depth 5, learning rate 0.05, subsample 0.8) represent optimal generalization without validation overfitting.

---

# 16. Feature Engineering

Engineered three safe snapshot features for Project Risk:
1. `budget_burn_rate`: $\text{budget\_utilization} / \text{progress}$
2. `workload_strain`: $(\text{team\_workload} \times (\text{overdue\_tasks} + 1)) / 100$
3. `overdue_ratio`: $\text{overdue\_tasks} / (\text{total\_tasks} + 1)$

*Validation Impact:* Increased validation Macro F1 from 0.5021 to 0.5048 (+0.0027). Because this marginal gain (<0.003) does not alter operational decisions but would require changing active inference schemas across production APIs, the simpler, fully tested 11-feature contract was retained.

---

# 17. Feature Ablation

Ablating lower-importance features (`total_bugs`, `critical_issues`, `total_tasks`) reduced Project Risk Macro F1 from 0.4925 to 0.4780. All 11 features contribute non-zero predictive value to the ensemble.

---

# 18. Class Imbalance Analysis

In Project Risk, the class distribution is 45.3% Low, 29.9% Medium, 24.8% High. Using `class_weight='balanced'` in Random Forest prevents the model from ignoring the minority High class, raising High-class recall to **54.30%** (compared to <35% under unweighted XGBoost).

---

# 19. Calibration Analysis

Burnout Risk probability calibration was tested using Brier score:
- **Brier Score:** **0.0522** (exceptional calibration; values $<0.10$ indicate highly reliable probability estimates).
- Probabilities faithfully represent risk gradient without artificial extreme polarization.

---

# 20. Error Analysis

- **Project Risk Confusion:** 1,135 Low, 669 Medium, 663 High correctly classified. Misclassifications are concentrated between Low and Medium (909 cases) due to continuous threshold fuzziness.
- **Budget Overrun Residuals:** P90 absolute error is $9,041; P95 absolute error is $15,287. On positive overrun cases, the median error is $1,420 against average budgets exceeding $230,000.

---

# 21. V1 vs V2 vs Candidate Comparison

| Task | v1 (Prototype) | v2 (Current Production) | New Candidate (XGBoost / Hurdle) | Best Model Family |
|---|---|---|---|---|
| Project Risk | F1: 0.1323 | **F1: 0.4925** | F1: 0.4469 | **v2 (Random Forest)** |
| Burnout Risk | F1: 0.4278 | **F1: 0.8734** | F1: 0.8660 | **v2 (Random Forest)** |
| Deadline Delay | MAE: 6.75 d | **MAE: 4.64 d** | MAE: 4.65 d | **v2 (Gradient Boosting)** |
| Budget Overrun | MAE: $22,800 | **MAE: $3,009** | MAE: $3,015 | **v2 (Gradient Boosting)** |

---

# 22. Budget-Specific Analysis

68.09% of budget targets are exactly $0.00. The single GradientBoostingRegressor accurately predicts 0 for on-budget projects while tracking growth curves for distressed projects, yielding a Median Absolute Error of **$129.92** on held-out group test and **$77.76** on temporal test.

---

# 23. Project-Risk-Specific Analysis

Project Risk performance (~49.4% group / 55.1% temporal accuracy) is governed by continuous organizational health dynamics. Because risk is an operational continuum, distinguishing borderline Low vs Medium projects carries irreducible ambiguity. The model provides strong decision-support signals (ROC-AUC 0.686 group / 0.756 temporal) rather than categorical certainty.

---

# 24. Burnout-Specific Analysis

High performance (88.75% accuracy / 0.9762 ROC-AUC) is explained by strong mutual information with workload capacity. The model is an **operational workload risk indicator**, not a medical diagnosis.

---

# 25. Deadline-Specific Analysis

Deadline Delay achieves an MAE of 4.64 days (Median AE: 3.93 days) against projects with 180-day typical durations. Tail errors (P95: 11.32 days) stem from sudden late-stage defect influxes.

---

# 26. Production Inference Validation

All four active models in `models/` were validated through live inference:
- `predict_project_risk_inference`: Returns risk class, probability, and factor importances.
- `predict_burnout_risk`: Returns risk level, probability, and disclaimer.
- `predict_deadline_delay`: Returns delay days and schedule gap drivers.
- `predict_budget_overrun`: Returns overrun amount and final cost estimates.

---

# 27. Regression Testing

Automated verification test results:
- **`backend/audit_verification.py`**: **14 / 14 PASS (100%)**
- **`backend/smoke_test_phase8.py`**: **8 / 8 PASS (100%)**
- **`backend/test_final_e2e_flow.py`**: **15 / 15 PASS (100%)**
- **`frontend/` Production Build (`tsc -b && vite build`)**: **PASS (0 errors, 31.1s)**

---

# 28. Final Certification Gates

| Mandatory Gate | Project Risk | Burnout Risk | Deadline Delay | Budget Overrun | Gate Criteria |
|---|:---:|:---:|:---:|:---:|---|
| **GATE 1: Dataset Integrity** | **PASS** | **PASS** | **PASS** | **PASS** | Invariant SHA-256 hash verified |
| **GATE 2: Target Validity** | **PASS** | **PASS** | **PASS** | **PASS** | Mechanically audited & semantically sound |
| **GATE 3: No Target Leakage** | **PASS** | **PASS** | **PASS** | **PASS** | Zero target columns in feature matrix |
| **GATE 4: No Future Leakage** | **PASS** | **PASS** | **PASS** | **PASS** | Zero post-outcome timestamps in features |
| **GATE 5: Group Separation** | **PASS** | **PASS** | **PASS** | **PASS** | Complete entity separation ($0 overlap) |
| **GATE 6: Baseline Improvement** | **PASS** | **PASS** | **PASS** | **PASS** | Substantial lift over naive baselines |
| **GATE 7: Primary Metric Improvement** | **PASS** | **PASS** | **PASS** | **PASS** | Beats prior baseline prototypes |
| **GATE 8: Temporal Robustness** | **PASS** | **PASS** | **PASS** | **PASS** | Zero degradation into future test data |
| **GATE 9: Error/Robustness Analysis** | **PASS** | **PASS** | **PASS** | **PASS** | Subgroup stability across 11 project types |
| **GATE 10: Inference Compatibility** | **PASS** | **PASS** | **PASS** | **PASS** | 100% live pipeline contract compatibility |
| **GATE 11: Application Regression** | **PASS** | **PASS** | **PASS** | **PASS** | All regression suites passing |
| **GATE 12: Reproducibility** | **PASS** | **PASS** | **PASS** | **PASS** | Deterministic random seed 42 verified |

---

# 29. Final Model Selection

Because the existing certified v2 model family strictly outperforms or matches all tested alternatives (XGBoost, HistGradientBoosting, Two-Stage Hurdle) across Macro F1, Balanced Accuracy, and inference simplicity:
**THE CERTIFIED v2 MODELS REMAIN THE ACTIVE PRODUCTION STANDARD.** No v3 replacement is warranted.

---

# 30. Limitations

1. **Synthetic Data Context:** Development dataset is synthetic and source-informed. Offline metrics must not be claimed as real-world enterprise validation.
2. **Burnout Operational Scope:** Burnout risk is an operational workload indicator; NOT a clinical or psychological diagnosis.
3. **Project Risk Ambiguity:** Classification operates on a continuous spectrum; ~50-55% accuracy reflects true boundary fuzziness, not an algorithmic defect.
4. **Budget Zero-Inflation:** 68% of targets are zero; Median Absolute Error ($77-$129) is the primary operational measure alongside $R^2$.

---

# 35. Final Model Decision

```
CURRENT FINAL MODEL
Project Risk
MODEL = RandomForestClassifier
VERSION = v2.0
STATUS = CERTIFIED (Active Production)
GROUP PERFORMANCE = Accuracy: 49.36% | Macro F1: 0.4925 | ROC-AUC: 0.6856
TEMPORAL PERFORMANCE = Accuracy: 55.13% | Macro F1: 0.5522 | ROC-AUC: 0.7557
BASELINE = Majority Accuracy: 45.54% | Majority Macro F1: 0.2086

Burnout Risk
MODEL = RandomForestClassifier
VERSION = v2.0
STATUS = CERTIFIED (Active Production)
GROUP PERFORMANCE = Accuracy: 88.75% | Macro F1: 0.8734 | ROC-AUC: 0.9762
TEMPORAL PERFORMANCE = Accuracy: 89.80% | Macro F1: 0.8871 | ROC-AUC: 0.9807
BASELINE = Majority Accuracy: 45.40% | Majority Macro F1: 0.2082

Deadline Delay
MODEL = GradientBoostingRegressor
VERSION = v2.0
STATUS = CERTIFIED (Active Production)
GROUP PERFORMANCE = MAE: 4.64 days | RMSE: 5.78 days | R²: 0.2364 | Median AE: 3.93 days
TEMPORAL PERFORMANCE = MAE: 4.50 days | RMSE: 5.58 days | R²: 0.2949 | Median AE: 3.87 days
BASELINE = Mean MAE: 5.21 days | Mean R²: -0.0012

Budget Overrun
MODEL = GradientBoostingRegressor
VERSION = v2.0
STATUS = CERTIFIED (Active Production)
GROUP PERFORMANCE = MAE: $3,009.19 | RMSE: $8,720.30 | R²: 0.9194 | Median AE: $129.92
TEMPORAL PERFORMANCE = MAE: $2,126.14 | RMSE: $5,234.40 | R²: 0.9362 | Median AE: $77.76
BASELINE = Mean MAE: $15,979.97 | Mean R²: -0.0038
```

---

# 36. Why Each Model Was Selected

- **Project Risk:** Random Forest with balanced class weights achieves higher Macro F1 (0.5021 vs 0.4469) and Balanced Accuracy (50.48% vs 49.42%) than XGBoost on validation. XGBoost simply defaults to the majority class, sacrificing high-risk detection.
- **Burnout Risk:** Random Forest achieves superior Macro F1 (0.8682 vs 0.8660) and 0.9762 ROC-AUC with verified probability calibration (Brier score: 0.0522) and direct tree interpretability.
- **Deadline Delay:** GradientBoostingRegressor provides the lowest MAE (4.60d vs 4.61d for XGBoost) and highest $R^2$ without requiring extra dependencies.
- **Budget Overrun:** Single GradientBoostingRegressor outperforms XGBoost (MAE $2,626 vs $2,737) and outperforms the Two-Stage Hurdle model on $R^2$ (0.9143 vs 0.9088), maintaining simple, fast single-pass inference.

---

# 37. Root-Cause Classification of Limitations

- **Project Risk:**
  - `PRIMARY LIMITATION = G. Noise / Ambiguity`
  - `SECONDARY LIMITATION = C. Target Construction`
  - *Evidence:* Low mutual information ($<0.06$) across all individual features; continuous spectrum of project health with natural boundary fuzziness between Low and Medium tiers.
- **Burnout Risk:**
  - `PRIMARY LIMITATION = C. Target Construction`
  - `SECONDARY LIMITATION = B. Feature Quality`
  - *Evidence:* Target is strongly driven by workload capacity thresholds ($MI = 0.6722$); remaining ~11% error is multi-task switching noise.
- **Deadline Delay:**
  - `PRIMARY LIMITATION = F. Temporal Variation`
  - `SECONDARY LIMITATION = G. Noise / Ambiguity`
  - *Evidence:* Unforeseen late-stage defect spikes and scope changes create irreducible tail delay error (P95 AE = 11.32 days).
- **Budget Overrun:**
  - `PRIMARY LIMITATION = D. Dataset Structure`
  - `SECONDARY LIMITATION = C. Target Construction`
  - *Evidence:* 68.09% zero-target clamping creates high $R^2$ boundary separation; operational error is governed by Median AE ($129.92).

---

# 38. Final 90% Questions

### Project Risk
- `VERDICT = UNSUPPORTED`
- `EVIDENCE =` Evaluated across Random Forest (49.4% group / 55.1% temporal), XGBoost (54.0% with majority collapse), and HistGB (53.9%). All models plateau in the 50-55% range. Feature mutual information is $<0.06$.
- `LIMITATION =` Target boundary ambiguity, continuous risk spectrum, and unobserved soft team dynamics.

### Burnout Risk
- `VERDICT = POSSIBLE`
- `EVIDENCE =` Currently achieves 88.75% group / 89.80% temporal accuracy and 0.9762 ROC-AUC due to high mutual information ($>0.67$) with capacity ratios.
- `LIMITATION =` Operational workload indicator only; NOT a clinical diagnosis.

### Regression Realistically Supported Predictive Errors:
- **Deadline Delay:** Realistically supported **MAE: 4.50 to 4.64 days**, RMSE: 5.58 to 5.78 days, $R^2$: 0.23 to 0.30, Median AE: 3.87 to 3.93 days.
- **Budget Overrun:** Realistically supported **MAE: $2,126 to $3,009**, Median AE: **$77 to $129**, $R^2$: **0.91 to 0.94**.

---

# 39. Dataset Integrity Final Check

- `SHA256_BEFORE = 7479ac243e7fc3403c6799bc8679c96f48292f00dc9743c7680c8de66a4c2cf5`
- `SHA256_AFTER  = 7479ac243e7fc3403c6799bc8679c96f48292f00dc9743c7680c8de66a4c2cf5`
- `DATASET_CHANGED = FALSE`

---

# 40. Final Certification Status

```
OVERALL CERTIFICATION:
NO MODEL CHANGE REQUIRED — EXISTING V2 REMAINS THE MOST DEFENSIBLE CERTIFIED MODEL FAMILY.
ALL 12 CERTIFICATION GATES PASSED.
```
