"""
NexusAI - Controlled V2 Synthetic Dataset Generator
Generates: NexusAI_50K_Controlled_V2_Synthetic_Dataset.csv
Strictly preserves:
- 50,000 rows, 90 columns schema
- 1,000 projects, 5,000 employees, 50,000 tasks, 4,000 sprints, 18,543 issues
- FROZEN Burnout Risk and Budget Overrun targets
- Longitudinal project snapshots (2024-01-10 to 2025-12-07)
- Zero missing values, zero duplicates
Improves:
- Project Risk latent operational pressure & longitudinal momentum
- Deadline Delay realistic schedule gap & delivery dynamics
"""

import os
import sys
import hashlib
import numpy as np
import pandas as pd

RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)

V1_PATH = r"d:\NexsusAI\data\NexusAI_50K_Final_Integrated_Synthetic_Dataset.csv"
V2_PATH = r"d:\NexsusAI\data\NexusAI_50K_Controlled_V2_Synthetic_Dataset.csv"
EXPECTED_V1_SHA256 = "7479ac243e7fc3403c6799bc8679c96f48292f00dc9743c7680c8de66a4c2cf5"


def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def generate_v2_dataset():
    print("=" * 80)
    print("NEXUSAI: CONTROLLED V2 SYNTHETIC DATASET GENERATION")
    print("=" * 80)

    # 1. Verify V1 Dataset Hash Invariant
    v1_hash_before = compute_sha256(V1_PATH)
    print(f"\n[1] V1 DATASET INTEGRITY CHECK:")
    print(f"  V1 Path: {V1_PATH}")
    print(f"  V1 Hash: {v1_hash_before}")
    assert v1_hash_before == EXPECTED_V1_SHA256, f"V1 Hash mismatch! Expected {EXPECTED_V1_SHA256}"
    print("  [PASS] V1 Authoritative Dataset strictly verified and intact.")

    # 2. Load V1 Dataset
    df = pd.read_csv(V1_PATH)
    n_rows, n_cols = len(df), len(df.columns)
    print(f"\n[2] LOADED V1 DATASET: {n_rows:,} rows × {n_cols} columns")

    # -----------------------------------------------------------------
    # 3. GENERATE V2 PROJECT RISK (Latent Operational Pressure & Momentum)
    # -----------------------------------------------------------------
    print("\n[3] GENERATING V2 PROJECT RISK TARGET...")
    # Multi-component enterprise pressure formulation
    p_budget = np.clip((df["budget_utilization"] - (df["progress"] / 100.0)) / 0.30, -1.0, 2.0)
    p_workload = np.clip((df["team_workload"] - 120.0) / 100.0, -0.5, 2.0)
    p_schedule = np.clip((df["overdue_tasks"] - 1.0) / 2.5 + 0.6 * (1.0 - df["task_completion_rate"]), -0.5, 2.0)
    p_velocity = np.clip((42.0 - df["avg_sprint_velocity"]) / 8.0, -1.0, 1.5)
    p_quality = np.clip((df["total_bugs"] / 4.0) + 1.2 * df["critical_issues"], 0.0, 2.0)
    p_scope = np.clip((df["remaining_work"] / 100.0) * (df["high_priority_tasks"] / 8.0), 0.0, 1.5)
    p_proj = 0.15 * ((df["complexity_score"] - 5.0) / 3.0) + 0.15 * ((df["technical_debt"] - 40.0) / 20.0)

    raw_risk = (
        0.28 * p_budget +
        0.22 * p_workload +
        0.18 * p_schedule +
        0.14 * p_velocity +
        0.10 * p_quality +
        0.04 * p_scope +
        0.04 * p_proj
    )
    df["_raw_risk"] = raw_risk

    # Longitudinal autoregressive momentum per project
    proj_risks = np.zeros(n_rows)
    for pid, grp in df.groupby("project_id", sort=False):
        s_grp = grp.sort_values("snapshot_date")
        vals = s_grp["_raw_risk"].values
        k_obs = len(vals)
        proj_baseline = np.random.normal(0, 0.10)
        curr = vals[0] + proj_baseline
        state = np.zeros(k_obs)
        for i in range(k_obs):
            shock = np.random.normal(0, 0.08)
            curr = 0.70 * curr + 0.30 * vals[i] + shock
            state[i] = curr
        proj_risks[s_grp.index] = state

    # Calibrate thresholds for ~42% Low, ~34% Medium, ~24% High
    q_low = float(np.percentile(proj_risks, 42.0))
    q_high = float(np.percentile(proj_risks, 76.0))
    print(f"  Latent Risk Thresholds: Cutoff_Low={q_low:.4f} | Cutoff_High={q_high:.4f}")

    v2_risk_labels = np.where(
        proj_risks < q_low, "low",
        np.where(proj_risks < q_high, "medium", "high")
    )
    df["risk_class_reference"] = v2_risk_labels

    vc = df["risk_class_reference"].value_counts()
    for k, v in vc.items():
        print(f"  {k.upper()}: {v:,} ({v/n_rows*100:.2f}%)")

    # -----------------------------------------------------------------
    # 4. GENERATE V2 DEADLINE DELAY (Realistic Schedule Gap & Delivery Dynamics)
    # -----------------------------------------------------------------
    print("\n[4] GENERATING V2 DEADLINE DELAY TARGET...")
    sched_gap = np.maximum(0.0, df["schedule_progress_pct"] - df["progress"])
    vel_drag = np.clip((42.0 - df["avg_sprint_velocity"]) / 8.0, -0.5, 2.0)
    overdue_p = np.clip(df["overdue_tasks"] - 1.0, 0.0, 8.0)
    workload_s = np.clip((df["team_workload"] - 120.0) / 80.0, 0.0, 2.5)
    scope_factor = df["remaining_work"] / 100.0

    base_delay = (
        6.0 +
        10.0 * (sched_gap / 25.0) +
        4.0 * overdue_p +
        3.0 * vel_drag +
        3.5 * workload_s +
        3.5 * df["critical_issues"] +
        0.6 * df["total_bugs"] +
        3.0 * scope_factor +
        0.8 * (df["complexity_score"] - 5.0)
    )

    proj_delays = np.zeros(n_rows)
    for pid, grp in df.groupby("project_id", sort=False):
        s_grp = grp.sort_values("snapshot_date")
        vals = base_delay.loc[s_grp.index].values
        k_obs = len(vals)
        proj_b = np.random.normal(0, 1.5)
        curr = vals[0] + proj_b
        state = np.zeros(k_obs)
        for i in range(k_obs):
            noise = np.random.normal(0, 1.8)
            curr = 0.70 * curr + 0.30 * vals[i] + noise
            state[i] = max(0.0, curr)
        proj_delays[s_grp.index] = state

    v2_delay = np.clip(proj_delays, 0.0, 55.0)
    df["deadline_delay_target_days"] = np.round(v2_delay, 2)

    print(f"  Deadline Delay V2 Summary:")
    print(f"    Mean:   {df['deadline_delay_target_days'].mean():.2f} days")
    print(f"    Median: {df['deadline_delay_target_days'].median():.2f} days")
    print(f"    Std:    {df['deadline_delay_target_days'].std():.2f} days")
    print(f"    Min:    {df['deadline_delay_target_days'].min():.2f} days")
    print(f"    Max:    {df['deadline_delay_target_days'].max():.2f} days")

    # Drop temporary calculation columns
    df.drop(columns=["_raw_risk"], inplace=True)

    # -----------------------------------------------------------------
    # 5. INTEGRITY ASSERTIONS & CHECKS
    # -----------------------------------------------------------------
    print("\n[5] VERIFYING V2 SCHEMA & INTEGRITY...")
    assert len(df) == 50000, f"Expected 50,000 rows, got {len(df)}"
    assert len(df.columns) == 90, f"Expected 90 columns, got {len(df.columns)}"
    assert df.isnull().sum().sum() == 0, "Null values detected in V2!"
    assert df.duplicated().sum() == 0, "Duplicate rows detected in V2!"
    assert df["project_id"].nunique() == 1000, "Project count mismatch!"
    assert df["employee_id"].nunique() == 5000, "Employee count mismatch!"
    assert df["task_id"].nunique() == 50000, "Task count mismatch!"
    assert df["sprint_id"].nunique() == 4000, "Sprint count mismatch!"

    # Check that frozen targets were strictly untouched
    df_v1 = pd.read_csv(V1_PATH)
    assert (df["burnout_risk_reference"] == df_v1["burnout_risk_reference"]).all(), "Burnout target altered!"
    assert (df["budget_overrun_target"] == df_v1["budget_overrun_target"]).all(), "Budget target altered!"
    assert (df["budget_overrun_target_pct"] == df_v1["budget_overrun_target_pct"]).all(), "Budget pct altered!"
    print("  [PASS] All 90 schema columns, entity counts, and frozen targets verified 100% intact.")

    # -----------------------------------------------------------------
    # 6. WRITE V2 DATASET
    # -----------------------------------------------------------------
    print(f"\n[6] SAVING V2 DATASET TO: {V2_PATH}...")
    df.to_csv(V2_PATH, index=False)
    v2_size = os.path.getsize(V2_PATH)
    v2_hash = compute_sha256(V2_PATH)
    print(f"  V2 File Size: {v2_size:,} bytes")
    print(f"  V2 SHA-256:   {v2_hash}")

    # Re-verify V1 hash invariant
    v1_hash_after = compute_sha256(V1_PATH)
    print(f"\n[7] FINAL V1 INTEGRITY RE-VERIFICATION:")
    print(f"  V1 Hash Before: {v1_hash_before}")
    print(f"  V1 Hash After:  {v1_hash_after}")
    assert v1_hash_after == EXPECTED_V1_SHA256, "CRITICAL: V1 dataset was unexpectedly modified!"
    print("  [PASS] V1 dataset is completely UNTOUCHED (DATASET_CHANGED = FALSE).")

    print("\n" + "=" * 80)
    print("V2 DATASET GENERATION COMPLETE & CERTIFIED")
    print("=" * 80)
    return v2_hash


if __name__ == "__main__":
    generate_v2_dataset()
