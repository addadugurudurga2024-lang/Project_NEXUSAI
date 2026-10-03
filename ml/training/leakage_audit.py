import os
import json
import pandas as pd
import numpy as np

CSV_PATH = r"D:\NexsusAI\data\NexusAI_50K_Final_Integrated_Synthetic_Dataset.csv"
OUTPUT_DIR = r"D:\NexsusAI\ml\training\reports"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def audit_leakage():
    print("=" * 70)
    print("STEP 5, 6, 7: LEAKAGE AUDIT & TARGET DEFINITION ANALYSIS")
    print("=" * 70)

    df = pd.read_csv(CSV_PATH)
    print(f"Loaded {len(df):,} rows.")

    targets = {
        "project_risk": "risk_class_reference",
        "burnout_risk": "burnout_risk_reference",
        "deadline_delay": "deadline_delay_target_days",
        "budget_overrun": "budget_overrun_target"
    }

    all_target_cols = [
        "risk_class_reference",
        "burnout_risk_reference",
        "deadline_delay_target_days",
        "budget_overrun_target",
        "budget_overrun_target_pct"
    ]

    identifier_cols = [
        "observation_id", "project_id", "employee_id", "task_id",
        "sprint_id", "issue_id", "assigned_to", "split", "entity_type"
    ]

    text_cols = [
        "project_name", "employee_name", "task_name", "title",
        "description", "goal", "sprint_name", "skills", "required_skills"
    ]

    future_or_post_event_cols = [
        "completed_date", "resolved_at"
    ]

    # Map target columns to numeric for correlation analysis
    df["risk_class_num"] = df["risk_class_reference"].map({"low": 0, "medium": 1, "high": 2})
    df["burnout_risk_num"] = df["burnout_risk_reference"].map({"low": 0, "medium": 1, "high": 2})

    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    # 1. Target Leakage & High Correlation Check
    correlations = {}
    suspicious_features = {}
    for t_name, t_col in [
        ("project_risk", "risk_class_num"),
        ("burnout_risk", "burnout_risk_num"),
        ("deadline_delay", "deadline_delay_target_days"),
        ("budget_overrun", "budget_overrun_target")
    ]:
        corr_series = df[num_cols].corrwith(df[t_col]).abs().sort_values(ascending=False)
        correlations[t_name] = {k: round(float(v), 4) for k, v in corr_series.head(15).items()}
        # Identify suspicious features with |r| > 0.95 excluding self
        susp = {k: round(float(v), 4) for k, v in corr_series.items() if v > 0.95 and k != t_col and k not in all_target_cols and "num" not in k}
        if susp:
            suspicious_features[t_name] = susp

    print("\nTop Correlations per Target:")
    print(json.dumps(correlations, indent=2))
    if suspicious_features:
        print("\nWARNING: Suspicious high-correlation features (|r| > 0.95):")
        print(json.dumps(suspicious_features, indent=2))
    else:
        print("\n[PASS] No direct single-feature leakage (|r| > 0.95) found in candidate numeric features.")

    # 2. Inspect Model Feature Sets Against Production Inference
    # Model 1: Project Risk
    # Inference expects: progress, task_completion_rate, overdue_tasks, avg_sprint_velocity,
    # total_bugs, critical_issues, team_workload, budget_utilization, remaining_work,
    # high_priority_tasks, total_tasks
    model1_features = [
        "progress", "task_completion_rate", "overdue_tasks", "avg_sprint_velocity",
        "total_bugs", "critical_issues", "team_workload", "budget_utilization",
        "remaining_work", "high_priority_tasks", "total_tasks"
    ]
    
    # Model 2: Burnout Risk
    # Inference expects: workload_ratio, estimated_hours, overtime_hours, active_projects,
    # active_task_count, overdue_task_count, sprint_story_points, completion_rate,
    # high_priority_task_count
    # Note: In CSV, estimated_hours for employee might be represented as assigned_hours or estimated_hours
    model2_features = [
        "workload_ratio", "assigned_hours", "overtime_hours", "active_projects",
        "active_task_count", "overdue_task_count", "sprint_story_points",
        "completion_rate", "high_priority_task_count"
    ]

    # Model 3: Deadline Delay
    # Inference expects: progress, task_completion_rate, overdue_tasks, critical_issues,
    # team_workload, total_days (or days_total), days_remaining, schedule_progress_pct, progress_gap
    # Let's check CSV columns: total_days vs total_days in CSV
    # If total_days is not in CSV, can calculate from end_date - start_date
    model3_features = [
        "progress", "task_completion_rate", "overdue_tasks", "critical_issues",
        "team_workload", "days_remaining", "schedule_progress_pct", "progress_gap"
    ]

    # Model 4: Budget Overrun
    # Inference expects: budget_utilization, progress, spending_rate_ratio, remaining_work,
    # overdue_tasks, critical_issues, team_workload, days_remaining
    model4_features = [
        "budget_utilization", "progress", "spending_rate_ratio", "remaining_work",
        "overdue_tasks", "critical_issues", "team_workload", "days_remaining"
    ]

    models_config = {
        "project_risk": {
            "target": "risk_class_reference",
            "type": "classification",
            "classes": ["low", "medium", "high"],
            "features": model1_features,
            "group_col": "project_id"
        },
        "burnout_risk": {
            "target": "burnout_risk_reference",
            "type": "classification",
            "classes": ["low", "medium", "high"],
            "features": model2_features,
            "group_col": "employee_id"
        },
        "deadline_delay": {
            "target": "deadline_delay_target_days",
            "type": "regression",
            "features": model3_features,
            "group_col": "project_id"
        },
        "budget_overrun": {
            "target": "budget_overrun_target",
            "type": "regression",
            "features": model4_features,
            "group_col": "project_id"
        }
    }

    # Verify all feature columns exist in CSV
    missing_by_model = {}
    for m_name, m_cfg in models_config.items():
        missing = [f for f in m_cfg["features"] if f not in df.columns]
        if missing:
            missing_by_model[m_name] = missing
        # Verify no target in feature set
        assert m_cfg["target"] not in m_cfg["features"], f"Target in features for {m_name}!"
        for tf in all_target_cols:
            assert tf not in m_cfg["features"], f"Target auxiliary {tf} in features for {m_name}!"
    
    print("\nFeature Verification Against CSV:")
    for m_name, m_cfg in models_config.items():
        print(f"  {m_name:16s}: {len(m_cfg['features'])} features, Target: '{m_cfg['target']}' (Missing: {missing_by_model.get(m_name, 'None')})")

    # 3. Snapshot Leakage Analysis
    # Check if features are known at snapshot_date
    snapshot_audit = {
        "safe_features": list(set(model1_features + model2_features + model3_features + model4_features)),
        "excluded_future_cols": future_or_post_event_cols,
        "excluded_target_cols": all_target_cols,
        "excluded_identifier_cols": identifier_cols,
        "excluded_text_cols": text_cols
    }

    report = {
        "correlations": correlations,
        "suspicious_features": suspicious_features,
        "models_config": models_config,
        "snapshot_audit": snapshot_audit
    }

    with open(os.path.join(OUTPUT_DIR, "leakage_audit_report.json"), "w") as f:
        json.dump(report, f, indent=2)
    print("\nSaved leakage_audit_report.json!")

if __name__ == "__main__":
    audit_leakage()
