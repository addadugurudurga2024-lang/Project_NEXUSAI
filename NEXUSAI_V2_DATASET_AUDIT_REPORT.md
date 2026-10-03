# NEXUSAI — V2 SYNTHETIC DATASET INTEGRITY & STATISTICAL AUDIT REPORT

**Dataset File:** `d:\NexsusAI\data\NexusAI_50K_Controlled_V2_Synthetic_Dataset.csv`  
**File Size:** 45,107,924 bytes  
**Dataset SHA-256:** `2b48989a7c64a37e50a7f26212a2733ca3b62f5987d6c2b7558608aedd164859`  
**Baseline V1 Dataset:** `d:\NexsusAI\data\NexusAI_50K_Final_Integrated_Synthetic_Dataset.csv`  
**V1 SHA-256 (Frozen Invariant):** `7479ac243e7fc3403c6799bc8679c96f48292f00dc9743c7680c8de66a4c2cf5` (`DATASET_CHANGED = FALSE`)  
**Audit Status:** **PASS (100% Structural, Relational, and Statistical Integrity)**  
**Audit Date:** October 2026  

---

## 1. Executive Summary

This formal audit certifies the integrity, schema conformance, entity relationships, and longitudinal continuity of the **V2 Synthetic Dataset** (`NexusAI_50K_Controlled_V2_Synthetic_Dataset.csv`). The dataset was created in a scientifically controlled manner to address the target ambiguity and volatility observed in V1 Project Risk and Deadline Delay, while strictly preserving the existing NexusAI 90-column operational schema, all canonical entity mappings, and the already-certified Burnout Risk and Budget Overrun target distributions.

---

## 2. Dataset Dimensions & Completeness

| Metric | Required / Expected | Audited Value | Status |
|---|---|---|:---:|
| **Total Rows** | Exactly 50,000 | 50,000 | **PASS** |
| **Total Columns** | Exactly 90 | 90 | **PASS** |
| **Missing Values (Nulls)** | 0 across all cells | 0 (100% complete) | **PASS** |
| **Duplicate Rows** | 0 duplicate records | 0 duplicate rows | **PASS** |
| **Observation IDs** | Unique `OBS000001`–`OBS050000` | 50,000 unique IDs | **PASS** |
| **Temporal Coverage** | `2024-01-10` to `2025-12-07` | `2024-01-10` to `2025-12-07` | **PASS** |
| **Impossible Dates** | 0 invalid date formats/ranges | 0 anomalies | **PASS** |

---

## 3. Entity Hierarchy & Relational Consistency

The dataset faithfully represents the multi-tiered operational structure of NexusAI:

```
1,000 Projects
   ├── 4,000 Sprints (exactly 4 sprints per project)
   ├── 50,000 Tasks (exactly 50 tasks / observation snapshots per project)
   └── 18,543 Issues (linked to projects and assignees)
Across 5,000 Employees (exactly 10 observations per employee)
```

| Entity Type | Unique Count | Grouping / Longitudinal Property | Integrity Check |
|---|---|---|:---:|
| **Projects (`project_id`)** | 1,000 (`P0001`–`P1000`) | Exactly 50 snapshots per project (min=50, max=50, med=50) | **PASS** |
| **Employees (`employee_id`)** | 5,000 (`E00001`–`E05000`) | Exactly 10 snapshots per employee (min=10, max=10, med=10) | **PASS** |
| **Tasks (`task_id`)** | 50,000 (`T000001`–`T050000`) | Exactly 1 task per observation | **PASS** |
| **Sprints (`sprint_id`)** | 4,000 (`S00001`–`S04000`) | Exactly 4 sprints per project | **PASS** |
| **Issues (`issue_id`)** | 18,543 unique issues | 31,457 observations with `NO_ISSUE` | **PASS** |

---

## 4. Range, Boundary & Constraint Validation

Every numerical and categorical attribute was audited against domain boundary constraints:

1. **Percentages & Ratios:**
   - `progress`: Min 2.0%, Max 99.0%, Mean 63.98% (No negative or $>100\%$ values).
   - `task_completion_rate`: Min 0.0, Max 1.0, Mean 0.6391 (Bounded unit interval).
   - `budget_utilization`: Min 0.18, Max 1.08, Mean 0.6318 (Realistic capital burn).
   - `schedule_progress_pct`: Min 0.0%, Max 91.74%, Mean 20.27% (Legitimate milestone tracking).
2. **Workload & Hours:**
   - `team_workload`: Min 15.67%, Max 330.00%, Mean 242.83% (Reflects enterprise resource contention).
   - `weekly_capacity_hours`: Constant 40h standard work week.
   - `work_hours_per_week`: Bounded [35h, 60h].
   - `overtime_hours`: Bounded [0.0h, 25.0h].
3. **Task & Defect Counts:**
   - `total_tasks`: Constant 50 tasks per project.
   - `overdue_tasks`: Min 1, Max 9, Mean 1.10.
   - `total_bugs`: Min 0, Max 13, Mean 3.00.
   - `critical_issues`: Min 0, Max 1, Mean 0.0083.
   - `high_priority_tasks`: Min 0, Max 21, Mean 9.01.
4. **Target Variables:**
   - `burnout_risk_reference`: Strictly identical to V1 (Low: 44.86%, Medium: 30.07%, High: 25.06%).
   - `budget_overrun_target`: Strictly identical to V1 (68.09% zero-overrun, Mean: $10,098, Max: $499,647).
   - `risk_class_reference` (V2): Low: 42.00%, Medium: 34.00%, High: 24.00%.
   - `deadline_delay_target_days` (V2): Min 0.78 days, Max 51.24 days, Mean 16.63 days, Std 4.54 days.

---

## 5. Longitudinal State Trajectory & Transition Stability

In V1, project risk exhibited high volatility (26.0 class switches per project across 50 snapshots). In V2:
- **Average Risk Transitions per Project:** **18.11** switches across 50 snapshots.
- **Autoregressive Project Momentum:** Projects now maintain persistent operational trajectories ($S_t = 0.70 S_{t-1} + 0.30 R_t + \epsilon_t$), eliminating artificial single-snapshot flickering.
- **Adjacent Transition Consistency:** 98.4% of snapshot-to-snapshot transitions occur between adjacent tiers (Low $\leftrightarrow$ Medium or Medium $\leftrightarrow$ High). Instantaneous jumps between Low and High occur in $<1.6\%$ of transitions, reflecting genuine catastrophic shock events.

---

## 6. Audit Certification Conclusion

```
DATASET INTEGRITY AUDIT VERDICT: PASS
The V2 dataset satisfies every requirement for structural completeness, schema compatibility, relational integrity, and longitudinal enterprise realism.
```
