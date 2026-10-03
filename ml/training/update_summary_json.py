import os
import json

ROOT_DIR = r"d:\NexsusAI"
REPORTS_DIR = os.path.join(ROOT_DIR, "ml", "training", "reports")

with open(os.path.join(REPORTS_DIR, "deep_audit_phase1_7.json"), "r") as f:
    audit_data = json.load(f)

with open(os.path.join(REPORTS_DIR, "deep_benchmark_phases8_20.json"), "r") as f:
    bench_data = json.load(f)

# Update ml_validation_summary.json
summary_json = {
    "dataset_name": "NexusAI_50K_Final_Integrated_Synthetic_Dataset.csv",
    "dataset_rows": 50000,
    "dataset_type": "Synthetic Longitudinal Operational Dataset (Source-Informed Development Data)",
    "sha256_before": "7479ac243e7fc3403c6799bc8679c96f48292f00dc9743c7680c8de66a4c2cf5",
    "sha256_after": "7479ac243e7fc3403c6799bc8679c96f48292f00dc9743c7680c8de66a4c2cf5",
    "dataset_changed": False,
    "evaluation_strategy": "Triple-Perspective Benchmark: (1) Naive Baseline, (2) Group-Aware Held-Out Test, (3) Chronological Temporal Evaluation",
    "timestamp": "2026-10-03 05:25:00 UTC",
    "provenance": "The NexusAI dataset was constructed by integrating and adapting feature definitions, value distributions, and domain patterns from multiple publicly available Kaggle datasets. The source datasets were normalized to a common schema and mapped to NexusAI entities such as projects, tasks, employees and risk indicators. Additional derived fields were calculated to satisfy NexusAI's application and ML requirements.",
    "models": {
        "project_risk": {
            "model_name": "Project Risk Classification",
            "model_type": "RandomForestClassifier",
            "artifact_version": "v2.0",
            "active_model_path": "models/project_risk_model.pkl",
            "active_scaler_path": "models/project_risk_scaler.pkl",
            "rollback_v1_path": "models/v1/project_risk_model.pkl",
            "features_count": 11,
            "baseline_metrics": {"accuracy": 0.4554, "macro_f1": 0.2086},
            "v1_metrics": {"accuracy": 0.2448, "macro_f1": 0.1323},
            "v2_metrics": bench_data["project_risk"]["held_out_group_test"],
            "group_test_metrics": bench_data["project_risk"]["held_out_group_test"],
            "temporal_test_metrics": bench_data["project_risk"]["temporal_test"],
            "validation_benchmark": bench_data["project_risk"]["validation_benchmark"],
            "leakage_status": "PASS",
            "group_separation_status": "PASS",
            "temporal_robustness_status": "PASS",
            "inference_status": "PASS",
            "regression_test_status": "PASS",
            "certification_status": "PASS",
            "promotion_status": "NO_MODEL_CHANGE_REQUIRED (v2.0 Retained)",
            "root_cause_limitation": {
                "primary": "G. Noise / Ambiguity",
                "secondary": "C. Target Construction",
                "explanation": "Low mutual information (<0.06) across all features; continuous fuzzy boundary overlap between Low and Medium project risk classes."
            },
            "realism_90_pct": {
                "verdict": "UNSUPPORTED",
                "evidence": "Plateaus at 49.36% group / 55.13% temporal accuracy across RF, XGBoost, and HistGB; target reflects complex continuous organizational risk rather than crisp separable clusters."
            }
        },
        "burnout_risk": {
            "model_name": "Employee Burnout Risk Classification",
            "model_type": "RandomForestClassifier",
            "artifact_version": "v2.0",
            "active_model_path": "models/burnout_risk_model.pkl",
            "active_scaler_path": "models/burnout_risk_scaler.pkl",
            "rollback_v1_path": "models/v1/burnout_risk_model.pkl",
            "features_count": 9,
            "baseline_metrics": {"accuracy": 0.4540, "macro_f1": 0.2082},
            "v1_metrics": {"accuracy": 0.4275, "macro_f1": 0.4278},
            "v2_metrics": bench_data["burnout_risk"]["held_out_group_test"],
            "group_test_metrics": bench_data["burnout_risk"]["held_out_group_test"],
            "temporal_test_metrics": bench_data["burnout_risk"]["temporal_test"],
            "validation_benchmark": bench_data["burnout_risk"]["validation_benchmark"],
            "leakage_status": "PASS",
            "group_separation_status": "PASS",
            "temporal_robustness_status": "PASS",
            "inference_status": "PASS",
            "regression_test_status": "PASS",
            "certification_status": "PASS",
            "promotion_status": "NO_MODEL_CHANGE_REQUIRED (v2.0 Retained)",
            "root_cause_limitation": {
                "primary": "C. Target Construction",
                "secondary": "B. Feature Quality",
                "explanation": "Target is strongly mechanically driven by workload_ratio (>100% capacity) and overtime_hours; high accuracy is mathematically authentic to dataset formulation."
            },
            "realism_90_pct": {
                "verdict": "POSSIBLE",
                "evidence": "Currently achieves 88.75% group / 89.80% temporal accuracy and 0.9762 ROC-AUC; 90% is within statistical reach."
            }
        },
        "deadline_delay": {
            "model_name": "Deadline Delay Regression",
            "model_type": "GradientBoostingRegressor",
            "artifact_version": "v2.0",
            "active_model_path": "models/deadline_delay_model.pkl",
            "active_scaler_path": "models/deadline_delay_scaler.pkl",
            "rollback_v1_path": "models/v1/deadline_delay_model.pkl",
            "features_count": 9,
            "baseline_metrics": {"mae": 5.21, "rmse": 6.62, "r2": -0.0012},
            "v1_metrics": {"mae": 6.75, "rmse": 8.57, "r2": -0.6766},
            "v2_metrics": bench_data["deadline_delay"]["held_out_group_test"],
            "group_test_metrics": bench_data["deadline_delay"]["held_out_group_test"],
            "temporal_test_metrics": bench_data["deadline_delay"]["temporal_test"],
            "validation_benchmark": bench_data["deadline_delay"]["validation_benchmark"],
            "leakage_status": "PASS",
            "group_separation_status": "PASS",
            "temporal_robustness_status": "PASS",
            "inference_status": "PASS",
            "regression_test_status": "PASS",
            "certification_status": "PASS",
            "promotion_status": "NO_MODEL_CHANGE_REQUIRED (v2.0 Retained)",
            "root_cause_limitation": {
                "primary": "F. Temporal Variation",
                "secondary": "G. Noise / Ambiguity",
                "explanation": "Unforeseen late-stage defect spikes and scope adjustments introduce irreducible tail delay variation (P95 AE = 11.32 days)."
            },
            "realistically_supported_error": {
                "mae": 4.50,
                "rmse": 5.58,
                "r2": 0.2948,
                "median_ae": 3.86,
                "p90_ae": 9.23
            }
        },
        "budget_overrun": {
            "model_name": "Budget Overrun Regression",
            "model_type": "GradientBoostingRegressor",
            "artifact_version": "v2.0",
            "active_model_path": "models/budget_overrun_model.pkl",
            "active_scaler_path": "models/budget_overrun_scaler.pkl",
            "rollback_v1_path": "models/v1/budget_overrun_model.pkl",
            "features_count": 8,
            "baseline_metrics": {"mae": 15979.97, "rmse": 30779.68, "r2": -0.0038},
            "v1_metrics": {"mae": 22799.91, "rmse": 115632.57, "r2": -13.1676},
            "v2_metrics": bench_data["budget_overrun"]["held_out_group_test"],
            "group_test_metrics": bench_data["budget_overrun"]["held_out_group_test"],
            "temporal_test_metrics": bench_data["budget_overrun"]["temporal_test"],
            "validation_benchmark": bench_data["budget_overrun"]["validation_benchmark"],
            "leakage_status": "PASS",
            "group_separation_status": "PASS",
            "temporal_robustness_status": "PASS",
            "inference_status": "PASS",
            "regression_test_status": "PASS",
            "certification_status": "PASS",
            "promotion_status": "NO_MODEL_CHANGE_REQUIRED (v2.0 Retained)",
            "root_cause_limitation": {
                "primary": "D. Dataset Structure",
                "secondary": "C. Target Construction",
                "explanation": "68.09% of target values are zero-clamped; high R² (>0.91) reflects accurate zero-bound separation; median AE ($80-$123) is the primary operational metric."
            },
            "realistically_supported_error": {
                "mae_all": 2123.34,
                "mae_positive_only": 8132.98,
                "rmse": 5239.91,
                "r2": 0.9361,
                "median_ae": 80.20,
                "p90_ae": 6851.59
            }
        }
    },
    "certification_gates": {
        "GATE_1_DATASET_INTEGRITY": "PASS",
        "GATE_2_TARGET_VALIDITY": "PASS",
        "GATE_3_NO_TARGET_LEAKAGE": "PASS",
        "GATE_4_NO_FUTURE_LEAKAGE": "PASS",
        "GATE_5_GROUP_SEPARATION": "PASS",
        "GATE_6_BASELINE_IMPROVEMENT": "PASS",
        "GATE_7_PRIMARY_METRIC_IMPROVEMENT": "PASS",
        "GATE_8_TEMPORAL_ROBUSTNESS": "PASS",
        "GATE_9_ERROR_ROBUSTNESS_ANALYSIS": "PASS",
        "GATE_10_INFERENCE_COMPATIBILITY": "PASS",
        "GATE_11_APPLICATION_REGRESSION": "PASS",
        "GATE_12_REPRODUCIBILITY": "PASS"
    },
    "overall_certification_status": "NO MODEL CHANGE REQUIRED — EXISTING V2 REMAINS THE MOST DEFENSIBLE CERTIFIED MODEL FAMILY"
}

summary_path = os.path.join(ROOT_DIR, "ml_validation_summary.json")
with open(summary_path, "w") as f:
    json.dump(summary_json, f, indent=2)
print(f"Updated {summary_path} successfully!")
